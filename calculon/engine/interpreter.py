"""Parse and evaluate one line.

The parser is a Pratt parser that evaluates as it goes. Words it doesn't know are
treated as plain text and skipped, which lets lines mix prose and maths:
"$19 for breakfast + $22 for the uber" gives $41.
"""

import math
import re
import zoneinfo
from collections.abc import Callable
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timedelta
from decimal import Decimal
from functools import cache
from statistics import median, stdev

from . import ukrainian as UK
from . import units as U
from .currency import KNOWN_CODES, RateTable
from .currency import NAMES as CURRENCY_NAMES
from .lexer import GENERAL_SCALES, SCALES, Tok, tokenize
from .values import (
    ONE,
    ZERO,
    CalcError,
    DateVal,
    Q,
    Value,
    add,
    convert,
    date_diff,
    div,
    modulo,
    mul,
    negate,
    power,
    simplify,
)

KEYWORDS = {
    "of", "on", "off", "in", "into", "to", "as", "cast", "per", "a", "an", "at", "for", "is",
    "what", "plus", "minus", "times", "multiplied", "divided", "by", "mod", "remainder", "x",
    "the", "and", "power", "percent", "percentage", "fraction", "multiplier", "sci",
    "scientific", "hex", "hexadecimal", "binary", "bin", "octal", "oct", "decimal", "dec",
    "today", "now", "time", "tomorrow", "yesterday", "ago", "from", "after", "before",
    "since", "until", "till", "between", "through", "next", "last", "this", "if",
    "total", "sum", "subtotal", "average", "avg", "mean", "median", "count", "stdev",
    "standard", "deviation", "prev", "previous", "ans", "answer", "line", "squared", "cubed",
    "square", "cube", "root", "sq", "cubic", "midpoint", "halfway", "with", "then",
    "hundred", "thousand", "thousands", "million", "millions", "billion", "billions",
    "trillion", "trillions",
}  # fmt: skip
WORD_SCALES = {
    "hundred": Decimal(100),
    "thousand": Decimal(10) ** 3,
    "thousands": Decimal(10) ** 3,
    "million": Decimal(10) ** 6,
    "millions": Decimal(10) ** 6,
    "billion": Decimal(10) ** 9,
    "billions": Decimal(10) ** 9,
    "trillion": Decimal(10) ** 12,
    "trillions": Decimal(10) ** 12,
    # Ukrainian: 5 тис., 2,5 млн, 1 млрд
    "сто": Decimal(100),
    "тис": Decimal(10) ** 3,
    "тисяча": Decimal(10) ** 3,
    "тисячі": Decimal(10) ** 3,
    "тисяч": Decimal(10) ** 3,
    "млн": Decimal(10) ** 6,
    "мільйон": Decimal(10) ** 6,
    "мільйони": Decimal(10) ** 6,
    "мільйонів": Decimal(10) ** 6,
    "млрд": Decimal(10) ** 9,
    "мільярд": Decimal(10) ** 9,
    "мільярди": Decimal(10) ** 9,
    "мільярдів": Decimal(10) ** 9,
}
KEYWORDS |= set(WORD_SCALES)
# Keywords that are skipped as plain text when they don't fit the maths around them.
SOFT = {
    "of", "on", "off", "in", "into", "to", "as", "per", "a", "an", "at", "for", "is", "the",
    "and", "by", "with", "what", "from", "then", "x", "this", "next", "last", "if", "time",
    "line", "since", "until", "till", "between", "through", "after", "before", "ago",
}  # fmt: skip
FUNCTIONS: dict[str, Callable[[float], float]] = {
    "sqrt": math.sqrt,
    "cbrt": lambda v: math.copysign(abs(v) ** (1 / 3), v),
    "abs": abs,
    "ln": math.log,
    "log": math.log10,
    "log10": math.log10,
    "log2": math.log2,
    "exp": math.exp,
    "sin": math.sin,
    "cos": math.cos,
    "tan": math.tan,
    "asin": math.asin,
    "acos": math.acos,
    "atan": math.atan,
    "arcsin": math.asin,
    "arccos": math.acos,
    "arctan": math.atan,
    "sinh": math.sinh,
    "cosh": math.cosh,
    "tanh": math.tanh,
    "fact": lambda v: float(math.factorial(int(v))),
    "factorial": lambda v: float(math.factorial(int(v))),
}
ROUNDERS = {"round", "floor", "ceil", "ceiling"}
TRIG = {"sin", "cos", "tan"}
CONSTANTS = {"pi": Decimal("3.14159265358979323846264338327950288"), "π": None, "e": None}
CONSTANTS["π"] = CONSTANTS["pi"]
CONSTANTS["e"] = Decimal("2.71828182845904523536028747135266250")
MONTHS = {
    m: i + 1
    for i, names in enumerate(
        [
            ("january", "jan"),
            ("february", "feb"),
            ("march", "mar"),
            ("april", "apr"),
            ("may",),
            ("june", "jun"),
            ("july", "jul"),
            ("august", "aug"),
            ("september", "sep", "sept"),
            ("october", "oct"),
            ("november", "nov"),
            ("december", "dec"),
        ]
    )
    for m in names
}
MONTHS |= {
    m: i + 1
    for i, names in enumerate(
        [
            ("січень", "січня"),
            ("лютий", "лютого"),
            ("березень", "березня"),
            ("квітень", "квітня"),
            ("травень", "травня"),
            ("червень", "червня"),
            ("липень", "липня"),
            ("серпень", "серпня"),
            ("вересень", "вересня"),
            ("жовтень", "жовтня"),
            ("листопад", "листопада"),
            ("грудень", "грудня"),
        ]
    )
    for m in names
}
WEEKDAYS = {
    d: i
    for i, names in enumerate(
        [
            ("monday", "mon"),
            ("tuesday", "tue", "tues"),
            ("wednesday", "wed"),
            ("thursday", "thu", "thur", "thurs"),
            ("friday", "fri"),
            ("saturday", "sat"),
            ("sunday", "sun"),
        ]
    )
    for d in names
}
WEEKDAYS |= {
    d: i
    for i, names in enumerate(
        [
            ("понеділок", "понеділка"),
            ("вівторок", "вівторка"),
            ("середа", "середи", "середу"),
            ("четвер", "четверга"),
            ("пʼятниця", "п'ятниця", "пʼятниці", "п'ятниці", "пʼятницю", "п'ятницю"),
            ("субота", "суботи", "суботу"),
            ("неділя", "неділі", "неділю"),
        ]
    )
    for d in names
}
AGGREGATES = {
    "total": "sum",
    "sum": "sum",
    "subtotal": "sum",
    "average": "avg",
    "avg": "avg",
    "mean": "avg",
    "median": "median",
    "count": "count",
    "stdev": "stdev",
}
LIST_SEPARATORS = {",", "and", ";"}

