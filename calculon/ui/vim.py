"""Vim mode through side-vim, when it's installed. Calculon works the same without it."""

import sys
from enum import Enum

try:
    from side_vim import Mode, VimMode
except ImportError:  # optional until side-vim is on PyPI
    Mode = VimMode = None

AVAILABLE = VimMode is not None

# what vim shows at the bottom left; Normal mode shows nothing
LABELS = {
    "insert": "-- INSERT --",
    "visual": "-- VISUAL --",
    "visual line": "-- VISUAL LINE --",
}


def label(mode: Enum) -> str:
    return LABELS.get(mode.value, "")


def ctrl(key: str) -> str:
    """A Ctrl key as side-vim reads it: the physical Control key, also on macOS."""
    return f"⌃{key}" if sys.platform == "darwin" else f"Ctrl+{key}"


def key_rows() -> list[tuple[str, str]]:
    """(translation key, keys) for the shortcuts window, side-vim's supported keys."""
    return [
        ("vim_move", "h j k l, w b e, W B E, 0 ^ $, gg G"),
        ("vim_count", "3w, 5G, 2dd, y3j"),
        ("vim_insert", "i a I A o O"),
        ("vim_operators", "d c y"),
        ("vim_whole", "dd cc yy, x, D C"),
        ("vim_paste", "p P, J"),
        ("vim_undo", f"u, {ctrl('R')}"),
        ("vim_select", "v, V"),
        ("vim_selection", "d c y x p, o"),
        ("vim_search", "/ ?, n N"),
        ("vim_scroll_line", f"{ctrl('E')}, {ctrl('Y')}"),
        ("vim_scroll_half", f"{ctrl('D')}, {ctrl('U')}"),
        ("vim_scroll_page", f"{ctrl('F')}, {ctrl('B')}"),
        ("vim_normal", f"Esc, {ctrl('[')}"),
    ]
