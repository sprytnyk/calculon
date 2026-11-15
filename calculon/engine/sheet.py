"""Evaluate a whole sheet, line by line."""

import logging
import re
from contextlib import suppress
from dataclasses import dataclass, field, replace

from . import units as U
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
    var_key,
)
from .lexer import Tok
from .timeline import (
    DIRECTIVE_RE,
    Timeline,
    is_start,
    lasts_text,
    left_text,
    short_time,
    time_left,
)
from .values import CalcError, DateVal, Q, Value, add, is_money

log = logging.getLogger(__name__)

HEADING_RE = re.compile(r"^\s*#(\s|$)")
DIVIDER_RE = re.compile(r"^\s*-{3,}\s*$")
LABEL_RE = re.compile(r"^(?P<label>[^:=\n]*[^\W\d_][^:=\n]*?):(?=\s|$)")
ASSIGN_RE = re.compile(r"^(?P<lead>\s*)(?P<name>[^\W\d][\w ]*?)\s*(?P<op>\+=|-=|=)(?!=)\s*")
# "1. ", "1) " and "• " start a list item; a bare "3 " too, but only before "name ="
# since a variable name can't start with a digit. "-" and "*" stay operators.
LIST_MARK_RE = re.compile(
    r"^\s*(?:(?:\d+[.)]|•)\s+(?=\S)|\d+\s+(?=[^\W\d][\w ]*?\s*(?:\+=|-=|=)(?!=)))"
)
# an operator at the very start continues the answer on the line just above, as typing does
# in Soulver; "-200" too, so a plain negative number under an answer needs a label
CONTINUE_RE = re.compile(r"^\s*(\+|-|−|\*|/|×|÷|\^)")
# how Soulver writes a reference into exported text: "[$1 000,00](line2) − 200"
SOULVER_REF_RE = re.compile(r"\[[^\]\n]*\]\((line\d+)\)")

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
    aggregate: str = ""  # a line like total, average or total of #food: "sum", "avg"...
    of_tag: bool = False  # the aggregate works on tagged lines, not the lines above
    short: str = ""  # the answer as the answers column shows it, when shorter: $386.8M
    hints: list[tuple[int, int, str]] = field(default_factory=list)  # variables' values

    @property
    def is_total(self) -> bool:
        """A total of the lines above: bold, and it starts a new block."""
        return bool(self.aggregate) and not self.of_tag


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
    # The sheet total adds up each answer once. A line that adds up earlier answers, as
    # "t = rent + food" does, takes their place in it; "deposit = rent × 2" doesn't.
    live: dict[int, Value] = {}  # the lines the total adds up
    taken_by: dict[int, int] = {}  # a line that left the total -> the line in its place
    out: set[int] = set()  # lines not in the total, nor anything worked out from them
    timeline: Timeline | None = None
    for i, raw in enumerate(text.split("\n")):
        ctx.used, ctx.adds_up = set(), set()
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
        if res.value is None:
            continue
        if directive or res.aggregate not in ("", "sum") or ctx.used & out:
            out.add(i)  # @from, average, count, or "* 12" under an average
            continue
        replaced = ctx.adds_up
        if res.aggregate:
            # a total adds up whole lines, so it takes the place of what stands for them
            # now, as a total of #food does for the lines tagged #food
            added = (j for j in ctx.used if _added_up(ctx.line_values[j], res.value))
            replaced = {_in_place_of(j, taken_by) for j in added}
        for j in replaced:
            if live.pop(j, None) is not None:
                taken_by[j] = i
        live[i] = res.value
    names = sorted(set(ctx.var_names.values()), key=str.lower)
    return SheetResult(results, _sheet_total(list(live.values()), rates), names)


def _in_place_of(line: int, taken_by: dict[int, int]) -> int:
    """The line that stands for this one in the sheet total now."""
    while line in taken_by:
        line = taken_by[line]
    return line


def _added_up(value: Value | None, total: Value) -> bool:
    """Whether a total added up this answer: it leaves out the kinds of unit it isn't in,
    as km in a total of money."""
    if not isinstance(value, Q) or not isinstance(total, Q) or value.pct:
        return False
    return U.dims_of(value.units) == U.dims_of(total.units)


