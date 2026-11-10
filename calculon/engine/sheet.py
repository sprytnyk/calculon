"""Evaluate a whole sheet, line by line."""

from __future__ import annotations

import logging
import re
from dataclasses import dataclass, field, replace

from .currency import RateTable
from .format import FormatOptions, format_value
from .interpreter import (
    AGGREGATES,
    Config,
    Context,
    Item,
    ParseError,
    aggregate,
    classify,
    evaluate_tokens,
    tokenize_line,
)
from .values import CalcError, Q, Value

log = logging.getLogger(__name__)

HEADING_RE = re.compile(r"^\s*#(\s|$)")
DIVIDER_RE = re.compile(r"^\s*-{3,}\s*$")
LABEL_RE = re.compile(r"^(?P<label>[^:=\n]*[^\W\d_][^:=\n]*?):(?=\s|$)")
ASSIGN_RE = re.compile(r"^(?P<lead>\s*)(?P<name>[^\W\d][\w ]*?)\s*(?P<op>\+=|-=|=)(?!=)\s*")
CONTINUE_RE = re.compile(r"^\s*(\+|\*|/|×|÷|\^)")

# highlight classes
SPAN_CLASSES = {
    "num": "number",
    "cur": "unit",
    "unit": "unit",
    "city": "unit",
    "var": "variable",
    "kw": "keyword",
    "fn": "keyword",
    "const": "keyword",
    "lineref": "keyword",
    "month": "keyword",
    "weekday": "keyword",
    "date": "number",
    "time": "number",
    "tag": "tag",
    "op": "operator",
}


@dataclass
class LineResult:
    kind: str = "empty"  # empty heading divider comment value text
    value: Value | None = None
    text: str = ""
    error: str = ""
    spans: list[tuple[int, int, str]] = field(default_factory=list)
    is_total: bool = False


@dataclass
class SheetResult:
    lines: list[LineResult]
    total: Value | None
    variables: list[str]


def evaluate_sheet(
    text: str,
    rates: RateTable,
    config: Config | None = None,
    opts: FormatOptions | None = None,
) -> SheetResult:
    opts = opts or FormatOptions()
    config = replace(config or Config(), number_style=opts.number_style)
    ctx = Context(rates=rates, config=config)
    results: list[LineResult] = []
    all_values: list[Value] = []
    for raw in text.split("\n"):
        try:
            res = _evaluate_line(raw, ctx, opts)
        except Exception as exc:  # noqa: BLE001 - one bad line must never break the sheet
            log.debug("line failed: %r", raw, exc_info=True)
            res = LineResult(kind="text", error=f"internal error: {type(exc).__name__}")
        results.append(res)
        ctx.line_values.append(res.value)
        if res.value is not None:
            ctx.prev = res.value
            if not res.is_total:
                all_values.append(res.value)
    total = None
    if any(isinstance(v, Q) for v in all_values):
        try:
            total = aggregate("sum", all_values, rates)
        except CalcError, ArithmeticError:  # 9e999999 + 9e999999 overflows
            total = None
    names = sorted(set(ctx.var_names.values()), key=str.lower)
    return SheetResult(results, total, names)


def _evaluate_line(raw: str, ctx: Context, opts: FormatOptions) -> LineResult:
    res = LineResult()
    line = raw
    comment_at = line.find("//")
    if comment_at != -1:
        res.spans.append((comment_at, len(raw), "comment"))
        line = line[:comment_at]
    if not line.strip():
        res.kind = "comment" if comment_at != -1 else "empty"
        return res
    if HEADING_RE.match(line):
        res.kind = "heading"
        res.spans = [(0, len(raw), "heading")]
        ctx.block = []
        return res
    if DIVIDER_RE.match(line):
        res.kind = "divider"
        res.spans = [(0, len(raw), "comment")]
        ctx.block = []
        ctx.tags = {}
        ctx.variables = {}
        ctx.var_names = {}
        ctx.custom_units = set()
        return res
    offset = 0
    m = LABEL_RE.match(line)
    if m and not re.search(r"\d$", m.group("label")):
        res.spans.append((0, m.end() + 1, "label"))
        offset = m.end() + 1
    body = line[offset:]
    var_name = None
    op = None
    m = ASSIGN_RE.match(body)
    if m:
        var_name = m.group("name").strip()
        op = m.group("op")
        res.spans.append((offset + m.start("name"), offset + m.end("name"), "variable"))
        offset += m.end()
        body = line[offset:]
    toks = tokenize_line(body, ctx)
    for t in toks:
        t.start += offset
        t.end += offset
    items = classify(toks, ctx)
    for it in items:
        cls = SPAN_CLASSES.get(it.kind)
        if cls:
            res.spans.append((it.start, it.end, cls))
    meaningful = [it for it in items if it.kind != "noise"]
    res.is_total = _is_total_line(meaningful)
    if not [it for it in meaningful if it.kind != "tag"]:
        res.kind = "text"
        return res
    # a line starting with an operator continues from the previous answer
    if CONTINUE_RE.match(body) and ctx.prev is not None and meaningful[0].kind == "op":
        meaningful.insert(0, _prev_item(meaningful[0]))
    try:
        if var_name and op in ("+=", "-="):
            key = " ".join(var_name.lower().split())
            if key not in ctx.variables:
                raise ParseError(f"{var_name} is not defined")
            current = ctx.variables[key]
            from .values import add

            value = add(
                current, evaluate_tokens(meaningful, ctx), ctx.rates, 1 if op == "+=" else -1
            )
        else:
            value = evaluate_tokens(meaningful, ctx)
    except (ParseError, CalcError, ArithmeticError, ValueError, OverflowError) as exc:
        res.kind = "text"
        res.error = str(exc)
        return res
    try:
        text = format_value(value, opts)
    except ArithmeticError, ValueError:  # 1e999999 as % overflows while formatting
        res.kind = "text"
        res.error = "number too large"
        return res
    if var_name:
        ctx.set_var(var_name, value)
    res.kind = "value"
    res.value = value
    res.text = text
    if res.is_total:
        ctx.block = []
    else:
        ctx.block.append(value)
    for i, it in enumerate(items):
        if it.kind == "tag" and not (i and items[i - 1].key == "of"):
            ctx.tags.setdefault(it.key, []).append(value)
    return res


def _is_total_line(items: list[Item]) -> bool:
    if not items or items[0].kind != "kw" or items[0].key not in AGGREGATES:
        return False
    return not (len(items) > 1 and items[1].key == "of")


def _prev_item(first: Item) -> Item:
    return Item("kw", "prev", first.tok, first.tok)