TZ_ALIASES = {
    "utc": "UTC", "gmt": "Etc/GMT", "kyiv": "Europe/Kyiv", "kiev": "Europe/Kyiv",
    "new york": "America/New_York", "nyc": "America/New_York",
    "washington": "America/New_York", "boston": "America/New_York",
    "los angeles": "America/Los_Angeles", "la": "America/Los_Angeles",
    "san francisco": "America/Los_Angeles", "sf": "America/Los_Angeles",
    "seattle": "America/Los_Angeles", "las vegas": "America/Los_Angeles",
    "dallas": "America/Chicago", "houston": "America/Chicago", "austin": "America/Chicago",
    "miami": "America/New_York", "atlanta": "America/New_York",
    "beijing": "Asia/Shanghai", "delhi": "Asia/Kolkata", "new delhi": "Asia/Kolkata",
    "mumbai": "Asia/Kolkata", "bangalore": "Asia/Kolkata", "lviv": "Europe/Kyiv",
    "odesa": "Europe/Kyiv", "kharkiv": "Europe/Kyiv", "munich": "Europe/Berlin",
    "barcelona": "Europe/Madrid", "milan": "Europe/Rome", "krakow": "Europe/Warsaw",
    "est": "America/New_York", "edt": "America/New_York", "cst": "America/Chicago",
    "cdt": "America/Chicago", "mst": "America/Denver", "mdt": "America/Denver",
    "pst": "America/Los_Angeles", "pdt": "America/Los_Angeles", "cet": "Europe/Paris",
    "cest": "Europe/Paris", "eet": "Europe/Kyiv", "eest": "Europe/Kyiv",
    "bst": "Europe/London", "ist": "Asia/Kolkata", "jst": "Asia/Tokyo",
    "aest": "Australia/Sydney", "local": "",
}  # fmt: skip


@cache
def tz_table() -> dict[str, str]:
    table: dict[str, str] = {}
    for key in zoneinfo.available_timezones():
        if "/" not in key or key.startswith(("Etc/", "SystemV/", "US/")):
            continue
        city = key.rsplit("/", 1)[-1].replace("_", " ").lower()
        table.setdefault(city, key)
    table.update(TZ_ALIASES)
    table.update(UK.CITIES)
    return table


@dataclass
class Config:
    number_style: str = "comma_dot"
    date_order: str = "DMY"  # how 01/02/2026 is read
    dollar: str = "USD"
    now: Callable[[], datetime] = datetime.now


@dataclass
class Item:
    """A classified token."""

    kind: str  # num cur unit var kw fn const op date time tag city month weekday noise prev
    key: str  # lowercased text, unit name, currency code, variable key...
    tok: Tok
    end_tok: Tok
    extra: object = None

    @property
    def start(self) -> int:
        return self.tok.start

    @property
    def end(self) -> int:
        return self.end_tok.end


@dataclass
class Context:
    """Everything a line can see: variables, earlier results, rates."""

    rates: RateTable
    config: Config = field(default_factory=Config)
    variables: dict[str, Value] = field(default_factory=dict)
    var_names: dict[str, str] = field(default_factory=dict)  # key -> name as typed
    line_values: list[Value | None] = field(default_factory=list)
    prev: Value | None = None
    block: list[Value] = field(default_factory=list)  # values since the last total/heading
    tags: dict[str, list[Value]] = field(default_factory=dict)
    custom_units: set[str] = field(default_factory=set)

    def set_var(self, name: str, value: Value) -> None:
        key = " ".join(name.lower().split())
        self.variables[key] = value
        self.var_names[key] = name.strip()


class ParseError(Exception):
    pass


def classify(toks: list[Tok], ctx: Context) -> list[Item]:
    items: list[Item] = []
    var_keys = [tuple(k.split()) for k in ctx.variables]
    max_var = max((len(k) for k in var_keys), default=1)
    tz = tz_table()
    i = 0
    while i < len(toks):
        t = toks[i]
        if t.kind != "WORD":
            items.append(_classify_symbol(t, toks, i, ctx))
            i += 1
            continue
        # multi-word variables, longest first
        matched = False
        words = []
        j = i
        while j < len(toks) and toks[j].kind == "WORD" and len(words) < max_var:
            words.append(toks[j].text.lower())
            j += 1
        for size in range(len(words), 0, -1):
            key = tuple(words[:size])
            if key in var_keys:
                items.append(Item("var", " ".join(key), t, toks[i + size - 1]))
                i += size
                matched = True
                break
        if matched:
            continue
        # cities after "in"/"to"/a time/"time"/"now"
        prev = items[-1] if items else None
        if prev and (prev.kind == "time" or prev.key in ("in", "to", "time", "now", "into")):
            found = False
            for size in (3, 2, 1):
                ws = toks[i : i + size]
                if len(ws) < size or any(w.kind != "WORD" for w in ws):
                    continue
                name = " ".join(w.text.lower() for w in ws)
                if name in tz and len(name) > 1:
                    items.append(Item("city", name, t, ws[-1], tz[name]))
                    i += size
                    found = True
                    break
            if found:
                continue
        # two-word units
        if i + 1 < len(toks) and toks[i + 1].kind == "WORD":
            pair = (t.text.lower(), toks[i + 1].text.lower())
            if pair in U.PHRASES:
                items.append(Item("unit", U.PHRASES[pair], t, toks[i + 1]))
                i += 2
                continue
        items.append(_classify_word(t, toks, i, items))
        i += 1
    items = UK.apply(items)
    _mark_custom_units(items, ctx)
    _mark_comment_parens(items)
    return items


def _mark_custom_units(items: list[Item], ctx: Context) -> None:
    """A plain word after "/" or "per" becomes a unit for the rest of the sheet."""
    for i, it in enumerate(items):
        if it.kind != "noise" or not it.tok.text.isalpha() or len(it.tok.text) < 2 or not i:
            continue
        prev = items[i - 1]
        if (prev.kind == "op" and prev.key == "/") or (prev.kind == "kw" and prev.key == "per"):
            ctx.custom_units.add(U.singular(it.tok.text))
    if not ctx.custom_units:
        return
    for it in items:
        if it.kind == "noise" and it.tok.text.isalpha():
            name = U.singular(it.tok.text)
            if name in ctx.custom_units:
                it.kind = "unit"
                it.key = U.CUSTOM + name


def _classify_symbol(t: Tok, toks: list[Tok], i: int, ctx: Context) -> Item:
    if t.kind == "NUM":
        return Item("num", t.text, t, t)
    if t.kind == "CUR":
        code = ctx.config.dollar if t.value == "$" else str(t.value)
        return Item("cur", code, t, t)
    if t.kind == "DATE":
        return Item("date", t.text, t, t)
    if t.kind == "TIME":
        return Item("time", t.text, t, t)
    if t.kind == "TAG":
        return Item("tag", t.text[1:].lower(), t, t)
    return Item("op", t.text, t, t)


