"""The website in docs/ shows answers from Calculon's engine; they must still be right."""

from calculon.paths import ARROWS
from scripts.build_site import build
from scripts.make_arrows import build as build_arrows


def test_site_examples_are_up_to_date() -> None:
    for path, text in build().items():
        assert path.read_text(encoding="utf-8") == text, f"{path.name} is stale: run make site"


def test_arrow_files_are_up_to_date() -> None:
    """The stylesheet points at these files, so each theme colour needs its own."""
    files = build_arrows()
    for path, data in files.items():
        assert path.is_file() and path.read_bytes() == data, (
            f"{path.name} is stale: run make arrows"
        )
    assert set(files) == set(ARROWS.glob("*.svg")), "arrows don't match the themes: run make arrows"
