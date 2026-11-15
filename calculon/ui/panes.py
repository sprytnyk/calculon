"""Vim mode outside the sheet's text. Ctrl+W h and Ctrl+W l move between the sheet
list, the sheet and its answers, as between vim's windows. In the list and the answers,
j and k move and Enter opens or copies. In the sheet, side-vim reads Ctrl+W and calls
jump through its window hook."""

from PySide6.QtCore import QEvent, QObject, Qt, Signal
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QApplication, QWidget
from side_vim.keys import key_token, map_layout

from .editor import SheetEdit
from .sidebar import Sidebar

WINDOW = "<C-w>"
# the key after Ctrl+W, read the way side-vim reads it in the sheet
WINDOW_KEYS = {"<C-h>": "h", "<Left>": "h", "<C-l>": "l", "<Right>": "l"}
STEPS = {"h": -1, "l": 1}
DOWN = "j"
UP = "k"
ENTER = "<CR>"


class PaneKeys(QObject):
    """Vim keys on the sheet list and on the answers."""

    pending_changed = Signal(str)  # "^W" while it waits for the key after Ctrl+W

    def __init__(self, sidebar: Sidebar, editor: SheetEdit, parent: QObject | None = None):
        super().__init__(parent)
        self.sidebar = sidebar
        self.editor = editor
        self._waiting = False
        sidebar.tree.installEventFilter(self)
        editor.results.installEventFilter(self)
        editor.vim_window.connect(lambda key: self.jump(editor, key))

    def jump(self, pane: QObject, key: str) -> None:
        """Ctrl+W and key, pressed in pane: h goes to the pane on the left, l to the
        one on the right. Other keys, and a step past the last pane, do nothing."""
        panes: list[QWidget] = [self.sidebar.tree] if self.sidebar.isVisible() else []
        panes += [self.editor, self.editor.results]
        step = STEPS.get(key)
        here = next((i for i, widget in enumerate(panes) if widget is pane), None)
        if step is None or here is None:
            return
        if 0 <= here + step < len(panes):
            panes[here + step].setFocus(Qt.FocusReason.OtherFocusReason)

    def eventFilter(self, watched: QObject, event: QEvent) -> bool:  # noqa: N802
        kind = event.type()
        if kind == QEvent.Type.FocusOut and self._waiting:
            self._wait(False)  # a click elsewhere, or another window, drops a Ctrl+W
            return False
        key_events = (QEvent.Type.KeyPress, QEvent.Type.ShortcutOverride)
        if kind not in key_events or not self.editor.vim_on():
            return False
        assert isinstance(event, QKeyEvent)
        token = self._token(event)
        if token is None:
            return False  # Shift on its own, say
        if kind == QEvent.Type.ShortcutOverride:
            # after Ctrl+W every key is ours, even Ctrl+L, Calculon's own shortcut
            if self._waiting or token == WINDOW:
                event.accept()
                return True
            return False
        if self._waiting:
            self._wait(False)
            self.jump(watched, WINDOW_KEYS.get(token, token))
            return True  # a key that isn't h or l ends the wait and does nothing, as in vim
        if token == WINDOW:
            self._wait(True)
            return True
        if watched is self.sidebar.tree:
            return self._list_key(token)
        return self._results_key(token)

    def _token(self, event: QKeyEvent) -> str | None:
        """The key as side-vim reads it, Ukrainian letters included."""
        token = key_token(event)
        vim = self.editor.vim
        return map_layout(token, vim.layout_map) if token and vim else token

    def _wait(self, on: bool) -> None:
        self._waiting = on
        self.pending_changed.emit("^W" if on else "")

    def _list_key(self, token: str) -> bool:
        if token in (DOWN, UP):
            key = Qt.Key.Key_Down if token == DOWN else Qt.Key.Key_Up
            # the list's own arrow keys, so j and k skip the section titles as arrows do
            arrow = QKeyEvent(QEvent.Type.KeyPress, key, Qt.KeyboardModifier.NoModifier)
            QApplication.sendEvent(self.sidebar.tree, arrow)
            return True
        if token == ENTER:
            if self.sidebar.open_current():
                self.editor.setFocus(Qt.FocusReason.OtherFocusReason)
            return True
        return False

    def _results_key(self, token: str) -> bool:
        results = self.editor.results
        if token in (DOWN, UP):
            results.step(forward=token == DOWN)
            return True
        if token == ENTER:
            results.copy_line(self.editor.textCursor().blockNumber())
            return True
        return False