def _classify_word(t: Tok, toks: list[Tok], i: int, items: list[Item]) -> Item:
    w = t.text
    low = w.lower()
    prev_tok = toks[i - 1] if i else None
    # ordinal suffix: 1st, 2nd, 23rd
    ordinal = low in ("st", "nd", "rd", "th")
    if ordinal and prev_tok and prev_tok.kind == "NUM" and prev_tok.end == t.start:
        return Item("noise", low, t, t)
    m = re.fullmatch(r"(?:line|рядок)(\d+)", low)
    if m:
        return Item("lineref", m.group(1), t, t)
    if low in AGGREGATES or low in KEYWORDS:
        return Item("kw", low, t, t)
    if low in UK.WORDS:
        return Item("kw", UK.WORDS[low], t, t)
    if low in UK.FUNCTIONS:
        return Item("fn", UK.FUNCTIONS[low], t, t)
    if low in UK.CONSTANTS:
        return Item("const", UK.CONSTANTS[low], t, t)
    if low in FUNCTIONS or low in ROUNDERS:
        return Item("fn", low, t, t)
    if low in CONSTANTS and (low != "e" or w == "e"):
        return Item("const", low, t, t)
    unit = U.lookup(w)
    if unit:
        return Item("unit", unit, t, t)
    if w.isupper() and len(w) == 3 and w in KNOWN_CODES:
        return Item("cur", w, t, t)
    prev_item = items[-1] if items else None
    if (
        len(w) == 3
        and w.upper() in KNOWN_CODES
        and prev_item is not None
        and (prev_item.kind == "num" or prev_item.key in ("in", "to", "as", "into"))
    ):
        return Item("cur", w.upper(), t, t)
    if low in CURRENCY_NAMES:
        return Item("cur", CURRENCY_NAMES[low], t, t)
    if low in MONTHS:
        return Item("month", low, t, t)
    if low in WEEKDAYS:
        return Item("weekday", low, t, t)
    return Item("noise", low, t, t)


def _mark_comment_parens(items: list[Item]) -> None:
    """(for iPhone 16) is a comment: parentheses holding plain words are ignored."""
    stack: list[int] = []
    for idx, it in enumerate(items):
        if it.kind == "op" and it.key == "(":
            stack.append(idx)
        elif it.kind == "op" and it.key == ")" and stack:
            start = stack.pop()
            inner = items[start + 1 : idx]
            if any(x.kind == "noise" for x in inner):
                for x in items[start : idx + 1]:
                    x.kind = "noise"


ADD_OPS = {"+": 1, "plus": 1, "-": -1, "−": -1, "–": -1, "minus": -1}
MUL_OPS = {"*", "×", "·", "times", "x"}
DIV_OPS = {"/", "÷"}
CONVERT_WORDS = {"in", "to", "into", "as"}


