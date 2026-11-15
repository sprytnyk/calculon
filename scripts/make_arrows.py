"""Make assets/arrows: the dropdown and number field arrows in each theme's muted colour.

Stylesheets can only show an image from a file and can't recolour it, so the app ships
one file per colour instead of writing them at run time.

Run with: uv run python -m scripts.make_arrows
"""

from pathlib import Path

from calculon.paths import ARROWS
from calculon.ui.icons import ARROW_NAMES, arrow_file, svg
from calculon.ui.theme import PALETTES


def build() -> dict[Path, bytes]:
    colors = sorted({theme.muted for pair in PALETTES.values() for theme in pair})
    # Phosphor's files end without a newline; add one so pre-commit leaves them be
    return {
        arrow_file(name, color): svg(name, color).rstrip(b"\n") + b"\n"
        for name in ARROW_NAMES
        for color in colors
    }


def main() -> None:
    files = build()
    ARROWS.mkdir(exist_ok=True)
    for old in ARROWS.glob("*.svg"):
        if old not in files:
            old.unlink()
            print(f"removed {old.name}")
    for path, data in files.items():
        path.write_bytes(data)
        print(f"wrote {path.name}")


if __name__ == "__main__":
    main()
