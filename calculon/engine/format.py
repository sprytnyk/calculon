"""Turning values into the text shown in the results column."""

from dataclasses import dataclass
from decimal import ROUND_HALF_EVEN, ROUND_HALF_UP, Decimal
from fractions import Fraction

from . import units as U
from .currency import ZERO_DECIMALS
from .currency import display as currency_display
from .ukrainian import CITY_NAMES
from .values import DateVal, Q, Value

# thousands separator, decimal separator
NUMBER_STYLES = {
    "comma_dot": (",", "."),  # 1,234.56
    "dot_comma": (".", ","),  # 1.234,56
    "space_comma": (" ", ","),  # 1 234,56 (narrow no-break space)
    "space_dot": (" ", "."),  # 1 234.56
}
# Number format used for each UI language when the setting is "auto".
LANGUAGE_NUMBER_STYLES = {"en": "comma_dot", "uk": "space_comma"}


# Month names as they follow a day number: "10 листопада".
MONTHS_UK = (
    "січня", "лютого", "березня", "квітня", "травня", "червня",
    "липня", "серпня", "вересня", "жовтня", "листопада", "грудня",
)  # fmt: skip


@dataclass(frozen=True)
class FormatOptions:
    number_style: str = "comma_dot"
    max_decimals: int = 6
    money_decimals: int = 2
    time_24h: bool = True
    lang: str = "en"  # unit names, month names and where currency symbols go


def format_number(x: Decimal, opts: FormatOptions, decimals: int | None = None) -> str:
    thousands, point = NUMBER_STYLES.get(opts.number_style, NUMBER_STYLES["comma_dot"])
    if not x.is_finite():
        return str(x)
    if x != 0 and abs(x) >= Decimal("1e21"):
        return format_sci(x, opts)
    if decimals is None:
        if x != 0 and abs(x) < Decimal(10) ** -opts.max_decimals:
            return format_sci(x, opts)
        q = x.quantize(Decimal(1).scaleb(-opts.max_decimals), rounding=ROUND_HALF_EVEN)
        text = f"{q:f}"
        if "." in text:
            text = text.rstrip("0").rstrip(".")
    else:
        q = x.quantize(Decimal(1).scaleb(-decimals), rounding=ROUND_HALF_UP)
        text = f"{q:f}"
    if text in ("-0", "-0.00", "-0.0") or (text.startswith("-") and Decimal(text) == 0):
        text = text[1:]
    sign = ""
    if text.startswith("-"):
        sign, text = "-", text[1:]
    whole, _, frac = text.partition(".")
    groups = []
    while len(whole) > 3:
        groups.insert(0, whole[-3:])
        whole = whole[:-3]
    groups.insert(0, whole)
    out = thousands.join(groups)
    if frac:
        out += point + frac
    return sign + out


def format_sci(x: Decimal, opts: FormatOptions) -> str:
    _, point = NUMBER_STYLES.get(opts.number_style, NUMBER_STYLES["comma_dot"])
    text = f"{x:.{min(opts.max_decimals, 10)}e}"
    mant, _, exp = text.partition("e")
    if "." in mant:
        mant = mant.rstrip("0").rstrip(".")
    return f"{mant.replace('.', point)}e{int(exp)}"


def format_value(v: Value, opts: FormatOptions) -> str:
    if isinstance(v, DateVal):
        return format_date(v, opts)
    return format_q(v, opts)


def format_q(q: Q, opts: FormatOptions) -> str:
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
        month = MONTHS_UK[dt.month - 1] if opts.lang == "uk" else f"{dt:%B}"
        text = f"{dt.day} {month}"
        from datetime import datetime

        if dt.year != datetime.now().year:
            text += f" {dt.year}"
        parts.append(text)
    if d.has_time:
        if opts.time_24h:
            parts.append(f"{dt:%H:%M}")
        else:
            hour = dt.hour % 12 or 12
            parts.append(f"{hour}:{dt:%M}{'am' if dt.hour < 12 else 'pm'}")
        key = getattr(dt.tzinfo, "key", None) if dt.tzinfo is not None else None
        if key:
            city = CITY_NAMES.get(key) if opts.lang == "uk" else None
            parts[-1] += f" {city or key.rsplit('/', 1)[-1].replace('_', ' ')}"
    return ", ".join(parts)