class Parser:
    def __init__(self, items: list[Item], ctx: Context):
        self.items = items
        self.pos = 0
        self.ctx = ctx
        self.rates = ctx.rates
        self.plain: list[int] = []  # positions of soft keywords read as plain text

    def rewind(self, pos: int) -> None:
        self.pos = pos
        self.plain = [i for i in self.plain if i < pos]

    def skip_plain(self) -> None:
        self.plain.append(self.pos)
        self.pos += 1

    # helpers
    def peek(self, offset: int = 0) -> Item | None:
        p = self.pos + offset
        return self.items[p] if p < len(self.items) else None

    def at(self, *keys: str, offset: int = 0) -> bool:
        it = self.peek(offset)
        return it is not None and it.kind in ("kw", "op") and it.key in keys

    def take(self, *keys: str) -> bool:
        if self.at(*keys):
            self.pos += 1
            return True
        return False

    def expect(self, *keys: str) -> None:
        if not self.take(*keys):
            raise ParseError(f"expected {keys}")

    def done(self) -> bool:
        return self.pos >= len(self.items)

    # entry
    def statement(self) -> Value:
        for pattern in PATTERNS:
            self.rewind(0)
            try:
                value = pattern(self)
            except ParseError, CalcError, ArithmeticError, ValueError, OverflowError:
                continue
            if value is not None and self.done():
                return value
        self.rewind(0)
        value = self.expr(0, frozenset())
        if not self.done():
            raise ParseError("unexpected text")
        return value

    # Pratt core
    def expr(self, min_bp: int, stops: frozenset[str]) -> Value:
        left = self.prefix(stops)
        while True:
            it = self.peek()
            if it is None:
                break
            if it.kind in ("kw", "op") and it.key in stops:
                break
            save = self.pos
            try:
                result = self.infix(left, it, min_bp, stops)
            except ParseError:
                self.rewind(save)
                if it.kind == "kw" and it.key in SOFT:
                    self.skip_plain()
                    continue
                raise
            if result is None:
                self.rewind(save)
                if it.kind == "kw" and it.key in SOFT and min_bp == 0:
                    self.skip_plain()
                    continue
                break
            left = result
        return left

    def infix(self, left: Value, it: Item, min_bp: int, stops: frozenset[str]) -> Value | None:
        key = it.key
        kind = it.kind
        r = self.rates
        if kind in ("kw", "op"):
            if key in ("^", "**") or (key == "to" and self.at("the", offset=1)):
                if min_bp > 30:
                    return None
                self.pos += 1
                if key == "to":
                    self.expect("the")
                    self.expect("power")
                    self.expect("of")
                right = self.expr(30, stops)
                return power(left, right)
            if key in CONVERT_WORDS or key == "cast":
                if min_bp > 5:
                    return None
                self.pos += 1
                return self.conversion(left, key, stops)
            if key in ("for", "at", "@"):
                if min_bp > 8:
                    return None
                self.pos += 1
                right = self.expr(9, stops)
                return self.rate_apply(left, right, key)
            if key in ADD_OPS:
                if min_bp > 10:
                    return None
                self.pos += 1
                right = self.expr(11, stops)
                return add(left, right, r, ADD_OPS[key])
            if key in MUL_OPS or key in DIV_OPS or key in ("multiplied", "divided", "mod", "per"):
                if min_bp > 20:
                    return None
                self.pos += 1
                if key in ("multiplied", "divided"):
                    self.expect("by")
                if key == "per":
                    unit = self.unit_expr()
                    if unit is None:
                        raise ParseError("per what")
                    return div(left, Q(ONE, unit), r)
                if key in DIV_OPS and not isinstance(left, DateVal):
                    unit = self.unit_expr(allow_currency_code=True)
                    if unit is not None and not self._starts_value():
                        return div(left, Q(ONE, unit), r)
                right = self.expr(21, stops)
                if key == "mod":
                    return modulo(left, right)
                if key in MUL_OPS or key == "multiplied":
                    return mul(left, right, r)
                return div(left, right, r)
            if key == "%" and self._percent_is_mod():
                if min_bp > 20:
                    return None
                self.pos += 1
                return modulo(left, self.expr(21, stops))
            if key in ("a", "an") and isinstance(left, Q):
                # $24 a day -> $24/day
                if min_bp > 20:
                    return None
                self.pos += 1
                unit = self.unit_expr()
                if unit is None:
                    raise ParseError("a what")
                return div(left, Q(ONE, unit), r)
            if key == "of":
                if min_bp > 20:
                    return None
                self.pos += 1
                right = self.expr(21, stops)
                return mul(left, right, r)
            if key in ("on", "off"):
                if min_bp > 20 or not (isinstance(left, Q) and left.pct):
                    return None
                self.pos += 1
                right = self.expr(21, stops)
                return add(right, left, r, 1 if key == "on" else -1)
            if key == "(":
                if min_bp > 20:
                    return None
                return mul(left, self.expr(21, stops), r)
            if key in ("squared", "cubed"):
                self.pos += 1
                return power(left, Q(Decimal(2 if key == "squared" else 3)))
            if key == "!" and isinstance(left, Q):
                self.pos += 1
                return _apply_fn("fact", left)
            if key == "ago":
                self.pos += 1
                return add(self.now_val(), left, r, -1)
            if key in ("after", "before") and isinstance(left, Q):
                self.pos += 1
                base = self.expr(6, stops)
                if not isinstance(base, DateVal):
                    raise ParseError("after what")
                return add(base, left, r, 1 if key == "after" else -1)
            if key == "from" and isinstance(left, Q):
                self.pos += 1
                if self.take("now"):
                    return add(self.now_val(), left, r)
                base = self.expr(6, stops)
                if not isinstance(base, DateVal):
                    raise ParseError("from what")
                return add(base, left, r)
            if key == "through" and isinstance(left, DateVal):
                self.pos += 1
                end = self.expr(6, stops)
                if not isinstance(end, DateVal):
                    raise ParseError("through what")
                return date_diff(left, DateVal(end.dt + timedelta(days=1), end.has_date))
            if key in WORD_SCALES and isinstance(left, Q):
                self.pos += 1
                return replace(left, mag=left.mag * WORD_SCALES[key])
            return None
        if kind == "num" and isinstance(left, Q) and left.units:
            # 5 hours 30 minutes, 1 km 200 m
            save = self.pos
            try:
                right = self.prefix(stops)
            except ParseError:
                self.rewind(save)
                return None
            if (
                isinstance(right, Q)
                and right.units
                and U.dims_of(right.units) == U.dims_of(left.units)
            ):
                return add(left, right, r)
            self.rewind(save)
            return None
        if kind == "city" and isinstance(left, DateVal):
            self.pos += 1
            zone = zoneinfo.ZoneInfo(str(it.extra)) if it.extra else None
            return DateVal(left.dt.replace(tzinfo=zone), left.has_date, left.has_time)
        return None

    def _starts_value(self) -> bool:
        it = self.peek()
        return it is not None and it.kind in ("num", "cur", "var", "const", "date", "time")

    def _percent_is_mod(self) -> bool:
        it = self.peek()
        prev = self.items[self.pos - 1] if self.pos else None
        if it is None or prev is None:
            return False
        nxt = self.peek(1)
        spaced = prev.end < it.start
        return spaced and nxt is not None and nxt.kind in ("num", "var", "const")

    # prefix / primary
    def prefix(self, stops: frozenset[str]) -> Value:
        it = self.peek()
        if it is None:
            raise ParseError("expected a value")
        kind, key = it.kind, it.key
        if kind in ("kw", "op") and key in stops:
            raise ParseError("expected a value")
        if kind == "op" and key in ("-", "−", "–"):
            self.pos += 1
            return negate(self.expr(25, stops))
        if kind == "op" and key == "+":
            self.pos += 1
            return self.expr(25, stops)
        if kind == "kw" and key == "minus":
            self.pos += 1
            return negate(self.expr(25, stops))
        if kind == "op" and key == "(":
            self.pos += 1
            value = self.expr(0, frozenset())
            self.expect(")")
            return self.postfix(value)
        if kind == "num":
            return self.postfix(self.number())
        if kind == "cur":
            return self.money()
        if kind == "var":
            self.pos += 1
            return self.postfix(self.ctx.variables[key])
        if kind == "const":
            self.pos += 1
            return self.postfix(Q(CONSTANTS[key]))  # type: ignore[arg-type]
        if kind == "lineref":
            self.pos += 1
            return self.postfix(self.line_ref(Decimal(key)))
        if kind == "fn":
            return self.postfix(self.function())
        if kind == "date":
            self.pos += 1
            return self.postfix(self.numeric_date(it.tok))
        if kind == "time":
            self.pos += 1
            h, m, s = it.tok.value  # type: ignore[misc]
            now = self.ctx.config.now()
            return DateVal(now.replace(hour=h, minute=m, second=s, microsecond=0), False, True)
        if kind == "month":
            return self.postfix(self.month_date())
        if kind == "weekday":
            return self.weekday_date(0)
        if kind == "unit":
            return self.unit_lead(stops)
        if kind == "kw":
            return self.keyword(key, stops)
        if kind == "op" and key == "@":
            raise ParseError("unexpected @")
        raise ParseError(f"unexpected {it.tok.text}")

    def keyword(self, key: str, stops: frozenset[str]) -> Value:
        cfg = self.ctx.config
        if key in ("today", "now", "tomorrow", "yesterday", "time"):
            self.pos += 1
            now = cfg.now().replace(microsecond=0)
            if key == "now":
                return self.postfix(DateVal(now, True, True))
            if key == "time":
                return self.postfix(DateVal(now, False, True))
            day = datetime(now.year, now.month, now.day)
            day += timedelta(days={"today": 0, "tomorrow": 1, "yesterday": -1}[key])
            return self.postfix(DateVal(day))
        if key in ("next", "last", "this") and self.peek(1) and self.peek(1).kind == "weekday":  # type: ignore[union-attr]
            self.pos += 1
            return self.weekday_date({"next": 1, "last": -1, "this": 0}[key])
        if key in ("prev", "previous", "ans", "answer"):
            self.pos += 1
            if self.ctx.prev is None:
                raise ParseError("no previous answer")
            return self.postfix(self.ctx.prev)
        if key == "line" and self.peek(1) and self.peek(1).kind == "num":  # type: ignore[union-attr]
            self.pos += 1
            n = self.peek()
            assert n
            self.pos += 1
            return self.postfix(self.line_ref(n.tok.value))  # type: ignore[arg-type]
        if key in AGGREGATES or (key == "standard" and self.at("deviation", offset=1)):
            return self.aggregate()
        if key == "remainder":
            self.pos += 1
            self.expect("of")
            a = self.expr(0, stops | {"divided", "by"})
            self.take("divided")  # "остача від ділення 21 на 5" has no "divided"
            self.expect("by")
            return modulo(a, self.expr(21, stops))
        if key in ("square", "cube") and self.at("root", offset=1):
            self.pos += 2
            self.take("of")
            arg = self.expr(25, stops)
            return _apply_fn("sqrt" if key == "square" else "cbrt", arg)
        if key in ("midpoint", "halfway"):
            self.pos += 1
            self.expect("between")
            a = self.expr(0, stops | {"and"})
            self.expect("and")
            b = self.expr(0, stops)
            if isinstance(a, DateVal) and isinstance(b, DateVal):
                return DateVal(a.dt + (b.dt - a.dt) / 2, a.has_date, a.has_time or b.has_time)
            return div(add(a, b, self.rates), Q(Decimal(2)), self.rates)
        if key in ("a", "an"):
            self.pos += 1
            unit = self.unit_expr()
            if unit is None:
                # "a" as plain text
                return self.expr(25, stops)
            return self.postfix(Q(ONE, unit))
        if key in SOFT:
            self.skip_plain()  # plain text at the start of an expression
            return self.prefix(stops)
        raise ParseError(f"unexpected {key}")

    def number(self) -> Q:
        it = self.peek()
        assert it and it.kind == "num"
        self.pos += 1
        tok = it.tok
        value: Decimal = tok.value  # type: ignore[assignment]
        q = Q(value, fmt=tok.fmt)
        if tok.scale:
            prev = self.items[self.pos - 2] if self.pos >= 2 else None
            nxt = self.peek()
            money = (prev is not None and prev.kind == "cur") or (
                nxt is not None and nxt.kind == "cur"
            )
            if money or tok.scale in GENERAL_SCALES:
                q = Q(value * SCALES[tok.scale])
            else:
                unit = U.lookup(tok.scale)
                if unit is None:
                    raise ParseError("unknown suffix")
                q = Q(value, ((unit, 1),))
        # 12 June [2026]
        nxt = self.peek()
        if nxt is not None and nxt.kind == "month" and not tok.scale and value <= 31:
            self.pos += 1
            month = MONTHS[nxt.key]
            year = self._year()
            return self._make_date(year, month, int(value))  # type: ignore[return-value]
        return q

    def _year(self) -> int | None:
        save = self.pos
        self.take(",")
        it = self.peek()
        if it is not None and it.kind == "num" and not it.tok.scale:
            v = it.tok.value
            if isinstance(v, Decimal) and 1000 <= v <= 2999 and v == int(v):
                self.pos += 1
                return int(v)
        self.rewind(save)
        return None

    def _make_date(self, year: int | None, month: int, day: int) -> DateVal:
        now = self.ctx.config.now()
        try:
            return DateVal(datetime(year or now.year, month, day))
        except ValueError as exc:
            raise CalcError("no such date") from exc

    def month_date(self) -> DateVal:
        it = self.peek()
        assert it
        self.pos += 1
        month = MONTHS[it.key]
        nxt = self.peek()
        if nxt is not None and nxt.kind == "num" and not nxt.tok.scale:
            v = nxt.tok.value
            if isinstance(v, Decimal) and 1 <= v <= 31 and v == int(v):
                self.pos += 1
                return self._make_date(self._year(), month, int(v))
            if isinstance(v, Decimal) and 1000 <= v <= 2999:
                self.pos += 1
                return self._make_date(int(v), month, 1)
        return self._make_date(None, month, 1)

    def weekday_date(self, direction: int) -> DateVal:
        it = self.peek()
        assert it
        self.pos += 1
        target = WEEKDAYS[it.key]
        now = self.ctx.config.now()
        today = datetime(now.year, now.month, now.day)
        diff = (target - today.weekday()) % 7
        if direction < 0:
            diff = diff - 7 if diff else -7
        elif direction > 0 and diff == 0:
            diff = 7
        return DateVal(today + timedelta(days=diff))

    def numeric_date(self, tok: Tok) -> DateVal:
        a, b, c, order = tok.value  # type: ignore[misc]
        if order == "ymd":
            return self._make_date(a, b, c)
        if self.ctx.config.date_order == "MDY":
            return self._make_date(c, a, b)
        return self._make_date(c, b, a)

    def money(self) -> Q:
        it = self.peek()
        assert it
        self.pos += 1
        code = it.key
        nxt = self.peek()
        if nxt is not None and nxt.kind == "op" and nxt.key == "-":
            self.pos += 1
            inner = negate(self.number_only())
        else:
            inner = self.number_only()
        q = Q(inner.mag, ((U.CUR + code, 1),))
        return self.postfix(q)  # type: ignore[return-value]

    def number_only(self) -> Q:
        it = self.peek()
        if it is None:
            raise ParseError("expected a number")
        if it.kind == "num":
            q = self.number()
            if not isinstance(q, Q) or q.units:
                raise ParseError("expected a number")
            # word scales: $3 million
            nxt = self.peek()
            if nxt is not None and nxt.kind == "kw" and nxt.key in WORD_SCALES:
                self.pos += 1
                q = replace(q, mag=q.mag * WORD_SCALES[nxt.key])
            return q
        if it.kind == "var":
            self.pos += 1
            v = self.ctx.variables[it.key]
            if isinstance(v, Q) and v.unitless and not v.pct:
                return v
        if it.kind == "op" and it.key == "(":
            self.pos += 1
            v = self.expr(0, frozenset())
            self.expect(")")
            if isinstance(v, Q) and v.unitless:
                return v
        raise ParseError("expected a number")

    def postfix(self, value: Value) -> Value:
        """Things that stick to a value: %, units, currency codes, scale words, a date's time."""
        if isinstance(value, DateVal):
            return self._date_time(value)
        while isinstance(value, Q):
            it = self.peek()
            if it is None:
                break
            if it.kind == "op" and it.key == "%" and not value.pct and not self._percent_is_mod():
                self.pos += 1
                value = Q(value.mag / 100, pct=True)
                continue
            if it.kind == "kw" and it.key in ("percent",) and not value.pct:
                self.pos += 1
                value = Q(value.mag / 100, pct=True)
                continue
            if it.kind == "kw" and it.key in WORD_SCALES and value.unitless:
                self.pos += 1
                value = replace(value, mag=value.mag * WORD_SCALES[it.key])
                continue
            if value.unitless and not value.pct and it.kind in ("unit", "cur", "kw"):
                unit = self.unit_expr(allow_currency_code=True, attach=True)
                if unit is not None:
                    value = Q(value.mag, unit, fmt=None)
                    continue
            break
        return value

    def _date_time(self, value: DateVal) -> DateVal:
        """A time right after a date joins it: 11.11.2026 15:00, Nov 11 at 3pm, 12 Nov, 17:00."""
        if not value.has_date or value.has_time:
            return value
        offset = 1 if self.at("at", "@", ",") else 0
        it = self.peek(offset)
        if it is None or it.kind != "time":
            return value
        self.pos += offset + 1
        h, m, s = it.tok.value  # type: ignore[misc]
        return DateVal(value.dt.replace(hour=h, minute=m, second=s), True, True)

    def unit_expr(self, allow_currency_code: bool = False, attach: bool = False) -> U.Units | None:
        """Parse 'km', 'km/h', 'm²', 'sq ft', '€/month', 'USD'. None if no unit here."""
        save = self.pos
        units: list[tuple[str, int]] = []
        first = self._unit_atom(allow_currency_code or attach)
        if first is None:
            self.rewind(save)
            return None
        units.extend(first)
        while True:
            it = self.peek()
            if it is None:
                break
            if it.kind == "op" and it.key == "/" or it.kind == "kw" and it.key == "per":
                save2 = self.pos
                self.pos += 1
                atom = self._unit_atom(True)
                if atom is None:
                    self.rewind(save2)
                    break
                units.extend((a, -p) for a, p in atom)
                continue
            if it.kind == "op" and it.key in ("^", "**"):
                nxt = self.peek(1)
                v = nxt.tok.value if nxt is not None and nxt.kind == "num" else None
                if isinstance(v, Decimal) and v == v.to_integral_value() and abs(v) <= 12:
                    self.pos += 2
                    a, p = units[-1]
                    units[-1] = (a, p * int(nxt.tok.value))  # type: ignore[arg-type]
                    continue
            break
        return U.normalize(tuple(units))

    def _unit_atom(self, allow_currency: bool) -> list[tuple[str, int]] | None:
        it = self.peek()
        if it is None:
            return None
        power_ = 1
        if it.kind == "kw" and it.key in ("sq", "square", "cubic", "cube"):
            nxt = self.peek(1)
            if nxt is None or nxt.kind != "unit":
                return None
            power_ = 2 if it.key in ("sq", "square") else 3
            self.pos += 1
            it = nxt
        if it.kind == "unit":
            self.pos += 1
            name, p = U.split_power(it.key)
            return U.expand(name, p * power_)
        if it.kind == "cur" and allow_currency and it.tok.kind == "WORD":
            self.pos += 1
            return [(U.CUR + it.key, 1)]
        if it.kind == "cur" and allow_currency and it.tok.kind == "CUR":
            # "in €", "€/month" in a target
            nxt = self.peek(1)
            if nxt is None or nxt.kind != "num":
                self.pos += 1
                return [(U.CUR + it.key, 1)]
        if it.kind == "noise" and allow_currency:
            code = it.tok.text.upper()
            if len(code) == 3 and (code in KNOWN_CODES or self.rates.has(code)):
                self.pos += 1
                return [(U.CUR + code, 1)]
        return None

    def unit_lead(self, stops: frozenset[str]) -> Value:
        """A line starting with a unit: 'days since March 1', 'meters in 10 km', 'km m'."""
        unit = self.unit_expr()
        if unit is None:
            raise ParseError("unit")
        if self.take("since"):
            when = self.expr(6, stops)
            return self._diff_in(when, self.now_or_today(when), unit)
        if self.take("until", "till"):
            when = self.expr(6, stops)
            return self._diff_in(self.now_or_today(when), when, unit)
        if self.take("between"):
            a = self.expr(0, stops | {"and"})
            self.expect("and")
            b = self.expr(0, stops)
            return self._diff_in(a, b, unit)
        if self.take("in"):
            value = self.expr(6, stops)
            return self._convert_to(value, unit)
        if self.peek() is not None and self.peek().kind == "unit":  # type: ignore[union-attr]
            other = self.unit_expr()
            assert other is not None
            return convert(Q(ONE, unit), other, self.rates)
        raise ParseError("a unit on its own")

    def now_or_today(self, other: Value) -> DateVal:
        now = self.ctx.config.now().replace(microsecond=0)
        if isinstance(other, DateVal) and not other.has_time:
            return DateVal(datetime(now.year, now.month, now.day))
        return DateVal(now, True, True)

    def now_val(self) -> DateVal:
        return DateVal(self.ctx.config.now().replace(microsecond=0), True, False)

    def _diff_in(self, a: Value, b: Value, unit: U.Units) -> Q:
        if not isinstance(a, DateVal) or not isinstance(b, DateVal):
            raise ParseError("expected dates")
        return self._convert_to(date_diff(a, b), unit)  # type: ignore[return-value]

    def _convert_to(self, value: Value, unit: U.Units) -> Value:
        if isinstance(value, DateVal):
            raise CalcError("can't convert a date to a unit")
        return convert(replace(value, parts=None, fmt=None), unit, self.rates)

    def line_ref(self, n: Decimal) -> Value:
        lines = self.ctx.line_values
        # compare before int(): int(1e999999) takes a minute
        if n != n.to_integral_value() or not 1 <= n <= len(lines) or lines[int(n) - 1] is None:
            raise ParseError("no such line")
        return lines[int(n) - 1]  # type: ignore[return-value]

    def function(self) -> Value:
        it = self.peek()
        assert it
        self.pos += 1
        name = it.key
        args: list[Value]
        if self.take("("):
            # ";" also separates arguments, for 1,5 style decimals: round(2,345; 2)
            stops = frozenset({",", ";"})
            args = [self.expr(0, stops)]
            while self.take(",") or self.take(";"):
                args.append(self.expr(0, stops))
            self.expect(")")
        else:
            self.take("of")
            args = [self.expr(25, frozenset())]
        if name in ROUNDERS:
            return _round(name, args)
        if len(args) != 1:
            raise ParseError("one argument expected")
        return _apply_fn(name, args[0])

    def aggregate(self) -> Value:
        it = self.peek()
        assert it
        self.pos += 1
        key = it.key
        if key == "standard":
            self.expect("deviation")
            key = "stdev"
        kind = AGGREGATES[key]
        values: list[Value]
        if self.take("of"):
            nxt = self.peek()
            if nxt is not None and nxt.kind == "tag":
                self.pos += 1
                values = list(self.ctx.tags.get(nxt.key, []))
            else:
                values = [self.expr(0, frozenset(LIST_SEPARATORS))]
                while self.take(*LIST_SEPARATORS):
                    values.append(self.expr(0, frozenset(LIST_SEPARATORS)))
                return aggregate(kind, values, self.rates, lines=False)
        else:
            values = list(self.ctx.block)
        return aggregate(kind, values, self.rates)

    def rate_apply(self, left: Value, right: Value, key: str) -> Value:
        """'30 hours at $30/hour' multiplies; '$500 at $20/hour' divides."""
        if not isinstance(left, Q) or not isinstance(right, Q):
            raise ParseError("rates need quantities")
        if not any(p < 0 for _, p in left.units + right.units):
            raise ParseError("not a rate")
        product = mul(left, right, self.rates)
        if key != "for" and any(p < 0 for _, p in right.units):
            numerator = tuple((a, p) for a, p in right.units if p > 0)
            if numerator and U.dims_of(numerator) == U.dims_of(left.units):
                return div(left, right, self.rates)
        if any(p < 0 for _, p in product.units) and key == "for":
            raise ParseError("rate doesn't cancel")
        return product

    def conversion(self, left: Value, word: str, stops: frozenset[str]) -> Value:
        r = self.rates
        if word == "cast":
            unit = self.unit_expr(allow_currency_code=True)
            if unit is None or not isinstance(left, Q):
                raise ParseError("cast to what")
            return Q(left.mag, unit)
        # number formats and percent
        if isinstance(left, Q):
            fmt_target = self._format_target()
            if fmt_target is not None:
                return _apply_format(left, fmt_target)
        it = self.peek()
        if it is None:
            raise ParseError("convert to what")
        # time zones
        if it.kind == "city":
            if not isinstance(left, DateVal):
                raise ParseError("only times move between time zones")
            self.pos += 1
            zone = zoneinfo.ZoneInfo(str(it.extra)) if it.extra else None
            dt = left.dt if left.dt.tzinfo else left.dt.astimezone()
            moved = dt.astimezone(zone) if zone else dt.astimezone().replace(tzinfo=None)
            return DateVal(moved, left.has_date, True)
        # "/ month", "per year": change a rate's time base
        if it.kind == "op" and it.key == "/" or (it.kind == "kw" and it.key == "per"):
            self.pos += 1
            unit = self.unit_expr(allow_currency_code=True)
            if unit is None or not isinstance(left, Q):
                raise ParseError("per what")
            return _rebase_rate(left, unit, r)
        unit = self.unit_expr(allow_currency_code=True)
        if unit is not None:
            if isinstance(left, DateVal):
                raise CalcError("can't convert a date to a unit")
            # custom exchange rate: 50 EUR in USD at 1.05 USD/EUR
            if self.at("at", "@"):
                self.pos += 1
                rate = self.expr(9, stops)
                return _custom_rate(left, unit, rate, r)
            if not left.units and not left.pct:
                return Q(left.mag, unit)
            return self._convert_to(left, unit)
        # "March 3 to May 30": a date range
        if word == "to" and isinstance(left, DateVal):
            end = self.expr(6, stops)
            if isinstance(end, DateVal):
                return date_diff(left, end)
        raise ParseError("convert to what")

    def _format_target(self) -> str | None:
        it = self.peek()
        if it is None:
            return None
        key = it.key
        if it.kind == "op" and key == "%":
            self.pos += 1
            return "pct"
        if it.kind != "kw":
            return None
        if key in ("a", "an") and self.at("%", offset=1):
            self.pos += 2
            return "pct"
        mapping = {
            "percent": "pct",
            "percentage": "pct",
            "fraction": "fraction",
            "multiplier": "x",
            "x": "x",
            "sci": "sci",
            "scientific": "sci",
            "hex": "hex",
            "hexadecimal": "hex",
            "binary": "bin",
            "bin": "bin",
            "octal": "oct",
            "oct": "oct",
            "decimal": "dec",
            "dec": "dec",
        }
        if key in mapping:
            self.pos += 1
            return mapping[key]
        return None


