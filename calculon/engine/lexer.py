"""Split a line into tokens."""

import re
from dataclasses import dataclass
from datetime import date
from decimal import Decimal, InvalidOperation

from .currency import PREFIX_SYMBOLS
from .months import MONTHS
from .numbers import decimal_mantissa, separators


@dataclass
class Tok:
    kind: str  # NUM INVALID_NUMBER UNFINISHED_NUMBER WORD OP CUR DATE TIME TAG
    text: str
    start: int
    end: int
    value: object = None  # Decimal for NUM, tuple for DATE/TIME, code for CUR
    scale: str | None = None  # scale suffix attached to a number ("k", "M", "bn")
    fmt: str | None = None  # number base for 0x/0b/0o literals
    cls: str = ""  # filled in by the interpreter: num, unit, currency, var, kw, fn, noise


SCALES = {
    "k": Decimal(10) ** 3,
    "K": Decimal(10) ** 3,
    "к": Decimal(10) ** 3,  # Cyrillic, as in 5к
    "К": Decimal(10) ** 3,
    "M": Decimal(10) ** 6,
    "G": Decimal(10) ** 9,
    "T": Decimal(10) ** 12,
    # money only
    "m": Decimal(10) ** 6,
    "b": Decimal(10) ** 9,
    "B": Decimal(10) ** 9,
    "bn": Decimal(10) ** 9,
    "t": Decimal(10) ** 12,
    "tn": Decimal(10) ** 12,
}
GENERAL_SCALES = {"k", "K", "к", "К", "M", "G", "T"}

_PREFIX_SYMS = sorted(PREFIX_SYMBOLS, key=len, reverse=True)
_ISO_DATE = re.compile(r"(\d{4})-(\d{2})-(\d{2})(?!\d|[.,]\d)")
_OTHER_DATE = re.compile(r"\d{1,2}([./-])\d{1,2}\1\d{4}(?!\d|[.,]\d)")
_MONTH = "|".join(sorted(MONTHS, key=len, reverse=True))
_DAY = r"\d{1,2}(?:st|nd|rd|th)?"
_NAMED_DATE = re.compile(
    rf"(?:(?P<day>{_DAY})\s+(?P<month>{_MONTH})\.?|(?P<first>{_MONTH})\.?\s+(?P<after>{_DAY}))"
    r"(?:(?:\s+|,\s*)(?P<year>\d{4})(?![\w:]|[.,]\d))?(?![\w:]|[.,]\d)",
    re.IGNORECASE,
)
_MONTH_YEAR = re.compile(rf"({_MONTH})\.?\s+([12]\d{{3}})(?![\w:]|[.,]\d)", re.IGNORECASE)
_DAY_DIGITS = re.compile(r"\d+")
_TIME_RE = re.compile(
    r"(?P<h>\d{1,2}):(?P<m>\d{2})(?::(?P<s>\d{2}))?(?:\s?(?P<ap>[aApP])\.?[mM]\.?)?(?![\w:])"
    r"|(?P<h2>\d{1,2})\s?(?P<ap2>[aApP])\.?[mM]\.?(?!\w)"
)
_OPS = ["**", "+=", "-=", "//", "+", "-", "−", "–", "*", "×", "·", "/", "÷", "^", "(", ")"]
_OPS += [",", "=", "%", ";", "!", "?", ":", "@"]
_WORD_RE = re.compile(r"[°℃℉]?[^\W\d_][\w']*[²³]?|°")


def tokenize(line: str, number_style: str = "comma_dot") -> list[Tok]:
    toks: list[Tok] = []
    i = 0
    n = len(line)
    group, point = separators(number_style)
    while i < n:
        c = line[i]
        if c.isspace():
            i += 1
            continue
        # quoted text is ignored
        if c in '"“”':
            close = line.find('"' if c == '"' else "”", i + 1)
            if close == -1:
                close = n - 1
            i = close + 1
            continue
        # tags
        if c == "#" and i + 1 < n and line[i + 1].isalnum():
            m = re.compile(r"#[\w-]+").match(line, i)
            assert m
            toks.append(Tok("TAG", m.group(), i, m.end()))
            i = m.end()
            continue
        if (c.isdecimal() or c.isalpha()) and (date := _date(line, i)):
            toks.append(date)
            i = date.end
            continue
        if c.isdecimal() and (clock := _TIME_RE.match(line, i)):
            toks.append(_time(clock))
            i = clock.end()
            continue
        if (
            c.isdecimal()
            or (c in _NUMBER_PUNCTUATION and _LEADING_POINT.match(line, i))
            or (c == point and (not toks or toks[-1].kind == "OP") and not line[i + 1 :].strip())
        ):
            tok = _number(line, i, group, point)
            toks.append(tok)
            i = tok.end
            if tok.kind != "NUM":
                continue
            # attached scale suffix: 2.5k, 5к, $5m, 7bn
            m = re.compile(r"(bn|tn|[kKкКMGTmbBt])(?![\w])").match(line, i)
            if m:
                tok.scale = m.group(1)
                tok.end = m.end()
                tok.text = line[tok.start : tok.end]
                i = m.end()
            continue
        # currency prefix symbols: $, US$, €, ...
        sym = next((s for s in _PREFIX_SYMS if line.startswith(s, i)), None)
        # "zł" etc. must not be part of a longer word
        if (
            sym
            and not (sym[0].isalpha() and i > 0 and line[i - 1].isalnum())
            and not (sym[-1].isalpha() and i + len(sym) < n and line[i + len(sym)].isalpha())
        ):
            toks.append(Tok("CUR", sym, i, i + len(sym), PREFIX_SYMBOLS[sym]))
            i += len(sym)
            continue
        if c == "$":
            toks.append(Tok("CUR", "$", i, i + 1, "$"))
            i += 1
            continue
        # 20², (1 + 2)³: a power. "m²" never gets here, the word takes its ²
        if c in "²³":
            if toks and (toks[-1].kind == "NUM" or toks[-1].text == ")"):
                toks.append(Tok("OP", "^", i, i + 1))
                toks.append(Tok("NUM", c, i, i + 1, Decimal(2 if c == "²" else 3)))
            i += 1
            continue
        m = _WORD_RE.match(line, i)
        if m:
            toks.append(Tok("WORD", m.group(), i, m.end()))
            i = m.end()
            continue
        op = next((o for o in _OPS if line.startswith(o, i)), None)
        if op:
            toks.append(Tok("OP", op, i, i + len(op)))
            i += len(op)
            continue
        # anything else (emoji, stray symbols) is skipped
        i += 1
    return toks


