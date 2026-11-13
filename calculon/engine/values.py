"""Values and arithmetic."""

from dataclasses import dataclass, replace
from datetime import datetime, timedelta
from decimal import Decimal, InvalidOperation, localcontext

from dateutil.relativedelta import relativedelta

from . import units as U
from .currency import RatesError, RateTable


class CalcError(ValueError):
    """Raised for anything that cannot be calculated."""


ZERO = Decimal(0)
ONE = Decimal(1)


@dataclass(frozen=True)
class Q:
    """A number with optional units.

    pct: the value is a percentage; mag holds the fraction (10% -> 0.1).
    fmt: display hint: "hex", "bin", "oct", "sci", "fraction", "x" (multiplier).
    parts: for durations built from several pieces ("3 months 5 days"), the pieces as
        ((unit, amount), ...); mag/units hold the combined value in the largest unit.
    """

    mag: Decimal
    units: U.Units = ()
    pct: bool = False
    fmt: str | None = None
    parts: tuple[tuple[str, Decimal], ...] | None = None

    @property
    def unitless(self) -> bool:
        return not self.units

    def plain(self) -> Q:
        return Q(self.mag, self.units)

    def is_time(self) -> bool:
        return len(self.units) == 1 and self.units[0][0] in U.TIME_UNITS and self.units[0][1] == 1

    def time_parts(self) -> tuple[tuple[str, Decimal], ...]:
        if self.parts:
            return self.parts
        if self.is_time():
            return ((self.units[0][0], self.mag),)
        raise CalcError("not a duration")


@dataclass(frozen=True)
class DateVal:
    dt: datetime
    has_date: bool = True
    has_time: bool = False


type Value = Q | DateVal


def num(x: int | str | Decimal) -> Q:
    return Q(Decimal(x))


def _cur_atoms(units: U.Units) -> list[tuple[str, int]]:
    return [(a, p) for a, p in units if U.is_currency(a)]


def compatible(a: U.Units, b: U.Units) -> bool:
    return U.dims_of(a) == U.dims_of(b)


def convert(q: Q, target: U.Units, rates: RateTable) -> Q:
    """Convert q into the target units (dimensions must match)."""
    if q.units == target:
        return q
    if not compatible(q.units, target):
        raise CalcError("incompatible units")
    if (
        len(q.units) == 1
        and len(target) == 1
        and q.units[0][0] in U.TEMPERATURES
        and target[0][0] in U.TEMPERATURES
    ):
        return Q(U.convert_temperature(q.mag, q.units[0][0], target[0][0]), target)
    mag = q.mag * U.physical_factor(q.units, target)
    src_cur = _cur_atoms(q.units)
    dst_cur = _cur_atoms(target)
    if src_cur:
        # Pair currencies by power: the dimensions match, so there is one per power.
        for (sa, sp), (da, _dp) in zip(
            sorted(src_cur, key=lambda x: x[1]), sorted(dst_cur, key=lambda x: x[1]), strict=False
        ):
            try:
                rate = rates.rate(sa[1:], da[1:])
            except RatesError as exc:
                raise CalcError(str(exc)) from exc
            mag *= rate**sp
    return Q(mag, target)


def simplify(q: Q, rates: RateTable) -> Q:
    """Cancel units of the same kind (hours/days, EUR/USD)."""
    units = U.normalize(q.units)
    mag = q.mag
    changed = True
    while changed:
        changed = False
        for i, (a, _pa) in enumerate(units):
            for j in range(i + 1, len(units)):
                b, pb = units[j]
                if U.dimensionality(a) != U.dimensionality(b):
                    continue
                # convert b into a
                if U.is_currency(a):
                    try:
                        f = rates.rate(b[1:], a[1:])
                    except RatesError as exc:
                        raise CalcError(str(exc)) from exc
                elif a in U.TEMPERATURES or b in U.TEMPERATURES:
                    continue
                else:
                    f = U.factor(b, a)
                mag *= f**pb
                units = U.normalize(units[:j] + ((a, pb),) + units[j + 1 :])
                changed = True
                break
            if changed:
                break
    return Q(mag, units, q.pct, q.fmt)


def _winner(a: U.Units, b: U.Units) -> U.Units:
    """Units for a + b: larger unit for same kind, last used for currencies."""
    if len(a) == 1 and len(b) == 1:
        (ua, pa), (ub, pb) = a[0], b[0]
        if U.is_currency(ua) or U.is_currency(ub):
            return b
        if pa == pb == 1 and ua not in U.TEMPERATURES:
            return ((U.larger(ua, ub), 1),)
    return b if _cur_atoms(b) else a


