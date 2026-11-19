"""Evaluate a whole sheet, line by line."""

import logging
import re
from contextlib import suppress
from dataclasses import dataclass, field, replace

from . import units as U
from .currency import RateTable
from .diagnostics import Diagnostic, DiagnosticError
from .format import FormatOptions, format_value
from .interpreter import (
    AGGREGATES,
    SOFT,
    SYMBOL_OPERATORS,
    VALUE_KEYWORDS,
    VALUE_KINDS,
    Config,
    Context,
    Item,
    ParseError,
    aggregate,
    classify,
    evaluate_tokens,
    tokenize_line,
    unsupported_date_in_range,
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
REFERENCE_OR_COMMENT_RE = re.compile(rf"{SOULVER_REF_RE.pattern}|(?P<comment>//)")
QUOTED_TEXT_RE = re.compile(r'"[^"]*(?:"|$)|[“”][^”]*(?:”|$)')

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
INPUT_WARNINGS = {
    "invalid_number": Diagnostic("invalid number"),
    "invalid_date": Diagnostic("use YYYY-MM-DD for numeric dates"),
    "invalid_calendar_date": Diagnostic("no such date"),
    "invalid_time": Diagnostic("no such time"),
}


@dataclass
class LineResult:
    kind: str = "empty"  # empty heading divider comment value text unfinished
    value: Value | None = None
    text: str = ""
    diagnostic: Diagnostic | None = None
    spans: list[tuple[int, int, str]] = field(default_factory=list)
    aggregate: str = ""  # a line like total, average or total of #food: "sum", "avg"...
    of_tag: bool = False  # the aggregate works on tagged lines, not the lines above
    short: str = ""  # the answer as the answers column shows it, when shorter: $386.8M
    hints: list[tuple[int, int, str]] = field(default_factory=list)  # variables' values

    @property
    def error(self) -> str:
        return self.diagnostic.render() if self.diagnostic is not None else ""

    @property
    def is_total(self) -> bool:
        """A total of the lines above: bold, and it starts a new block."""
        return bool(self.aggregate) and not self.of_tag


@dataclass
class SheetResult:
    lines: list[LineResult]
    total: Value | None
    variables: list[str]
    total_diagnostic: Diagnostic | None = None


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
    # Keep the original amounts available to overlapping subtotals. Arithmetic that
    # changes a subtotal takes the place of the amounts it covers.
    live: dict[int, Value] = {}  # the lines the total adds up
    subtotals: dict[int, set[int]] = {}  # a subtotal -> the lines that make it up
    taken_by: dict[int, int] = {}  # a line that left the total -> the line in its place
    out: set[int] = set()  # lines not in the total, nor anything worked out from them
    timeline: Timeline | None = None
    for i, raw in enumerate(text.split("\n")):
        ctx.used, ctx.adds_up, ctx.subtotal = set(), set(), None
        try:
            note_at = _note_at(raw, ctx) if "," in raw else None
            directive = (
                DIRECTIVE_RE.match(raw) if note_at is None else DIRECTIVE_RE.match(raw, 0, note_at)
            )
            if directive:
                res, timeline = _evaluate_directive(raw, directive, timeline, ctx, opts, note_at)
            else:
                res = _evaluate_line(raw, ctx, opts, timeline, note_at=note_at)
                if res.kind == "divider":
                    timeline = None
        except Exception:  # noqa: BLE001 - one bad line must never break the sheet
            log.debug("line failed: %r", raw, exc_info=True)
            res = LineResult(kind="text", diagnostic=Diagnostic("internal calculation error"))
        results.append(res)
        ctx.line_values.append(res.value)
        if res.value is None:
            continue
        if directive or res.aggregate not in ("", "sum") or ctx.used & out:
            out.add(i)  # @from, average, count, or "* 12" under an average
            continue
        replaced = ctx.adds_up
        if res.aggregate:
            summands = {j for j in ctx.used if _added_up(ctx.line_values[j], res.value)}
            if summands and res.value is ctx.subtotal:
                subtotals[i] = {line for j in summands for line in subtotals.get(j, {j})}
                continue
            replaced = {_in_place_of(j, taken_by) for j in summands}
        covered: set[int] = set()
        for j in replaced:
            if j in subtotals and j not in taken_by:
                covered.update(_in_place_of(line, taken_by) for line in subtotals[j])
                taken_by[j] = i
            else:
                covered.add(j)
        for j in covered:
            if live.pop(j, None) is not None:
                taken_by[j] = i
        live[i] = res.value
    names = sorted(set(ctx.var_names.values()), key=str.lower)
    total, diagnostic = _sheet_total(list(live.values()), rates)
    return SheetResult(results, total, names, diagnostic)


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


def _sheet_total(values: list[Value], rates: RateTable) -> tuple[Q | None, Diagnostic | None]:
    """The status bar's total. Money wins when there's any; otherwise the kind of unit
    used most, as in a total line."""
    if not any(isinstance(v, Q) for v in values):
        return None, None
    money = [v for v in values if isinstance(v, Q) and is_money(v)]
    try:
        return aggregate("sum", money or values, rates), None
    except CalcError as exc:
        return None, exc.diagnostic
    except ArithmeticError:  # 9e999999 + 9e999999 overflows
        return None, None


def _evaluate_directive(
    raw: str,
    m: re.Match[str],
    timeline: Timeline | None,
    ctx: Context,
    opts: FormatOptions,
    note_at: int | None,
) -> tuple[LineResult, Timeline | None]:
    """@from <date> starts a timeline; @to [<date>] ends it."""
    at = m.start("word") - 1
    # blank out the directive so the rest keeps its columns for highlighting
    rest = raw[:at] + " " * (m.end() - at) + raw[m.end() :]
    block = len(ctx.block)
    res = _evaluate_line(rest, ctx, opts, note_at=note_at)
    del ctx.block[block:]  # @from/@to answers don't count in totals
    res.spans.insert(0, (at, m.end(), "keyword"))
    if res.kind == "unfinished":
        return res, timeline
    given = res.value if res.kind == "value" else None
    if is_start(m.group("word")):
        if isinstance(given, DateVal) and given.has_date:
            return res, Timeline(given, given)
        _no_answer(res, res.diagnostic or Diagnostic("@{0} needs a date", (m.group("word"),)))
        return res, Timeline(None, None)
    elapsed = timeline.elapsed() if timeline else None
    if timeline is None:
        start = "від" if m.group("word").lower() == "до" else "from"
        _no_answer(res, Diagnostic("no @{0} above", (start,)))
    elif timeline.cursor is None or elapsed is None:
        _no_answer(res, None)  # @from already shows the error
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
        _no_answer(res, res.diagnostic or Diagnostic("@{0} needs a date", (m.group("word"),)))
    return res, None


def _no_answer(res: LineResult, diagnostic: Diagnostic | None) -> None:
    res.kind = "text"
    res.value = None
    res.text = ""
    res.diagnostic = diagnostic


def _expression_tokens(body: str, offset: int, ctx: Context, res: LineResult) -> list[Tok] | None:
    """Mark input warnings and return the tokens the calculator can use."""
    tokens = tokenize_line(body, ctx)
    has_unsupported_date = any(token.kind == "INVALID_DATE" for token in tokens)
    date_error = has_unsupported_date and (
        not any(token.kind == "DATE" for token in tokens) or unsupported_date_in_range(tokens)
    )
    for token in tokens:
        token.start += offset
        token.end += offset
        span = token.kind.lower()
        if warning := INPUT_WARNINGS.get(span):
            res.spans.append((token.start, token.end, span))
            if res.diagnostic is None and (span != "invalid_date" or date_error):
                res.diagnostic = warning
    if res.diagnostic is not None:
        res.kind = "text"
        return None
    if any(t.kind == "UNFINISHED_NUMBER" for t in tokens):
        res.kind = "unfinished"
        return None
    return [token for token in tokens if token.kind != "INVALID_DATE"]


def _note_at(line: str, ctx: Context) -> int | None:
    """Locate a trailing comma note before interpreting the line."""
    comment_at = line.find("//")
    if comment_at >= 0:
        # A // in an exported Soulver reference is part of its label.
        if line.find("[", 0, comment_at) >= 0:
            references_and_comments = REFERENCE_OR_COMMENT_RE.finditer(line)
            comment_at = next(
                (match.start() for match in references_and_comments if match["comment"]),
                len(line),
            )
        line = line[:comment_at]
    line = line.rstrip()
    if line.endswith(".") and line[-2:-1].isalpha():
        line = line[:-1]
    if not line[-1:].isalpha():
        return None
    suffix_start = len(line)
    while (comma := line.rfind(",", 0, suffix_start)) >= 0:
        clause = line[comma + 1 : suffix_start].strip()
        if not clause.isalpha():
            words = clause.replace("’", "'").split()
            if not words or any(not part.isalpha() for word in words for part in word.split("'")):
                break
        suffix_start = comma
    if suffix_start == len(line) or any(
        match.start() < suffix_start < match.end() for match in QUOTED_TEXT_RE.finditer(line)
    ):
        return None

    # Only check the suffix. A rejected note must leave the sheet's units untouched.
    items = classify(tokenize_line(line[suffix_start:], ctx), ctx, remember_units=False)
    note_at = None
    words_seen = False
    for item in reversed(items):
        if item.kind == "noise" and item.tok.kind == "WORD":
            words_seen = True
        elif words_seen and item.kind == "op" and item.key == ",":
            note_at = suffix_start + item.start
            words_seen = False
        else:
            break
    return note_at


def _evaluate_line(
    raw: str,
    ctx: Context,
    opts: FormatOptions,
    timeline: Timeline | None = None,
    *,
    note_at: int | None = None,
) -> LineResult:
    res = LineResult()
    line = raw
    for m in SOULVER_REF_RE.finditer(raw):  # read as "line2", keeping every column in place
        start, end = m.span(1)
        line = line[: m.start()] + " " * (start - m.start()) + m[1] + " " + line[m.end() :]
        res.spans += [(m.start(), start, "comment"), (end, m.end(), "comment")]
    comment_at = line.find("//")
    if note_at is not None and (comment_at == -1 or note_at < comment_at):
        comment_at = note_at
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
        ctx.invalid_variables.clear()
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
        tokens = _expression_tokens(body, offset, ctx, res)
        if tokens is None:
            if var_name:
                ctx.invalidate_var(var_name)
            return res
        items = classify(tokens, ctx)
    # each variable's value as the line sees it, before an assignment changes it
    seen = {id(it): ctx.variables.get(it.key) for it in items if it.kind == "var"}
    plain: set[int] = set()  # "if", "to", "in" in prose: not coloured as keywords
    moves = timeline if labelled and not var_name else None
    skipped: set[int] = set()  # what the maths left out, as in the 4 of "4 Car $200"
    continues = offset == 0 and CONTINUE_RE.match(line) is not None  # no label, name, list mark
    _evaluate_items(res, items, var_name, op, ctx, opts, plain, skipped, continues, moves)
    if res.kind != "value":
        if var_name:
            ctx.invalidate_var(var_name)
        plain = {id(it) for it in items if it.kind == "kw" and it.key in SOFT}
    for it in items:
        item_id = id(it)
        cls = SPAN_CLASSES.get(it.kind)
        if cls and item_id not in plain and it.end > it.start:
            if item_id in skipped:
                cls = "comment"
            res.spans.append((it.start, it.end, cls))
        if (
            item_id not in skipped
            and (value := seen.get(item_id)) is not None
            and (text := _format(value, opts))
        ):
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
        if var_name and any(item.tok.kind == "WORD" for item in items):
            res.diagnostic = Diagnostic("expected a value")
        return
    last = items[-1]
    if last.kind == "op" and last.key in SYMBOL_OPERATORS:
        res.kind = "unfinished"
        return
    # a line starting with an operator continues from the answer just above it
    above = ctx.line_values[-1] if ctx.line_values else None
    continued = continues and above is not None and meaningful[0].kind == "op"
    if continued:
        meaningful.insert(0, _prev_item(meaningful[0]))
    try:
        if var_name and op in ("+=", "-="):
            key = var_key(var_name)
            if key in ctx.invalid_variables:
                raise CalcError("{0} has no value", ctx.var_names.get(key, var_name))
            if key not in ctx.variables:
                raise ParseError("{0} is not defined", var_name)
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
            res.kind = "text"
            return
        if timeline is not None and not res.is_total:
            value = timeline.advance(value, ctx.rates)  # a labelled duration moves it
    except DiagnosticError as exc:
        function_call = len(meaningful) > 1 and (
            meaningful[0].kind == "fn" and meaningful[1].key == "("
        )
        calculation = (
            isinstance(exc, CalcError)
            or var_name
            or function_call
            or any(item.kind in VALUE_KINDS or item.key in VALUE_KEYWORDS for item in meaningful)
        )
        _no_answer(res, exc.diagnostic if calculation else None)
        return
    except ArithmeticError, ValueError:
        _no_answer(res, Diagnostic("could not calculate this line"))
        return
    try:
        text = format_value(value, opts)
    except ArithmeticError, ValueError:  # 1e999999 as % overflows while formatting
        _no_answer(res, Diagnostic("number too large"))
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
            tagged_lines = ctx.tags.setdefault(it.key, [])
            if not tagged_lines or tagged_lines[-1] != line:
                tagged_lines.append(line)


def _aggregate_of(items: list[Item]) -> tuple[str, bool]:
    """What a line like total or average works out ("sum", "avg"...), or "" if it isn't
    one, and whether it works on tagged lines, as "total of #food" does. "total of 3; 4"
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