def _apply_format(q: Q, target: str) -> Q:
    if target == "pct":
        return Q(q.mag, pct=True) if not q.pct else q
    if target == "dec":
        return Q(q.mag, q.units)
    if target == "x":
        return Q(q.mag, fmt="x")
    return Q(q.mag, q.units, fmt=target)


def _rebase_rate(q: Q, per: U.Units, rates: RateTable) -> Q:
    """$30/day as /month -> $912.5/month."""
    num = tuple((a, p) for a, p in q.units if p > 0)
    if not any(p < 0 for _, p in q.units):
        raise CalcError("not a rate")
    target = num + tuple((a, -p) for a, p in per)
    return convert(q, U.normalize(target), rates)


def _custom_rate(value: Q, target: U.Units, rate: Value, rates: RateTable) -> Q:
    if not isinstance(rate, Q):
        raise CalcError("rate must be a number")
    if rate.unitless:
        return Q(value.mag * rate.mag, target)
    out = mul(value, rate, RateTable())  # empty table: no hidden conversions
    if out.units != target:
        out = div(value, rate, RateTable())
    if U.normalize(out.units) != U.normalize(target):
        raise CalcError("rate doesn't match")
    return out


def _apply_fn(name: str, arg: Value) -> Q:
    if not isinstance(arg, Q):
        raise CalcError("functions need numbers")
    x = arg
    if name in TRIG and x.units:
        if x.units == (("degree", 1),):
            v = math.radians(float(x.mag))
        elif x.units == (("radian", 1),):
            v = float(x.mag)
        else:
            raise CalcError("angle expected")
    else:
        if x.units and name not in ("abs", "sqrt", "cbrt"):
            raise CalcError("plain number expected")
        v = float(x.mag)
    if name in ("sqrt", "cbrt") and x.units:
        root = 2 if name == "sqrt" else 3
        if any(p % root for _, p in x.units):
            raise CalcError("can't take that root of these units")
        units = tuple((a, p // root) for a, p in x.units)
        return Q(_dec(FUNCTIONS[name](v)), units)
    if name == "abs":
        return Q(abs(x.mag), x.units, pct=x.pct)
    if name in ("fact", "factorial") and (v < 0 or v > 1000 or v != int(v)):
        raise CalcError("factorial needs a whole number up to 1000")
    if name in ("fact", "factorial"):
        return Q(Decimal(math.factorial(int(v))))
    result = FUNCTIONS[name](v)
    if name in ("asin", "acos", "atan", "arcsin", "arccos", "arctan"):
        return Q(_dec(result))
    return Q(_dec(result))


def _dec(f: float) -> Decimal:
    if math.isnan(f) or math.isinf(f):
        raise CalcError("result is not a number")
    d = Decimal(f"{f:.15g}")
    return d


def _round(name: str, args: list[Value]) -> Q:
    x = args[0]
    if not isinstance(x, Q):
        raise CalcError("functions need numbers")
    places = 0
    if len(args) > 1:
        p = args[1]
        if not isinstance(p, Q) or not p.unitless:
            raise CalcError("places must be a number")
        if not -20 <= p.mag <= 20:
            raise CalcError("places must be between -20 and 20")
        places = int(p.mag)
    mag = x.mag * 100 if x.pct else x.mag
    quantum = Decimal(1).scaleb(-places)
    rounding = {"round": "ROUND_HALF_UP", "floor": "ROUND_FLOOR"}.get(name, "ROUND_CEILING")
    out = mag.quantize(quantum, rounding=rounding)
    if x.pct:
        out = out / 100
    return Q(out, x.units, pct=x.pct)


def aggregate(kind: str, values: list[Value], rates: RateTable, lines: bool = True) -> Q:
    """Sum, average... of values.

    lines=True (totals of lines above, tags, the sheet total): only the kind of unit
    used most is counted (money, usually), and plain numbers are left out when any
    value has a unit. The result is in the last unit of that kind ("last used wins").
    """
    qs = [v for v in values if isinstance(v, Q) and not v.pct]
    if kind == "count":
        return Q(Decimal(len(values)))
    if not qs:
        if kind == "sum":
            return Q(ZERO)
        raise CalcError("nothing to average")
    with_units = [q for q in qs if q.units]
    if lines and with_units:
        groups: dict[frozenset, list[tuple[int, Q]]] = {}
        for n, q in enumerate(with_units):
            groups.setdefault(frozenset(U.dims_of(q.units).items()), []).append((n, q))
        best = max(groups.values(), key=lambda g: (len(g), g[-1][0]))
        qs = [q for _, q in best]
    target = next((q.units for q in reversed(qs) if q.units), ())
    mags: list[Decimal] = []
    for q in qs:
        if q.units and q.units != target:
            try:
                q = convert(q, target, rates)
            except CalcError:
                continue
        mags.append(q.mag)
    if not mags:
        return Q(ZERO, target)
    if kind == "sum":
        return Q(sum(mags, ZERO), target)
    if kind == "avg":
        return Q(sum(mags, ZERO) / len(mags), target)
    if kind == "median":
        return Q(Decimal(median(mags)), target)
    if kind == "stdev":
        if len(mags) < 2:
            raise CalcError("need at least two values")
        return Q(_dec(stdev(float(m) for m in mags)), target)
    raise CalcError(kind)


def _hole(p: Parser, *stop: str) -> Value:
    return p.expr(0, frozenset(stop))


def _q(v: Value) -> Q:
    if not isinstance(v, Q):
        raise ParseError("number expected")
    return v


def _pct_of(v: Value) -> Decimal:
    q = _q(v)
    if q.pct:
        return q.mag
    if q.unitless:
        return q.mag
    raise ParseError("percent expected")


def _ratio(a: Value, b: Value, rates: RateTable) -> Decimal:
    qa, qb = _q(a), _q(b)
    if qa.units and qb.units and qa.units != qb.units:
        qa = convert(qa, qb.units, rates)
    if qb.mag == 0:
        raise CalcError("division by zero")
    return qa.mag / qb.mag


def _pat_change(p: Parser) -> Value | None:
    # 50 to 75 is what % | 40 to 90 as % | 50 to 75 is what x | 20 to 40 as x
    a = _hole(p, "to")
    p.expect("to")
    b = _hole(p, "is", "as")
    if p.take("is"):
        p.expect("what")
    else:
        p.expect("as")
    r = _ratio(b, a, p.rates)
    if p.take("%", "percent"):
        return Q(r - 1, pct=True)
    if p.take("x", "multiplier"):
        return Q(r, fmt="x")
    return None


def _pat_what_pct(p: Parser) -> Value | None:
    # 180 is what % off 200 | 180 is what % on 150 | 20 is what % of 200 | 20 is what %
    a = _hole(p, "is")
    p.expect("is")
    p.expect("what")
    p.expect("%", "percent")
    if p.done():
        q = _q(a)
        return Q(q.mag, pct=True)
    word = p.peek()
    if word is None or word.key not in ("of", "on", "off"):
        return None
    p.pos += 1
    b = _hole(p)
    r = _ratio(a, b, p.rates)
    return Q({"of": r, "on": r - 1, "off": 1 - r}[word.key], pct=True)


def _pat_as_pct_of(p: Parser) -> Value | None:
    # 20 as a % of 200 | 20 as % of 200 | 50 as x of 5 | 2 as multiplier on 1 | 1 as x off 2
    a = _hole(p, "as")
    p.expect("as")
    p.take("a")
    if p.take("%", "percent"):
        kind = "pct"
    elif p.take("x", "multiplier"):
        kind = "x"
    else:
        return None
    word = p.peek()
    if word is None or word.key not in ("of", "on", "off"):
        return None
    p.pos += 1
    b = _hole(p)
    r = _ratio(a, b, p.rates)
    val = {"of": r, "on": r - 1, "off": 1 - r}[word.key]
    return Q(val, pct=True) if kind == "pct" else Q(val, fmt="x")


def _pat_of_what(p: Parser) -> Value | None:
    # 20 is 10% of what | 180 is 10% off what | 220 is 10% on what | 50 is 1/5 of what
    a = _hole(p, "is")
    p.expect("is")
    pct = _hole(p, "of", "on", "off")
    word = p.peek()
    if word is None or word.key not in ("of", "on", "off"):
        return None
    p.pos += 1
    p.expect("what")
    f = _pct_of(pct)
    qa = _q(a)
    base = {"of": f, "on": 1 + f, "off": 1 - f}[word.key]
    if base == 0:
        raise CalcError("division by zero")
    return Q(qa.mag / base, qa.units)


def _pat_one_in(p: Parser) -> Value | None:
    # 5% is 1 in what
    a = _hole(p, "is")
    p.expect("is")
    one = p.peek()
    if one is None or one.kind != "num" or one.tok.value != 1:
        return None
    p.pos += 1
    p.expect("in")
    p.expect("what")
    f = _pct_of(a)
    if f == 0:
        raise CalcError("division by zero")
    return Q(f, fmt="one_in")


def _pat_in_what_pct(p: Parser) -> Value | None:
    # 3 in 20 is what %
    a = _hole(p, "in")
    p.expect("in")
    b = _hole(p, "is")
    p.expect("is")
    p.expect("what")
    p.expect("%", "percent")
    return Q(_ratio(a, b, p.rates), pct=True)


def _pat_proportion(p: Parser) -> Value | None:
    # 20% is 500, what is 750 | if 20 is 30%, what is 60%
    p.take("if")
    x1 = _hole(p, "is")
    p.expect("is")
    y1 = _hole(p, ",", "what")
    p.take(",")
    p.expect("what")
    p.expect("is")
    y2 = _hole(p)
    qx, qy1, qy2 = _q(x1), _q(y1), _q(y2)
    r = _ratio(qy2, qy1, p.rates) if not (qy1.pct or qy2.pct) else qy2.mag / qy1.mag
    return Q(qx.mag * r, qx.units, pct=qx.pct)


def _pat_what_per(p: Parser) -> Value | None:
    # $30/day is what per year
    a = _hole(p, "is")
    p.expect("is")
    p.expect("what")
    p.expect("per", "a")
    unit = p.unit_expr()
    if unit is None:
        return None
    return _rebase_rate(_q(a), unit, p.rates)


PATTERNS: list[Callable[[Parser], Value | None]] = [
    _pat_change,
    _pat_what_pct,
    _pat_as_pct_of,
    _pat_of_what,
    _pat_one_in,
    _pat_in_what_pct,
    _pat_proportion,
    _pat_what_per,
]


def evaluate_tokens(items: list[Item], ctx: Context, plain: set[int] | None = None) -> Value:
    """Evaluate the line; if it fails, use the longest tail (then head) that works.

    `plain` gets the id() of each soft keyword ("if", "to", "in") the maths didn't use.
    """
    soft = [it for it in items if it.kind == "kw" and it.key in SOFT]
    items = [
        it
        for i, it in enumerate(items)
        if it.kind != "noise" and (it.kind != "tag" or (i and items[i - 1].key == "of"))
    ]
    if not items:
        raise ParseError("empty")
    errors: list[Exception] = []
    candidates = [items[s:] for s in range(len(items))]
    candidates += [items[:e] for e in range(len(items) - 1, 0, -1)]
    for n, cand in enumerate(candidates):
        try:
            parser = Parser(cand, ctx)
            value = parser.statement()
        except CalcError:
            if n == 0:
                raise  # the whole line is maths that can't be done: show no answer
            errors.append(ParseError("no answer"))
        except (ParseError, ArithmeticError, ValueError, OverflowError, KeyError) as exc:
            errors.append(exc)
        else:
            if plain is not None:
                used = {id(it) for i, it in enumerate(cand) if i not in parser.plain}
                plain.update(id(it) for it in soft if id(it) not in used)
            return value
    first = errors[0] if errors else ParseError("nothing to calculate")
    if isinstance(first, CalcError):
        raise first
    raise ParseError(str(first))


def simplify_value(v: Value, rates: RateTable) -> Value:
    if isinstance(v, Q) and v.units:
        return simplify(v, rates)
    return v


def today(ctx: Context) -> date:
    return ctx.config.now().date()


def tokenize_line(text: str, ctx: Context) -> list[Tok]:
    return tokenize(text, ctx.config.number_style)
