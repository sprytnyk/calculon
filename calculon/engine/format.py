"""Turning values into the text shown in the results column."""

from dataclasses import dataclass, replace
from datetime import datetime
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal, localcontext
from fractions import Fraction

from . import units as U
from .currency import ZERO_DECIMALS
from .currency import display as currency_display
from .numbers import separators
from .ukrainian import CITY_NAMES
from .values import DateVal, Q, Value

# The answers column shortens big numbers: $386,800,000.00 shows as $386.8M.
SHORT_FROM = Decimal(10) ** 6
SHORT_SCALES = {
    "en": ((Decimal(10) ** 12, "T"), (Decimal(10) ** 9, "B"), (SHORT_FROM, "M")),
    "uk": ((Decimal(10) ** 12, " трлн"), (Decimal(10) ** 9, " млрд"), (SHORT_FROM, " млн")),
}
# Month names as they follow a day number: "10 листопада".
MONTHS_EN = (
    "January", "February", "March", "April", "May", "June",
    "July", "August", "September", "October", "November", "December",
)  # fmt: skip
MONTHS_UK = (
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
)  # fmt: skip


@dataclass(frozen=True)
class FormatOptions:
    number_style: str = "comma_dot"
    max_decimals: int = 3
    money_decimals: int = 2
    time_24h: bool = True
    lang: str = "en"  # unit names, month names and where currency symbols go
    this_year: int | None = None  # dates in other years show the year; None reads the clock


def format_number(x: Decimal, opts: FormatOptions, decimals: int | None = None) -> str:
    thousands, point = separators(opts.number_style)
    if not x.is_finite():
        return str(x)
    magnitude = x.copy_abs()
    if magnitude >= Decimal("1e21"):
        return format_sci(x, opts)
    places = opts.max_decimals if decimals is None else decimals
    quantum = Decimal(1).scaleb(-places)
    if decimals is None and 0 < magnitude < quantum:
        return format_sci(x, opts)
    rounding = ROUND_HALF_EVEN if decimals is None else ROUND_HALF_UP
    with localcontext() as ctx:
        if x:
            # Allow the whole part, the requested decimal places, and a rounding carry.
            ctx.prec = max(ctx.prec, x.adjusted() + places + 2)
        q = x.quantize(quantum, rounding=rounding)
    if q.is_zero():
        q = q.copy_abs()
    whole, _, fraction = f"{q:,f}".partition(".")
    whole = whole.replace(",", thousands)
    if decimals is None:
        fraction = fraction.rstrip("0")
    return whole + point + fraction if fraction else whole


def format_sci(x: Decimal, opts: FormatOptions) -> str:
    _, point = separators(opts.number_style)
    text = f"{x:.{min(opts.max_decimals, 10)}e}"
    mant, _, exp = text.partition("e")
    if "." in mant:
        mant = mant.rstrip("0").rstrip(".")
    return f"{mant.replace('.', point)}e{int(exp)}"


def format_short(x: Decimal, opts: FormatOptions) -> str | None:
    """386,800,000 as 386.8M, or None when the number isn't big enough to shorten."""
    if not x.is_finite() or abs(x) < SHORT_FROM:
        return None
    three = replace(opts, max_decimals=3)
    if abs(x) >= Decimal(10) ** 15:
        return format_sci(x, three)
    for size, suffix in SHORT_SCALES.get(opts.lang, SHORT_SCALES["en"]):
        if abs(x) >= size - size / 2000:  # 999,999,999 rounds to 1B, not 1,000M
            return format_number(x / size, three) + suffix
    return None


def format_value(v: Value, opts: FormatOptions, short: bool = False) -> str:
    """`short` is for the answers column: big numbers as 386.8M."""
    if isinstance(v, DateVal):
        return format_date(v, opts)
    return format_q(v, opts, short)


def format_q(q: Q, opts: FormatOptions, short: bool = False) -> str:
    if q.pct:
        return format_number(q.mag * 100, opts) + "%"
    if q.fmt and q.unitless:
        special = _special(q, opts)
        if special is not None:
            return special
    if q.parts and len(q.parts) > 1:
        return " ".join(_part_text(u, a, opts) for u, a in q.parts if a)
    code = U.currency_code(q.units)
    money = code is not None and q.units[0] == (U.CUR + code, 1)
    decimals = None
    if money and code:
        decimals = 0 if code in ZERO_DECIMALS else opts.money_decimals
    number = format_sci(q.mag, opts) if q.fmt == "sci" else format_number(q.mag, opts, decimals)
    if short and not q.fmt and (shorter := format_short(q.mag, opts)) is not None:
        number = shorter
    if not q.units:
        return number
    prefix, suffix = U.display_units(q.units, q.mag, opts.lang)
    if prefix:
        sym, is_prefix = currency_display(prefix[1:])
        if is_prefix and opts.lang != "uk":
            sign = ""
            if number.startswith("-"):
                sign, number = "-", number[1:]
            text = f"{sign}{sym}{number}"
        else:
            text = f"{number} {sym}"
        return text + suffix
    return number + suffix


def _part_text(unit: str, amount: Decimal, opts: FormatOptions) -> str:
    return f"{format_number(amount, opts)} {U.atom_text(unit, 1, amount, opts.lang)}"


def _special(q: Q, opts: FormatOptions) -> str | None:
    x = q.mag
    if q.fmt == "x":
        return format_number(x, opts) + "x"
    if q.fmt == "sci":
        return format_sci(x, opts)
    if q.fmt == "fraction":
        f = Fraction(x).limit_denominator(10000)
        if f.denominator == 1:
            return str(f.numerator)
        return f"{f.numerator}/{f.denominator}"
    if q.fmt == "one_in":
        return f"1/{format_number(1 / x, opts)}" if x else None
    if x != x.to_integral_value() or x.adjusted() > 40:
        return None  # int(1e999999) alone takes a minute
    n = int(x)
    sign = "-" if n < 0 else ""
    n = abs(n)
    if q.fmt == "hex":
        return f"{sign}0x{n:X}"
    if q.fmt == "bin":
        return f"{sign}0b{n:b}"
    if q.fmt == "oct":
        return f"{sign}0o{n:o}"
    return None


def format_date(d: DateVal, opts: FormatOptions) -> str:
    dt = d.dt
    parts = []
    if d.has_date:
        month = (MONTHS_UK if opts.lang == "uk" else MONTHS_EN)[dt.month - 1]
        text = f"{dt.day} {month}"
        if dt.year != (opts.this_year or datetime.now().year):
            text += f" {dt.year}"
        parts.append(text)
    if d.has_time:
        parts.append(format_time(dt, opts.time_24h))
        key = getattr(dt.tzinfo, "key", None) if dt.tzinfo is not None else None
        if key:
            city = CITY_NAMES.get(key) if opts.lang == "uk" else None
            parts[-1] += f" {city or key.rsplit('/', 1)[-1].replace('_', ' ')}"
    return ", ".join(parts)


def format_time(dt: datetime, time_24h: bool) -> str:
    if time_24h:
        return f"{dt:%H:%M}"
    hour = dt.hour % 12 or 12
    return f"{hour}:{dt:%M}{'am' if dt.hour < 12 else 'pm'}"
