"""Load the built-in help in the same number format as the user's sheets."""

from .engine.numbers import separators
from .paths import HELP_DIR


def read_help(language: str, number_style: str) -> str:
    path = HELP_DIR / f"help_{language}.txt"
    if not path.is_file():
        path = HELP_DIR / "help_en.txt"
    group, point = separators(number_style)
    return path.read_text(encoding="utf-8").format(group=group, point=point)
