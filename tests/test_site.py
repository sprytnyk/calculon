"""The website in docs/ shows answers from Calculon's engine; they must still be right."""

from calculon.paths import ARROWS
from scripts import build_site
from scripts.build_site import build
from scripts.make_arrows import build as build_arrows


def test_site_examples_are_up_to_date() -> None:
    for path, text in build().items():
        assert path.read_text(encoding="utf-8") == text, f"{path.name} is stale: run make site"


def test_english_rates_date_does_not_depend_on_system_locale(monkeypatch) -> None:
    class LocalizedDate:
        day, month, year = 10, 11, 2026

        def __format__(self, spec: str) -> str:
            return "листопада 2026"

    class LocalizedDatetime:
        @staticmethod
        def fromtimestamp(timestamp, timezone):
            return LocalizedDate()

    monkeypatch.setattr(build_site, "datetime", LocalizedDatetime)
    assert build_site.rates_date(build_site.rates(), "en") == "10 November 2026"


def test_arrow_files_are_up_to_date() -> None:
    """The stylesheet points at these files, so each theme colour needs its own."""
    files = build_arrows()
    for path, data in files.items():
        assert path.is_file() and path.read_bytes() == data, (
            f"{path.name} is stale: run make arrows"
        )
    assert set(files) == set(ARROWS.glob("*.svg")), "arrows don't match the themes: run make arrows"
