"""Split a line into tokens."""

import re
from dataclasses import dataclass
from decimal import Decimal

from .currency import PREFIX_SYMBOLS


@dataclass
class Tok:
    kind: str  # NUM WORD OP CUR DATE TIME TAG
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
GENERAL_SCALES = {"k", "K", "M", "G", "T"}

_PREFIX_SYMS = sorted(PREFIX_SYMBOLS, key=len, reverse=True)
_DATE_RE = re.compile(
    r"(?P<iso>(?P<y1>\d{4})-(?P<m1>\d{1,2})-(?P<d1>\d{1,2}))"
    r"|(?P<a>\d{1,2})(?P<sep>[/.])(?P<b>\d{1,2})(?P=sep)(?P<y2>\d{4})"
)
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
    thousands, point = {
        "comma_dot": (",", "."),
        "dot_comma": (".", ","),
        "space_comma": (" ", ","),
        "space_dot": (" ", "."),
    }.get(number_style, (",", "."))
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
        if c.isdecimal() or (c == "." and i + 1 < n and line[i + 1].isdecimal()):
            m = _DATE_RE.match(line, i)
            if m and not (m.end() < n and line[m.end()].isdecimal()):
                if m.group("iso"):
                    val = (int(m.group("y1")), int(m.group("m1")), int(m.group("d1")), "ymd")
                else:
                    val = (int(m.group("a")), int(m.group("b")), int(m.group("y2")), "ab")
                toks.append(Tok("DATE", m.group(), i, m.end(), val))
                i = m.end()
                continue
            m = _TIME_RE.match(line, i)
            if m:
                if m.group("h") is not None:
                    h, mi = int(m.group("h")), int(m.group("m"))
                    s = int(m.group("s") or 0)
                    ap = m.group("ap")
                else:
                    h, mi, s, ap = int(m.group("h2")), 0, 0, m.group("ap2")
                if ap:
                    h = h % 12 + (12 if ap.lower() == "p" else 0)
                if h < 24 and mi < 60 and s < 60:
                    toks.append(Tok("TIME", m.group(), i, m.end(), (h, mi, s)))
                    i = m.end()
                    continue
            tok, i = _number(line, i, thousands, point)
            toks.append(tok)
            # attached scale suffix: 2.5k, $5m, 7bn
            m = re.compile(r"(bn|tn|[kKMGTmbBt])(?![\w])").match(line, i)
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


_NUM_PREFIX = re.compile(r"0([xX][0-9a-fA-F_]+|[bB][01_]+|[oO][0-7_]+)")


def _number(line: str, i: int, thousands: str, point: str) -> tuple[Tok, int]:
    m = _NUM_PREFIX.match(line, i)
    if m and not (m.end() < len(line) and line[m.end()].isalnum()):
        body = m.group(1)
        base = {"x": 16, "b": 2, "o": 8}[body[0].lower()]
        value = Decimal(int(body[1:].replace("_", ""), base))
        fmt = {16: "hex", 2: "bin", 8: "oct"}[base]
        return Tok("NUM", m.group(), i, m.end(), value, fmt=fmt), m.end()
    start = i
    n = len(line)
    digits = []
    # integer part with grouping
    while i < n and (line[i].isdecimal() or line[i] == "_"):
        if line[i] != "_":
            digits.append(line[i])
        i += 1
    while i < n:
        sep = line[i]
        is_group = sep == thousands or (thousands == " " and sep in "   ")
        if is_group and _three_digits(line, i + 1):
            digits.extend(line[i + 1 : i + 4])
            i += 4
            continue
        break
    decimal_sep = point
    if (
        i < n
        and line[i] in (point, ".")
        and i + 1 < n
        and line[i + 1].isdecimal()
        and (line[i] == point or thousands == " ")
    ):
        digits.append(".")
        i += 1
        while i < n and (line[i].isdecimal() or line[i] == "_"):
            if line[i] != "_":
                digits.append(line[i])
            i += 1
    del decimal_sep
    # scientific notation: 1.5e3, 2E-4
    m = re.compile(r"[eE][+-]?\d+(?![\w])").match(line, i)
    if m:
        digits.append(m.group())
        i = m.end()
    text = "".join(digits) or "0"
    if text.startswith("."):
        text = "0" + text
    return Tok("NUM", line[start:i], start, i, Decimal(text)), i


def _three_digits(line: str, j: int) -> bool:
    return (
        j + 3 <= len(line)
        and line[j : j + 3].isdecimal()
        and not (j + 3 < len(line) and line[j + 3].isdecimal())
    )
