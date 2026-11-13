"""Menu and sidebar icons: Phosphor Icons (MIT), duotone style, tinted to the theme.

The SVGs in assets/icons are named after what they do here; SOURCES maps them back.
"""

import tempfile
from functools import cache
from pathlib import Path

from PySide6.QtCore import QByteArray, QRectF, QStandardPaths, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from ..paths import ICONS

# our name -> Phosphor name, for updating the set later
SOURCES = {
    "sheet": "file-text",
    "new_sheet": "file-plus",
    "folder": "folder-simple",
    "new_folder": "folder-simple-plus",
    "open_folder": "folder-open",
    "settings": "gear-six",
    "quit": "sign-out",
    "undo": "arrow-u-up-left",
    "redo": "arrow-u-up-right",
    "cut": "scissors",
    "copy": "copy",
    "paste": "clipboard",
    "select_all": "selection-all",
    "comment": "chat-text",
    "copy_result": "clipboard-text",
    "copy_with_results": "copy-simple",
    "insert_total": "sigma",
    "insert_reference": "link-simple",
    "search": "magnifying-glass",
    "zoom_in": "magnifying-glass-plus",
    "zoom_out": "magnifying-glass-minus",
    "zoom_reset": "text-aa",
    "theme": "circle-half",
    "theme_dark": "moon",
    "theme_light": "sun",
    "theme_system": "monitor",
    "colours": "palette",
    "language": "globe",
    "sidebar": "sidebar-simple",
    "line_numbers": "list-numbers",
    "help": "question",
    "refresh": "arrows-clockwise",
    "about": "info",
    "pin": "push-pin",
    "unpin": "push-pin-slash",
    "rename": "pencil-simple",
    "trash": "trash",
    "empty_trash": "broom",
    "delete_forever": "x-circle",
    "restore": "arrow-counter-clockwise",
    "shortcuts": "keyboard",
    "numbers": "calculator",
    "rates": "currency-circle-dollar",
    "caret_down": "caret-down (bold)",
    "caret_up": "caret-up (bold)",
    "close": "x (bold)",
    "spell_add": "book-open-text",
    "spell_ignore": "eye-slash",
}
NAMES = frozenset(SOURCES)

# Each icon gets a colour by what it does; the theme supplies the actual shades.
GROUPS = {
    "sheet": "blue", "new_sheet": "blue", "help": "blue", "about": "blue",
    "folder": "amber", "new_folder": "amber", "open_folder": "amber",
    "cut": "violet", "copy": "violet", "paste": "violet", "select_all": "violet",
    "insert_total": "blue", "insert_reference": "blue",
    "copy_result": "green", "copy_with_results": "green", "refresh": "green", "rates": "green",
    "numbers": "amber",
    "language": "green",
    "undo": "teal", "redo": "teal", "restore": "teal",
    "search": "cyan", "zoom_in": "cyan", "zoom_out": "cyan", "zoom_reset": "cyan",
    "pin": "rose", "unpin": "rose",
    "trash": "red", "empty_trash": "red", "delete_forever": "red", "quit": "red",
    "rename": "yellow", "theme_light": "yellow",
    "spell_add": "green",
    "theme": "indigo", "colours": "violet", "theme_dark": "indigo", "shortcuts": "indigo",
}  # fmt: skip
ICON_SIZE = 20  # menus and the sidebar
FILL_OPACITY = "0.3"  # the soft second tone of the duotone icons

_palette: dict[str, str] = {"neutral": "#a3a7b1"}


def set_palette(palette: dict[str, str]) -> None:
    """Called when the theme changes; icons made afterwards use these colours."""
    _palette.clear()
    _palette.update(palette)


def color_for(name: str) -> str:
    return _palette.get(GROUPS.get(name, "neutral"), _palette.get("neutral", "#a3a7b1"))


def svg(name: str, color: str) -> bytes:
    text = (ICONS / f"{name}.svg").read_text(encoding="utf-8")
    text = text.replace('opacity="0.2"', f'opacity="{FILL_OPACITY}"')
    return text.replace("currentColor", color).encode()


def icon(name: str) -> QIcon:
    return _icon(name, color_for(name))


@cache
def _icon(name: str, color: str) -> QIcon:
    renderer = QSvgRenderer(QByteArray(svg(name, color)))
    out = QIcon()
    # sizes up to 96 so menus stay sharp on 2x screens
    for size in (16, 20, 24, 32, 40, 48, 64, 96):
        px = QPixmap(size, size)
        px.fill(Qt.GlobalColor.transparent)
        painter = QPainter(px)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        renderer.render(painter, QRectF(0, 0, size, size))
        painter.end()
        out.addPixmap(px)
    return out


def icon_file(name: str, color: str) -> str:
    """A tinted copy of an icon on disk, for stylesheets (url() can't take a colour)."""
    folder = (
        Path(
            QStandardPaths.writableLocation(QStandardPaths.StandardLocation.CacheLocation)
            or tempfile.gettempdir()
        )
        / "icons"
    )
    path = folder / f"{name}-{color.lstrip('#')}.svg"
    if not path.exists():
        folder.mkdir(parents=True, exist_ok=True)
        path.write_bytes(svg(name, color))
    return path.as_posix()
