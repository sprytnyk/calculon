"""Evaluate a whole sheet, line by line."""

import logging
import re
from dataclasses import dataclass, field, replace

from .currency import RateTable
from .format import FormatOptions, format_value
from .interpreter import (
    AGGREGATES,
    SOFT,
    Config,
    Context,
    Item,
    ParseError,
    aggregate,
    classify,
    evaluate_tokens,
    tokenize_line,
)
from .timeline import (
    DIRECTIVE_RE,
    Timeline,
    is_start,
    lasts_text,
    left_text,
    short_time,
    time_left,
)
from .values import CalcError, DateVal, Q, Value, add

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
    hints: list[tuple[int, int, str]] = field(default_factory=list)  # variables' values


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
    timeline: Timeline | None = None
    for raw in text.split("\n"):
        directive = DIRECTIVE_RE.match(raw)
        try:
            if directive:
                res, timeline = _evaluate_directive(raw, directive, timeline, ctx, opts)
            else:
                res = _evaluate_line(raw, ctx, opts, timeline)
                if res.kind == "divider":
                    timeline = None
        except Exception as exc:  # noqa: BLE001 - one bad line must never break the sheet
            log.debug("line failed: %r", raw, exc_info=True)
            res = LineResult(kind="text", error=f"internal error: {type(exc).__name__}")
        results.append(res)
        ctx.line_values.append(res.value)
        if res.value is not None:
            ctx.prev = res.value
            if not res.is_total and not directive:
                all_values.append(res.value)
    total = None
    if any(isinstance(v, Q) for v in all_values):
        try:
            total = aggregate("sum", all_values, rates)
        except CalcError, ArithmeticError:  # 9e999999 + 9e999999 overflows
            total = None
    names = sorted(set(ctx.var_names.values()), key=str.lower)
    return SheetResult(results, total, names)


def _evaluate_directive(
    raw: str, m: re.Match[str], timeline: Timeline | None, ctx: Context, opts: FormatOptions
) -> tuple[LineResult, Timeline | None]:
    """@from <date> starts a timeline; @to [<date>] ends it."""
    at = m.start("word") - 1
    # blank out the directive so the rest keeps its columns for highlighting
    rest = raw[:at] + " " * (m.end() - at) + raw[m.end() :]
    block = len(ctx.block)
    res = _evaluate_line(rest, ctx, opts, None)
    del ctx.block[block:]  # @from/@to answers don't count in totals
    res.spans.insert(0, (at, m.end(), "keyword"))
    given = res.value if res.kind == "value" else None
    if is_start(m.group("word")):
        if isinstance(given, DateVal) and given.has_date:
            return res, Timeline(given, given)
        _no_answer(res, res.error or f"@{m.group('word')} needs a date")
        return res, Timeline(None, None)
    elapsed = timeline.elapsed() if timeline else None
    if timeline is None:
        _no_answer(res, f"no @{'від' if m.group('word').lower() == 'до' else 'from'} above")
    elif timeline.cursor is None or elapsed is None:
        _no_answer(res, "")  # @from already shows the error
    elif res.kind in ("empty", "comment"):
        res.kind = "value"
        res.value = timeline.cursor
        res.text = _format(timeline.cursor, opts)
        res.hints.append((at, m.end(), lasts_text(_format(elapsed, opts), opts.lang)))
    elif isinstance(given, DateVal) and given.has_date:
        value, shown, over = time_left(timeline.cursor, given)
        res.value = value
        # days and hours keep the answer short; hovering over @to shows it exactly
        short = shown if not given.has_time else short_time(shown)
        res.text = left_text(_format(short, opts), over, opts.lang)
        full = left_text(_format(shown if shown.mag else short, opts), over, opts.lang)
        res.hints.append((at, m.end(), f"{full}\n{lasts_text(_format(elapsed, opts), opts.lang)}"))
    else:
        _no_answer(res, res.error or f"@{m.group('word')} needs a date")
    return res, None


