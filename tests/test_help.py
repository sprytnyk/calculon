from dataclasses import replace
from pathlib import Path

import pytest

from calculon.engine import FormatOptions, evaluate_sheet
from calculon.engine.format import LANGUAGE_NUMBER_STYLES
from calculon.engine.interpreter import FUNCTIONS, ROUNDERS
from tests.test_engine import CONFIG, RATES

HELP = Path(__file__).parent.parent / "calculon" / "help"


@pytest.mark.parametrize("lang", ["en", "uk"])
def test_every_help_example_has_an_answer(lang: str) -> None:
    text = (HELP / f"help_{lang}.txt").read_text(encoding="utf-8")
    style = LANGUAGE_NUMBER_STYLES[lang]
    opts = FormatOptions(number_style=style, lang=lang)
    res = evaluate_sheet(text, RATES, replace(CONFIG, number_style=style), opts)
    missing = [
        src
        for src, line in zip(text.split("\n"), res.lines, strict=True)
        if src.strip() and not src.lstrip().startswith(("#", "//", "---")) and not line.text
    ]
    assert missing == []


def test_ukrainian_help_uses_no_english_words() -> None:
    """Formula words in the Ukrainian help are Ukrainian; function names may stay Latin."""
    text = (HELP / "help_uk.txt").read_text(encoding="utf-8")
    opts = FormatOptions(number_style="space_comma", lang="uk")
    res = evaluate_sheet(text, RATES, replace(CONFIG, number_style="space_comma"), opts)
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
    text = (HELP / f"help_{lang}.txt").read_text(encoding="utf-8")
    style = LANGUAGE_NUMBER_STYLES[lang]
    opts = FormatOptions(number_style=style, lang=lang)
    res = evaluate_sheet(text, RATES, replace(CONFIG, number_style=style), opts)
    refs = [
        line.text
        for src, line in zip(text.split("\n"), res.lines, strict=True)
        if src.startswith(("line1", "рядок1"))
    ]
    assert refs == ["200"]
