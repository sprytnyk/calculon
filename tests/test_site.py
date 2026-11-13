"""The website in docs/ shows answers from Calculon's engine; they must still be right."""

from scripts.build_site import build


def test_site_examples_are_up_to_date() -> None:
    for path, text in build().items():
        assert path.read_text(encoding="utf-8") == text, f"{path.name} is stale: run make site"