def _no_answer(res: LineResult, error: str) -> None:
    res.kind = "text"
    res.value = None
    res.text = ""
    res.error = error


def _evaluate_line(
    raw: str, ctx: Context, opts: FormatOptions, timeline: Timeline | None = None
) -> LineResult:
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
    labelled = False
    m = LABEL_RE.match(line)
    if m:
        labelled = True
        res.spans.append((0, m.end() + 1, "label"))
        offset = m.end() + 1
    body = line[offset:]
    var_name = None
    op = None
    name_span = (0, 0)
    m = ASSIGN_RE.match(body)
    if m:
        var_name = m.group("name").strip()
        op = m.group("op")
        name_span = (offset + m.start("name"), offset + m.end("name"))
        res.spans.append((*name_span, "variable"))
        offset += m.end()
        body = line[offset:]
    toks = tokenize_line(body, ctx)
    for t in toks:
        t.start += offset
        t.end += offset
    items = classify(toks, ctx)
    # each variable's value as the line sees it, before an assignment changes it
    seen = {id(it): ctx.variables.get(it.key) for it in items if it.kind == "var"}
    plain: set[int] = set()  # "if", "to", "in" in prose: not coloured as keywords
    moves = timeline if labelled and not var_name else None
    _evaluate_items(res, items, body, var_name, op, ctx, opts, plain, moves)
    if res.kind != "value":
        plain = {id(it) for it in items if it.kind == "kw" and it.key in SOFT}
    for it in items:
        cls = SPAN_CLASSES.get(it.kind)
        if cls and id(it) not in plain:
            res.spans.append((it.start, it.end, cls))
        if (value := seen.get(id(it))) is not None and (text := _format(value, opts)):
            res.hints.append((it.start, it.end, text))
    if var_name and res.kind == "value":
        res.hints.append((*name_span, res.text))
    return res


def _format(value: Value, opts: FormatOptions) -> str:
    try:
        return format_value(value, opts)
    except ArithmeticError, ValueError:
        return ""


def _evaluate_items(
    res: LineResult,
    items: list[Item],
    body: str,
    var_name: str | None,
    op: str | None,
    ctx: Context,
    opts: FormatOptions,
    plain: set[int],
    timeline: Timeline | None = None,
) -> None:
    meaningful = [it for it in items if it.kind != "noise"]
    res.is_total = _is_total_line(meaningful)
    if not [it for it in meaningful if it.kind != "tag"]:
        res.kind = "text"
        return
    # a line starting with an operator continues from the previous answer
    if CONTINUE_RE.match(body) and ctx.prev is not None and meaningful[0].kind == "op":
        meaningful.insert(0, _prev_item(meaningful[0]))
    try:
        if var_name and op in ("+=", "-="):
            key = " ".join(var_name.lower().split())
            if key not in ctx.variables:
                raise ParseError(f"{var_name} is not defined")
            current = ctx.variables[key]
            value = add(
                current, evaluate_tokens(meaningful, ctx, plain), ctx.rates, 1 if op == "+=" else -1
            )
        else:
            value = evaluate_tokens(meaningful, ctx, plain)
        if timeline is not None and not res.is_total:
            value = timeline.advance(value, ctx.rates)  # a labelled duration moves it
    except (ParseError, CalcError, ArithmeticError, ValueError, OverflowError) as exc:
        res.kind = "text"
        res.error = str(exc)
        return
    try:
        text = format_value(value, opts)
    except ArithmeticError, ValueError:  # 1e999999 as % overflows while formatting
        res.kind = "text"
        res.error = "number too large"
        return
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


def _is_total_line(items: list[Item]) -> bool:
    if not items or items[0].kind != "kw" or items[0].key not in AGGREGATES:
        return False
    return not (len(items) > 1 and items[1].key == "of")


def _prev_item(first: Item) -> Item:
    return Item("kw", "prev", first.tok, first.tok)
