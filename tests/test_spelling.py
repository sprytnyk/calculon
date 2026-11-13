"""Spell check: picking words out of a line, the user's own words, and real Hunspell."""

from collections.abc import Iterator
from pathlib import Path

import pytest

from calculon import spelling
from calculon.spelling import SpellChecker, Status, misspelled, words


def found(text: str) -> list[str]:
    return [w for _start, _end, w in words(text)]


def test_words_are_prose_only() -> None:
    assert found("Hotel in Lviv 3 nights") == ["Hotel", "in", "Lviv", "nights"]
    assert found("x2 abc123 total_2 _x VAT USD a") == []  # names, codes, caps, one letter
    assert found("see https://exmaple.com, me@exmaple.com or ~/tmp/nottes") == ["see", "or"]


def test_words_keep_apostrophes_and_hyphens_inside() -> None:
    assert found("п'ять пʼять п’ять e-mail 'quoted'") == [
        "п'ять",
        "пʼять",
        "п’ять",
        "e-mail",
        "quoted",
    ]


def test_misspelled_leaves_out_skipped_ranges() -> None:
    text = "teh rent teh"
    assert misspelled(text, lambda w: w != "teh") == [(0, 3), (9, 12)]
    assert misspelled(text, lambda w: w != "teh", skip=[(0, 3)]) == [(9, 12)]


def test_language_goes_by_letters() -> None:
    assert spelling.language_of("оренда") == "uk"
    assert spelling.language_of("rent") == "en"


def test_without_dictionaries_everything_passes() -> None:
    checker = SpellChecker()
    assert checker.check("hotell")
    assert checker.suggest("hotell") == []


class Fake(spelling.Dictionary):
    """Knows only "rent"; no Hunspell needed."""

    def __init__(self) -> None:
        self.encoding = "utf-8"

    def check(self, word: str) -> bool:
        return word == "rent"

    def suggest(self, word: str) -> list[str]:
        return ["rent"]


def test_own_words_ignore_and_vocabulary(tmp_path: Path) -> None:
    file = tmp_path / "data" / "words.txt"
    checker = SpellChecker(file, extra=["uah", "km"])
    checker.dictionaries["en"] = Fake()
    assert not checker.check("rnet")
    assert checker.check("UAH") and checker.check("km")  # Calculon's own words, any case
    assert checker.check("Kyiv")  # built in

    checker.add("rnet")
    assert checker.check("rnet") and checker.check("Rnet")  # lower case: any case
    checker.add("GmbH")
    assert checker.check("GmbH") and not checker.check("gmbh")  # capitals: as written
    assert file.read_text(encoding="utf-8") == "rnet\nGmbH\n"
    assert SpellChecker(file).own >= {"rnet", "GmbH"}  # kept for the next start

    checker.ignore("zzz")
    assert checker.check("zzz")
    assert "zzz" not in SpellChecker(file).own  # only until Calculon closes


def test_find_dictionary_prefers_us_english(tmp_path: Path) -> None:
    for name in ("en_GB", "en_US", "uk_UA"):
        (tmp_path / f"{name}.aff").write_text("SET UTF-8\n")
        (tmp_path / f"{name}.dic").write_text("0\n")
    (tmp_path / "en_CA.aff").write_text("")  # no .dic: not a dictionary
    assert spelling.find_dictionary("en", [tmp_path]) == tmp_path / "en_US"
    assert spelling.find_dictionary("uk", [tmp_path]) == tmp_path / "uk_UA"
    assert spelling.find_dictionary("uk", [tmp_path / "nowhere"]) is None


def test_install_hint_names_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spelling, "platform_key", lambda: "linux")
    nothing = Status(supported=True, library=False)
    assert nothing.install_command() == (
        "sudo apt install libhunspell-1.7-0 hunspell-en-us hunspell-uk"
    )
    no_uk = Status(supported=True, library=True, dictionaries={"en": Path("/x/en_US")})
    assert no_uk.available and no_uk.missing == ["uk"]
    assert no_uk.install_command() == "sudo apt install hunspell-uk"
    monkeypatch.setattr(spelling, "platform_key", lambda: "darwin")
    assert nothing.install_command() == ""  # macOS: Homebrew, see the README


SYSTEM = spelling.probe()
needs_hunspell = pytest.mark.skipif(
    SYSTEM.missing != [] or not SYSTEM.library, reason="needs Hunspell with en and uk"
)


@pytest.fixture(scope="module")
def real() -> Iterator[SpellChecker]:
    checker = SpellChecker.load(SYSTEM)
    yield checker
    checker.close()


@needs_hunspell
def test_real_hunspell_checks_both_languages(real: SpellChecker) -> None:
    for good in ("hotel", "Hotel", "groceries", "оренда", "Оренда", "Львів", "ґанок"):
        assert real.check(good), good
    for bad in ("hotell", "recieve", "оредна", "мобілний", "Продуктии"):
        assert not real.check(bad), bad
    for apostrophe in ("п'ять", "пʼять", "п’ять", "з'їсти"):
        assert real.check(apostrophe), apostrophe


@needs_hunspell
def test_real_hunspell_suggests(real: SpellChecker) -> None:
    assert "hotel" in real.suggest("hotell")
    assert "receive" in real.suggest("recieve")
    assert "оренда" in real.suggest("оредна")
    assert "мобільний" in real.suggest("мобілний")


@needs_hunspell
def test_real_sheet_lines(real: SpellChecker) -> None:
    def bad(line: str) -> list[str]:
        return [line[a:b] for a, b in misspelled(line, real.check)]

    assert bad("Оренда квартири 12000 грн") == []
    assert bad("// бюджет на відпустку в Карпатах") == []
    assert bad("Taxi to airprot 450") == ["airprot"]
    assert bad("Продуктии на тиждень: 3500 грн") == ["Продуктии"]
