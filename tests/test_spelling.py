"""Spell check: picking words out of a line, the user's own words, and real Hunspell.

Windows' spell checker has its own tests in test_windows_spelling.py.
"""

import sys
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


class Fake:
    """Knows only "rent"; no Hunspell needed."""

    def check(self, word: str) -> bool:
        return word == "rent"

    def suggest(self, word: str) -> list[str]:
        return ["rent"]

    def close(self) -> None:
        pass


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


def test_install_hint_names_what_is_missing(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(spelling, "platform_key", lambda: "linux")
    nothing = Status(library=False)
    assert nothing.install_command() == (
        "sudo apt install libhunspell-1.7-0 hunspell-en-us hunspell-uk"
    )
    no_uk = Status(library=True, dictionaries={"en-GB": "/x/en_GB"})
    assert no_uk.available and no_uk.missing == ["uk"]
    assert no_uk.install_command() == "sudo apt install hunspell-uk"
    monkeypatch.setattr(spelling, "platform_key", lambda: "darwin")
    assert nothing.install_command() == ""  # macOS: Homebrew, see the README
    monkeypatch.setattr(spelling, "platform_key", lambda: "win32")
    assert nothing.install_command() == ""  # Windows: Settings, see the hint


def test_probe_finds_hunspell_files(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("en_GB", "en_US", "uk_UA"):
        (tmp_path / f"{name}.aff").write_text("SET UTF-8\n")
        (tmp_path / f"{name}.dic").write_text("0\n")
    monkeypatch.setattr(spelling, "platform_key", lambda: "linux")
    monkeypatch.setattr(spelling, "dictionary_dirs", lambda: [tmp_path])
    status = spelling.probe()
    assert status.english == ("en-US", "en-GB")
    assert status.selected() == {"en": str(tmp_path / "en_US"), "uk": str(tmp_path / "uk_UA")}


def test_hunspell_selects_an_installed_english_variant(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    user = tmp_path / "user"
    system = tmp_path / "system"
    for directory, names in ((user, ("en_GB",)), (system, ("en_US", "en_GB", "uk_UA"))):
        directory.mkdir()
        for name in names:
            (directory / f"{name}.aff").touch()
            (directory / f"{name}.dic").touch()
    (user / "en_CA.aff").touch()  # incomplete pair
    monkeypatch.setattr(spelling, "platform_key", lambda: "linux")
    monkeypatch.setattr(spelling, "dictionary_dirs", lambda: [user, system])
    monkeypatch.setattr(spelling, "load_library", lambda: object())

    status = spelling.probe()
    assert status.english == ("en-GB", "en-US")
    british = {"en": str(user / "en_GB"), "uk": str(system / "uk_UA")}
    assert status.selected() == british  # Automatic keeps directory priority
    assert status.selected("en-US") == british | {"en": str(system / "en_US")}
    assert status.selected("en-CA") == british  # a missing preference uses Automatic


SYSTEM = spelling.probe()
needs_hunspell = pytest.mark.skipif(
    sys.platform == "win32" or SYSTEM.missing != [] or not SYSTEM.library,
    reason="needs Hunspell with en and uk",
)


@pytest.fixture(scope="module")
def real() -> Iterator[SpellChecker]:
    checker = SpellChecker.load(SYSTEM.selected())
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
    assert len(real.suggest("teh")) <= 5  # a long list made the right-click menu too tall


@needs_hunspell
def test_real_sheet_lines(real: SpellChecker) -> None:
    def bad(line: str) -> list[str]:
        return [line[a:b] for a, b in misspelled(line, real.check)]

    assert bad("Оренда квартири 12000 грн") == []
    assert bad("// бюджет на відпустку в Карпатах") == []
    assert bad("Taxi to airprot 450") == ["airprot"]
    assert bad("Продуктии на тиждень: 3500 грн") == ["Продуктии"]
