from decimal import Decimal

import pytest

from calculon.engine import FormatOptions, evaluate_sheet
from calculon.engine.interpreter import FUNCTIONS, ROUNDERS
from calculon.engine.numbers import NUMBER_STYLES, number_sample
from calculon.help_sheet import read_help
from tests.test_engine import CONFIG, RATES


@pytest.mark.parametrize("lang", ["en", "uk"])
@pytest.mark.parametrize("style", NUMBER_STYLES)
def test_help_examples_keep_their_values_in_every_format(lang: str, style: str) -> None:
    text = read_help(lang, style)
    opts = FormatOptions(number_style=style, lang=lang)
    res = evaluate_sheet(text, RATES, CONFIG, opts)
    base = evaluate_sheet(read_help(lang, "comma_dot"), RATES, CONFIG, FormatOptions(lang=lang))
    missing = [
        src
        for src, line in zip(text.split("\n"), res.lines, strict=True)
        if src.strip() and not src.lstrip().startswith(("#", "//", "---")) and line.value is None
    ]
    assert missing == []
    assert [line.value for line in res.lines] == [line.value for line in base.lines]
    assert res.total == base.total
    examples = dict(zip(text.splitlines(), res.lines, strict=False))
    for prefix, magnitude in (
        (number_sample(style), "1234.56"),
        ("round(", "3.14"),
        (("average of " if lang == "en" else "середнє від ") + "36;", "44.5"),
    ):
        line = next(line for src, line in examples.items() if src.startswith(prefix))
        assert line.value.mag == Decimal(magnitude)


def test_ukrainian_help_uses_no_english_words() -> None:
    """Formula words in the Ukrainian help are Ukrainian; function names may stay Latin."""
    text = read_help("uk", "space_comma")
    opts = FormatOptions(number_style="space_comma", lang="uk")
    res = evaluate_sheet(text, RATES, CONFIG, opts)
    english = [
        src[start:end]
        for src, line in zip(text.split("\n"), res.lines, strict=True)
        for start, end, cls in line.spans
        if cls == "keyword"
        and src[start:end].isascii()
        and src[start:end].lower() not in set(FUNCTIONS) | ROUNDERS
    ]
    assert english == []


@pytest.mark.parametrize("lang", ["en", "uk"])
def test_help_line_reference_points_at_the_100_line(lang: str) -> None:
    """Adding a line above it shifts the numbers; the example must still double 100."""
    text = read_help(lang, "comma_dot")
    res = evaluate_sheet(text, RATES, CONFIG, FormatOptions(lang=lang))
    refs = [
        line.text
        for src, line in zip(text.split("\n"), res.lines, strict=True)
        if src.startswith(("line1", "рядок1"))
    ]
    assert refs == ["200"]