_NUM_PREFIX = re.compile(r"0([xX]|[bB](?=[\d_.,])|[oO](?=\d|_|[^\w]|$))[\w.,]*")
# Include unsupported separators in pasted numbers so validation sees the whole number.
_NUMBER_PUNCTUATION = ".,٫٬，．"
_DECIMAL_RUN = rf"[\d_{_NUMBER_PUNCTUATION}]+"
_NUM_PART = re.compile(rf"{_DECIMAL_RUN}(?:['’ʼ](?=\d){_DECIMAL_RUN})*")
_LEADING_POINT = re.compile(rf"[{_NUMBER_PUNCTUATION}]+\d")
_SPACE_BEFORE_DIGIT = re.compile(r"[^\S\r\n]+(?=\d)")
_EXPONENT = re.compile(r"[eE][+-]?\d*(?![\w])")


def _date(line: str, i: int) -> Tok | None:
    if m := _ISO_DATE.match(line, i):
        parts = tuple(map(int, m.groups()))
        try:
            date(*parts)
        except ValueError:
            return Tok("INVALID_CALENDAR_DATE", m.group(), i, m.end())
        return Tok("DATE", m.group(), i, m.end(), parts)
    if m := _OTHER_DATE.match(line, i):
        return Tok("INVALID_DATE", m.group(), i, m.end())
    if m := _NAMED_DATE.match(line, i):
        day_text = m["day"] or m["after"]
        digits = _DAY_DIGITS.match(day_text)
        assert digits
        day = int(digits.group())
        year = int(m["year"]) if m["year"] else None
        month_name = m["month"] or m["first"]
    elif m := _MONTH_YEAR.match(line, i):
        month_name, year_text = m.groups()
        year, day = int(year_text), 1
    else:
        return None
    month = MONTHS.get(month_name.lower())
    if month is None:
        return Tok("INVALID_CALENDAR_DATE", m.group(), i, m.end())
    return Tok("DATE", m.group(), i, m.end(), (year, month, day))


def _time(match: re.Match[str]) -> Tok:
    hours = int(match["h"] or match["h2"])
    minutes = int(match["m"] or 0)
    seconds = int(match["s"] or 0)
    period = match["ap"] or match["ap2"]
    start, end = match.span()
    valid_hour = 1 <= hours <= 12 if period else hours < 24
    if not valid_hour or minutes >= 60 or seconds >= 60:
        return Tok("INVALID_TIME", match[0], start, end)
    if period:
        hours = hours % 12 + (12 if period.lower() == "p" else 0)
    return Tok("TIME", match[0], start, end, (hours, minutes, seconds))


def _number(line: str, i: int, group: str, point: str) -> Tok:
    if m := _NUM_PREFIX.match(line, i):
        base, fmt = {"x": (16, "hex"), "b": (2, "bin"), "o": (8, "oct")}[m[1].lower()]
        end = _numeric_end(line, i, m.end())
        text = line[i:end]
        digits = text[2:].replace("_", "")
        if not digits and not line[end:].strip():
            return Tok("UNFINISHED_NUMBER", text, i, end)
        try:
            value = int(digits, base)
        except ValueError:
            return Tok("INVALID_NUMBER", text, i, end)
        return Tok("NUM", text, i, end, Decimal(value), fmt=fmt)
    part = _NUM_PART.match(line, i)
    assert part
    end = _numeric_end(line, i, part.end())
    normalized, incomplete = decimal_mantissa(line[i:end], group, point)
    if exp := _EXPONENT.match(line, end):
        exp_text = exp.group()
        end = exp.end()
        if not exp_text[-1].isdecimal():
            incomplete = normalized is not None
            normalized = None
        elif normalized is None:
            incomplete = False
        else:
            normalized += exp_text
        # Punctuation after the exponent cannot start a second decimal in the same run.
        tail = _NUM_PART.match(line, end)
        tail_end = _numeric_end(line, i, tail.end() if tail else end)
        if tail_end > end:
            end = tail_end
            normalized, incomplete = None, False
    text = line[i:end]
    if normalized is not None:
        try:
            value = Decimal(normalized)
        except InvalidOperation:
            return Tok("INVALID_NUMBER", text, i, end)
        return Tok("NUM", text, i, end, value)
    kind = "UNFINISHED_NUMBER" if incomplete and not line[end:].strip() else "INVALID_NUMBER"
    return Tok(kind, text, i, end)


def _numeric_end(line: str, start: int, end: int) -> int:
    while space := _SPACE_BEFORE_DIGIT.match(line, end):
        part = _NUM_PART.match(line, space.end())
        assert part
        end = part.end()
    # A comma can be punctuation in a sentence, as in "500, what is ...".
    if (
        end > start + 1
        and line[end - 1] == ","
        and line[end - 2].isdecimal()
        and end < len(line)
        and (line[end].isspace() or line[end].isalpha())
        and line[end:].strip()
    ):
        return end - 1
    return end
