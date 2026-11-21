"""Help → Keyboard Shortcuts: every shortcut, read from the menus so the list never drifts."""

from PySide6.QtCore import QSize, Qt
from PySide6.QtGui import QAction, QFont, QKeySequence
from PySide6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHeaderView,
    QMenuBar,
    QTreeWidget,
    QTreeWidgetItem,
    QVBoxLayout,
    QWidget,
)

from . import icons
from .vim import key_rows as vim_keys


def key_text(seq: QKeySequence | QKeySequence.StandardKey | Qt.Key | str) -> str:
    """A shortcut as this OS writes it: Ctrl+N here, ⌘N on macOS."""
    return QKeySequence(seq).toString(QKeySequence.SequenceFormat.NativeText)


def menu_shortcuts(bar: QMenuBar) -> list[tuple[str, list[tuple[QAction, str]]]]:
    """(menu title, [(action, shortcut text)]) for each menu, skipping actions without keys."""
    out = []
    for top in bar.actions():
        menu = top.menu()
        if menu is None:
            continue
        rows = []
        for act in menu.actions():
            keys = [key_text(s) for s in act.shortcuts() if not s.isEmpty()]
            if label := act.property("shortcut_label"):
                keys.append(label)
            if keys and act.isVisible():
                rows.append((act, ", ".join(keys)))
        if rows:
            out.append((top.text().replace("&", ""), rows))
    return out


def shortcut_sections(bar: QMenuBar, tr, vim: bool) -> list[tuple[str, list[tuple[str, str, str]]]]:
    """(section title, [(icon name, action, keys)]) for the window; every row has an icon."""
    sections = [
        (
            title,
            [
                (a.property("icon_name"), a.text().split("\t")[0].replace("&", ""), keys)
                for a, keys in rows
            ],
        )
        for title, rows in menu_shortcuts(bar)
    ]
    line_keys = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    sections += [
        (
            tr("shortcuts_sidebar"),
            [
                ("sheet", tr("shortcuts_open"), key_text(Qt.Key.Key_Return)),
                ("rename", tr("rename"), key_text(Qt.Key.Key_F2)),
                ("trash", tr("move_to_trash"), key_text(QKeySequence.StandardKey.Delete)),
            ],
        ),
        (
            tr("shortcuts_editor"),
            [
                (
                    "delete_back",
                    tr("delete_line_start"),
                    key_text(line_keys | Qt.Key.Key_Backspace),
                ),
                (
                    "delete_forward",
                    tr("delete_line_end"),
                    key_text(line_keys | Qt.Key.Key_Delete),
                ),
                ("insert_reference", tr("reference_answer"), tr("double_click_answer")),
            ],
        ),
        (
            tr("shortcuts_autocomplete"),
            [
                (
                    "accept",
                    tr("shortcuts_insert"),
                    f"{key_text(Qt.Key.Key_Return)}, {key_text(Qt.Key.Key_Tab)}",
                ),
                ("dismiss", tr("shortcuts_dismiss"), key_text(Qt.Key.Key_Escape)),
            ],
        ),
    ]
    if vim:
        sections.append(
            (tr("shortcuts_vim"), [(icon, tr(name), keys) for icon, name, keys in vim_keys()])
        )
    return sections


class ShortcutsDialog(QDialog):
    def __init__(self, bar: QMenuBar, tr, parent: QWidget | None = None, vim: bool = False):
        super().__init__(parent)
        self.setWindowTitle(tr("shortcuts"))
        self.setWindowIcon(icons.icon("shortcuts"))
        self.tree = QTreeWidget()
        self.tree.setObjectName("shortcuts")
        # breathing room: a framed list with padded rows and header
        self.tree.setStyleSheet(
            """
            QTreeWidget#shortcuts { border: 1px solid palette(mid); border-radius: 12px;
                                    padding: 6px 4px; }
            QTreeWidget#shortcuts::item { padding: 4px 12px; }
            QTreeWidget#shortcuts QHeaderView::section {
                padding: 8px 16px; border: none; border-bottom: 1px solid palette(mid);
                background: transparent; font-weight: 600; }
            """
        )
        self.tree.setColumnCount(2)
        self.tree.setHeaderLabels([tr("shortcuts_action"), tr("shortcuts_keys")])
        self.tree.headerItem().setTextAlignment(
            1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
        )
        self.tree.setRootIsDecorated(False)
        self.tree.setSelectionMode(QTreeWidget.SelectionMode.NoSelection)
        self.tree.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        header = self.tree.header()
        header.setStretchLastSection(False)
        header.setSectionResizeMode(0, QHeaderView.ResizeMode.Stretch)
        header.setSectionResizeMode(1, QHeaderView.ResizeMode.ResizeToContents)

        bold = QFont(self.tree.font())
        bold.setBold(True)
        for title, rows in shortcut_sections(bar, tr, vim):
            head = QTreeWidgetItem([title, ""])
            head.setFont(0, bold)
            head.setSizeHint(0, QSize(0, 36))  # a little air above each section
            head.setTextAlignment(0, Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignBottom)
            self.tree.addTopLevelItem(head)
            for icon, text, keys in rows:
                item = QTreeWidgetItem([text, keys])
                item.setIcon(0, icons.icon(icon))
                item.setTextAlignment(
                    1, Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter
                )
                self.tree.addTopLevelItem(item)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.rejected.connect(self.reject)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(20, 20, 20, 16)
        layout.setSpacing(14)
        layout.addWidget(self.tree)
        layout.addWidget(buttons)
        # as wide as the longest row, which depends on the language and the font
        tree = self.tree
        columns = tree.sizeHintForColumn(0) + tree.sizeHintForColumn(1)
        scrollbar = tree.verticalScrollBar().sizeHint().width()
        tree.setMinimumWidth(columns + scrollbar + 2 * tree.frameWidth())
        self.resize(600, 740)

    def rows(self) -> list[tuple[str, str]]:
        return [
            (self.tree.topLevelItem(i).text(0), self.tree.topLevelItem(i).text(1))
            for i in range(self.tree.topLevelItemCount())
        ]