def add(a: Value, b: Value, rates: RateTable, sign: int = 1) -> Value:
    if isinstance(a, DateVal) or isinstance(b, DateVal):
        return _date_add(a, b, sign)
    if a.pct and b.pct:
        return Q(a.mag + sign * b.mag, pct=True)
    if b.pct:  # 200 + 10%
        return Q(a.mag * (ONE + sign * b.mag), a.units, fmt=a.fmt)
    if a.pct:
        if b.unitless:  # 30% + 0.4 = 70%
            return Q(a.mag + sign * b.mag, pct=True)
        return Q(b.mag * (ONE + sign * a.mag), b.units)
    if a.unitless or b.unitless:
        units = a.units or b.units
        parts = None
        return Q(a.mag + sign * b.mag, units, fmt=a.fmt or b.fmt, parts=parts)
    if a.units == b.units:
        return Q(a.mag + sign * b.mag, a.units, parts=_merge_parts(a, b, sign))
    if not compatible(a.units, b.units):
        raise CalcError("can't add incompatible units")
    target = _winner(a.units, b.units)
    ca, cb = convert(a, target, rates), convert(b, target, rates)
    return Q(ca.mag + sign * cb.mag, target, parts=_merge_parts(a, b, sign))


def _merge_parts(a: Q, b: Q, sign: int) -> tuple[tuple[str, Decimal], ...] | None:
    if sign != 1:
        return None
    try:
        pa, pb = a.time_parts(), b.time_parts()
    except CalcError:
        return None
    merged: dict[str, Decimal] = {}
    for unit, amount in (*pa, *pb):
        merged[unit] = merged.get(unit, ZERO) + amount
    return tuple(merged.items())


def mul(a: Value, b: Value, rates: RateTable) -> Q:
    a, b = _need_q(a), _need_q(b)
    if a.pct and b.pct:
        return Q(a.mag * b.mag, pct=True)
    if a.pct or b.pct:  # 50% × 30 = 15
        return Q(a.mag * b.mag, a.units + b.units)
    # $30 × 4 days: money times a bare duration reads as $30/day × 4 days.
    for m, t in ((a, b), (b, a)):
        if _is_money(m) and t.is_time() and not t.parts:
            return Q(m.mag * t.mag, m.units)
    q = Q(a.mag * b.mag, a.units + b.units, fmt=a.fmt or b.fmt)
    return simplify(q, rates)


def div(a: Value, b: Value, rates: RateTable) -> Q:
    a, b = _need_q(a), _need_q(b)
    if b.mag == 0:
        raise CalcError("division by zero")
    if a.pct and b.pct:
        return Q(a.mag / b.mag)
    if b.pct:
        return Q(a.mag / b.mag, a.units)
    inv = tuple((u, -p) for u, p in b.units)
    q = Q(a.mag / b.mag, a.units + inv, pct=a.pct, fmt=a.fmt)
    return simplify(q, rates)


def power(a: Value, b: Value) -> Q:
    a, b = _need_q(a), _need_q(b)
    if not b.unitless:
        raise CalcError("exponent must be a plain number")
    if abs(b.mag) > 10000 or (abs(a.mag) > 1 and abs(b.mag) * a.mag.adjusted() > 100000):
        raise CalcError("number too large")
    exp = b.mag
    if a.units:
        if exp != exp.to_integral_value():
            raise CalcError("unit powers must be whole numbers")
        units = tuple((u, p * int(exp)) for u, p in a.units)
    else:
        units = ()
    try:
        with localcontext() as ctx:
            ctx.prec = 34
            if exp == exp.to_integral_value():
                mag = a.mag ** int(exp)
            else:
                if a.mag < 0:
                    raise CalcError("can't take a fractional power of a negative number")
                mag = Decimal(float(a.mag) ** float(exp)) if a.mag else ZERO
                mag = Decimal(f"{mag:.15g}")
    except (InvalidOperation, OverflowError, ZeroDivisionError) as exc:
        raise CalcError("can't calculate that power") from exc
    if not mag.is_finite():  # 0^-1 gives Infinity without an error
        raise CalcError("division by zero" if a.mag == 0 else "can't calculate that power")
    return Q(mag, units)


