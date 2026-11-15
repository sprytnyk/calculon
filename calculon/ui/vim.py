"""What Calculon shows for side-vim's vim mode: the mode label and the keys."""

import sys

from side_vim import Mode

# what vim shows at the bottom left; Normal mode shows nothing
LABELS = {
    "insert": "-- INSERT --",
    "visual": "-- VISUAL --",
    "visual line": "-- VISUAL LINE --",
}


def label(mode: Mode) -> str:
    return LABELS.get(mode.value, "")


def ctrl(key: str) -> str:
    """A Ctrl key as side-vim reads it: the physical Control key, also on macOS."""
    return f"⌃{key}" if sys.platform == "darwin" else f"Ctrl+{key}"


def key_rows() -> list[tuple[str, str, str]]:
    """(icon, translation key, keys) for the shortcuts window, side-vim's supported keys."""
    return [
        ("move", "vim_move", "h j k l, w b e, W B E, 0 ^ $, gg G"),
        ("count", "vim_count", "3w, 5G, 2dd, y3j"),
        ("type", "vim_insert", "i a I A o O"),
        ("operator", "vim_operators", "d c y"),
        ("line", "vim_whole", "dd cc yy, x, D C"),
        ("paste", "vim_paste", "p P, J"),
        ("operator", "vim_replace", "r, 3rx"),
        ("undo", "vim_undo", f"u, {ctrl('R')}"),
        ("select_all", "vim_select", "v, V"),
        ("edit_selection", "vim_selection", "d c y x p r, o"),
        ("search", "vim_search", "/ ?, n N"),
        ("spell_add", "vim_spell_next", "]s [s"),
        ("spell_add", "vim_spell_suggest", "z="),
        ("spell_add", "vim_spell_add", "zg, zG"),
        ("scroll", "vim_scroll_line", f"{ctrl('E')}, {ctrl('Y')}"),
        ("scroll", "vim_scroll_half", f"{ctrl('D')}, {ctrl('U')}"),
        ("scroll", "vim_scroll_page", f"{ctrl('F')}, {ctrl('B')}"),
        ("vim", "vim_normal", f"Esc, {ctrl('[')}"),
        ("sidebar", "vim_panes", f"{ctrl('W')} h, {ctrl('W')} l"),
        ("move", "vim_list_move", "j k"),
        ("accept", "vim_list_enter", "Enter"),
    ]