def _sheet_total(values: list[Value], rates: RateTable) -> Q | None:
    """The status bar's total. Money wins when there's any; otherwise the kind of unit
    used most, as in a total line."""
    if not any(isinstance(v, Q) for v in values):
        return None
    money = [v for v in values if isinstance(v, Q) and is_money(v)]
    try:
        return aggregate("sum", money or values, rates)
    except CalcError, ArithmeticError:  # 9e999999 + 9e999999 overflows
        return None


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
    for m in SOULVER_REF_RE.finditer(raw):  # read as "line2", keeping every column in place
        start, end = m.span(1)
        line = line[: m.start()] + " " * (start - m.start()) + m[1] + " " + line[m.end() :]
        res.spans += [(m.start(), start, "comment"), (end, m.end(), "comment")]
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
        ctx.var_lines = {}
        ctx.custom_units = set()
        return res
    offset = 0
    m = LIST_MARK_RE.match(line)
    if m:
        res.spans.append((0, m.end(), "comment"))
        offset = m.end()
    labelled = False
    m = LABEL_RE.match(line[offset:])
    if m:
        labelled = True
        res.spans.append((offset, offset + m.end() + 1, "label"))
        offset += m.end() + 1
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
    if op == "=" and not body.strip():
        # "food =" with nothing after it names the subtotal, as in Soulver
        tok = Tok("WORD", "subtotal", len(line), len(line))
        items = [Item("kw", "subtotal", tok, tok)]
    else:
        toks = tokenize_line(body, ctx)
        for t in toks:
            t.start += offset
            t.end += offset
        items = classify(toks, ctx)
    # each variable's value as the line sees it, before an assignment changes it
    seen = {id(it): ctx.variables.get(it.key) for it in items if it.kind == "var"}
    plain: set[int] = set()  # "if", "to", "in" in prose: not coloured as keywords
    moves = timeline if labelled and not var_name else None
    skipped: set[int] = set()  # what the maths left out, as in the 4 of "4 Car $200"
    continues = offset == 0 and CONTINUE_RE.match(line) is not None  # no label, name, list mark
    _evaluate_items(res, items, var_name, op, ctx, opts, plain, skipped, continues, moves)
    if res.kind != "value":
        plain = {id(it) for it in items if it.kind == "kw" and it.key in SOFT}
    # a list number the maths left out looks like the skipped "1." of "1. Rent $1000"
    lead = next((it for it in items if it.kind != "noise"), None)
    if res.kind == "value" and lead is not None and lead.kind == "num" and id(lead) in skipped:
        plain.add(id(lead))
        res.spans.append((lead.start, lead.end, "comment"))
    for it in items:
        cls = SPAN_CLASSES.get(it.kind)
        if cls and id(it) not in plain and it.end > it.start:
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
    var_name: str | None,
    op: str | None,
    ctx: Context,
    opts: FormatOptions,
    plain: set[int],
    skipped: set[int],
    continues: bool,
    timeline: Timeline | None = None,
) -> None:
    meaningful = [it for it in items if it.kind != "noise"]
    res.aggregate, res.of_tag = _aggregate_of(meaningful)
    if not any(it.kind != "tag" for it in meaningful):
        res.kind = "text"
        return
    # a line starting with an operator continues from the answer just above it
    above = ctx.line_values[-1] if ctx.line_values else None
    continued = continues and above is not None and meaningful[0].kind == "op"
    if continued:
        meaningful.insert(0, _prev_item(meaningful[0]))
    try:
        if var_name and op in ("+=", "-="):
            key = var_key(var_name)
            if key not in ctx.variables:
                raise ParseError(f"{var_name} is not defined")
            current = ctx.variables[key]
            value = add(
                current,
                evaluate_tokens(meaningful, ctx, plain, skipped),
                ctx.rates,
                1 if op == "+=" else -1,
            )
        else:
            value = evaluate_tokens(meaningful, ctx, plain, skipped)
        if continued and all(id(it) in skipped for it in meaningful[1:]):
            # "- milk" under $10 is a note, not $10 again
            raise ParseError("nothing after the operator")
        if timeline is not None and not res.is_total:
            value = timeline.advance(value, ctx.rates)  # a labelled duration moves it
    except (ParseError, ArithmeticError, ValueError) as exc:
        res.kind = "text"
        res.error = str(exc)
        return
    try:
        text = format_value(value, opts)
    except ArithmeticError, ValueError:  # 1e999999 as % overflows while formatting
        res.kind = "text"
        res.error = "number too large"
        return
    # "- 5k" and "rent += $100" change the answer they start from, whatever the maths
    if continued:
        ctx.adds_up.add(len(ctx.line_values) - 1)
    elif var_name and op in ("+=", "-="):
        line = ctx.var_lines[var_key(var_name)]
        ctx.used.add(line)
        ctx.adds_up.add(line)
    if var_name:
        ctx.set_var(var_name, value)
    res.kind = "value"
    res.value = value
    res.text = text
    with suppress(ArithmeticError, ValueError):
        if (short := format_value(value, opts, short=True)) != text:
            res.short = short
    line = len(ctx.line_values)  # the line being worked out
    if res.is_total:
        ctx.block = []
    elif not res.of_tag:  # its tagged lines are in the block already
        ctx.block.append(line)
    for i, it in enumerate(items):
        if it.kind == "tag" and not (i and items[i - 1].key == "of"):
            ctx.tags.setdefault(it.key, []).append(line)


def _aggregate_of(items: list[Item]) -> tuple[str, bool]:
    """What a line like total or average works out ("sum", "avg"...), or "" if it isn't
    one, and whether it works on tagged lines, as "total of #food" does. "total of 3, 4"
    isn't one: it adds up numbers of its own."""
    if not items or items[0].kind != "kw" or items[0].key not in AGGREGATES:
        return "", False
    kind = AGGREGATES[items[0].key]
    if len(items) > 1 and items[1].key == "of":
        tagged = len(items) > 2 and items[2].kind == "tag"
        return (kind, True) if tagged else ("", False)
    return kind, False


def _prev_item(first: Item) -> Item:
    return Item("kw", "prev", first.tok, first.tok)