def modulo(a: Value, b: Value) -> Q:
    a, b = _need_q(a), _need_q(b)
    if b.mag == 0:
        raise CalcError("division by zero")
    return Q(a.mag % b.mag, a.units)


def negate(a: Value) -> Q:
    a = _need_q(a)
    return replace(a, mag=-a.mag, parts=None)


def _is_money(q: Q) -> bool:
    return len(q.units) == 1 and U.is_currency(q.units[0][0]) and q.units[0][1] == 1


def _need_q(v: Value) -> Q:
    if isinstance(v, DateVal):
        raise CalcError("can't do that with a date")
    return v


_REL_FIELDS = {
    "century": ("years", 100),
    "decade": ("years", 10),
    "year": ("years", 1),
    "month": ("months", 1),
    "fortnight": ("weeks", 2),
    "week": ("weeks", 1),
    "day": ("days", 1),
    "night": ("days", 1),
    "hour": ("hours", 1),
    "minute": ("minutes", 1),
    "second": ("seconds", 1),
    "millisecond": ("microseconds", 1000),
}


def to_relativedelta(q: Q) -> relativedelta:
    kw: dict[str, float] = {}
    for unit, amount in q.time_parts():
        field_, mult = _REL_FIELDS[unit]
        kw[field_] = kw.get(field_, 0) + float(amount) * mult
    # relativedelta needs whole years/months; spill fractions into days.
    days_extra = 0.0
    for field_, per in (("years", 365.25), ("months", 30.436875)):
        if field_ in kw and kw[field_] != int(kw[field_]):
            whole = int(kw[field_])
            days_extra += (kw[field_] - whole) * per
            kw[field_] = whole
    if days_extra:
        kw["days"] = kw.get("days", 0) + days_extra
    ints = {k: int(v) for k, v in kw.items() if k in ("years", "months")}
    rest = {k: v for k, v in kw.items() if k not in ("years", "months")}
    return relativedelta(**ints) + relativedelta(seconds=timedelta(**rest).total_seconds())


def _date_add(a: Value, b: Value, sign: int) -> Value:
    if isinstance(a, DateVal) and isinstance(b, Q):
        delta = to_relativedelta(b)
        dt = a.dt + delta if sign > 0 else a.dt - delta
        has_time = a.has_time or any(u in ("hour", "minute", "second") for u, _ in b.time_parts())
        return DateVal(dt, a.has_date, has_time)
    if isinstance(a, Q) and isinstance(b, DateVal) and sign > 0:
        return _date_add(b, a, 1)
    if isinstance(a, DateVal) and isinstance(b, DateVal) and sign < 0:
        return date_diff(b, a, absolute=True)
    raise CalcError("can't add those")


def date_diff(start: DateVal, end: DateVal, absolute: bool = False) -> Q:
    """Duration from start to end, as parts like '3 weeks 5 days'."""
    a, b = start.dt, end.dt
    # March 5, 10:00 - 11:30: a time on its own is on the same day as the date
    if start.has_date and not end.has_date:
        b = b.replace(year=a.year, month=a.month, day=a.day)
    elif end.has_date and not start.has_date:
        a = a.replace(year=b.year, month=b.month, day=b.day)
    if (a.tzinfo is None) != (b.tzinfo is None):
        a, b = a.astimezone(), b.astimezone()
    if (not start.has_date or not end.has_date or absolute) and b < a:
        a, b = b, a
    neg = b < a
    if neg:
        a, b = b, a
    rd = relativedelta(b, a)
    parts: list[tuple[str, Decimal]] = []
    if rd.years:
        parts.append(("year", Decimal(rd.years)))
    if rd.months:
        parts.append(("month", Decimal(rd.months)))
    weeks, days = divmod(rd.days, 7)
    if weeks:
        parts.append(("week", Decimal(weeks)))
    if days:
        parts.append(("day", Decimal(days)))
    if rd.hours:
        parts.append(("hour", Decimal(rd.hours)))
    if rd.minutes:
        parts.append(("minute", Decimal(rd.minutes)))
    if rd.seconds and not parts:
        parts.append(("second", Decimal(rd.seconds)))
    if not parts:
        parts.append(("day" if start.has_date else "minute", ZERO))
    unit = parts[0][0]
    total_seconds = Decimal(str((b - a).total_seconds()))
    mag = total_seconds / U.factor(unit, "second")
    if neg:
        mag = -mag
        parts = [(u, -v) for u, v in parts]
    return Q(mag, ((unit, 1),), parts=tuple(parts))
