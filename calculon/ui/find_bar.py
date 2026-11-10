"""Find in the open sheet (Ctrl+F): a slim bar under the sheet."""

from collections.abc import Callable

from PySide6.QtCore import QEvent, QObject, Qt
from PySide6.QtGui import QKeyEvent
from PySide6.QtWidgets import QHBoxLayout, QLabel, QLineEdit, QToolButton, QWidget

from . import icons
from .editor import SheetEdit


class FindBar(QWidget):
    def __init__(self, editor: SheetEdit, tr: Callable[..., str]):
        super().__init__()
        self.setObjectName("findBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground)
        self.editor = editor
        self.tr_ = tr
        self._start = 0  # where the cursor was when the search began
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 6, 10, 6)
        layout.setSpacing(4)
        self.field = QLineEdit()
        self.field.setObjectName("findField")
        self.field.setClearButtonEnabled(True)
        self.field.textChanged.connect(self._search)
        self.field.installEventFilter(self)
        self.count = QLabel()
        self.count.setObjectName("findCount")
        self.prev = self._button("caret_up", lambda: self.step(backward=True))
        self.next = self._button("caret_down", lambda: self.step())
        self.close_button = self._button("close", self.close_bar)
        layout.addWidget(self.field, 1)
        layout.addWidget(self.count)
        layout.addSpacing(4)
        layout.addWidget(self.prev)
        layout.addWidget(self.next)
        layout.addWidget(self.close_button)
        editor.cursorPositionChanged.connect(self._update_count)
        editor.textChanged.connect(self._update_count)
        self.retranslate()
        self.hide()

    def _button(self, icon: str, slot) -> QToolButton:
        button = QToolButton()
        button.setObjectName("findButton")
        button.setIcon(icons.icon(icon))
        button.setAutoRaise(True)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.clicked.connect(slot)
        return button

    def retranslate(self) -> None:
        self.field.setPlaceholderText(self.tr_("find_placeholder"))
        self.prev.setToolTip(f"{self.tr_('find_previous')} (Shift+Enter)")
        self.next.setToolTip(f"{self.tr_('find_next')} (Enter)")
        self.close_button.setToolTip(self.tr_("find_close"))
        for name, button in (("caret_up", self.prev), ("caret_down", self.next)):
            button.setIcon(icons.icon(name))
        self.close_button.setIcon(icons.icon("close"))
        self._update_count()

    def open(self) -> None:
        cur = self.editor.textCursor()
        picked = cur.selectedText()
        self._start = cur.selectionStart()
        self.show()
        if picked and " " not in picked:  # a selection within one line
            self.field.setText(picked)
        self.field.setFocus()
        self.field.selectAll()
        self.editor.set_find(self.field.text())
        self._update_count()

    def close_bar(self) -> None:
        self.hide()
        self.editor.set_find("")
        self.editor.setFocus()

    def step(self, backward: bool = False) -> None:
        if not self.isVisible():
            self.open()
            return
        self.editor.find_next(backward)
        self._update_count()

    def sheet_changed(self) -> None:
        """Another sheet is open: search it from the top."""
        if self.isVisible():
            self._start = 0
            self.editor.set_find(self.field.text())
            self._update_count()

    def _search(self, text: str) -> None:
        self.editor.set_find(text)
        self.editor.find_next(start=self._start)
        self._update_count()

    def _update_count(self) -> None:
        if not self.isVisible() or not self.field.text():
            self.count.setText("")
            return
        n, total = self.editor.match_count()
        if total == 0:
            self.count.setText(self.tr_("find_none"))
        elif n:
            self.count.setText(self.tr_("find_count", n=n, total=total))
        else:
            self.count.setText(self.tr_("find_count", n="–", total=total))

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        if obj is self.field and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            if event.key() == Qt.Key.Key_Escape:
                self.close_bar()
                return True
            if event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
                self.step(backward=bool(event.modifiers() & Qt.KeyboardModifier.ShiftModifier))
                return True
        return super().eventFilter(obj, event)
