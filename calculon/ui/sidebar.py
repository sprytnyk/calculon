"""The sheet list: pinned sheets, folders and sheets, help and trash."""

from __future__ import annotations

from PySide6.QtCore import (
    QFileSystemWatcher,
    QPoint,
    QRectF,
    QSettings,
    QSize,
    Qt,
    QTimer,
    Signal,
)
from PySide6.QtGui import QAction, QDropEvent, QFont, QIcon, QKeySequence, QPainter, QPalette
from PySide6.QtWidgets import (
    QAbstractItemView,
    QHBoxLayout,
    QLineEdit,
    QMenu,
    QStyle,
    QToolButton,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from ..storage import TRASH_DIR, SheetStore
from . import icons

ROLE = Qt.ItemDataRole.UserRole
# item kinds
SECTION = "section"
SHEET = "sheet"
FOLDER = "folder"
PINNED = "pinned"
HELP = "help"
TRASH = "trash"
TRASHED = "trashed"


class SheetTree(QTreeWidget):
    dropped = Signal(object, object, int)  # dragged item data, target data, position

    def __init__(self, parent: QWidget | None = None):
        super().__init__(parent)
        self.setObjectName("sheetTree")
        self.setHeaderHidden(True)
        self.setMouseTracking(True)
        self.setDragDropMode(QAbstractItemView.DragDropMode.InternalMove)
        self.setDefaultDropAction(Qt.DropAction.MoveAction)
        self.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.setIndentation(14)
        self.setAnimated(True)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)

    def drawRow(self, painter: QPainter, option, index) -> None:  # noqa: N802
        """One rounded highlight across the whole row, indentation included."""
        selected = self.selectionModel().isSelected(index)
        hovered = bool(option.state & QStyle.StateFlag.State_MouseOver)
        if selected or hovered:
            role = QPalette.ColorRole.Highlight if selected else QPalette.ColorRole.AlternateBase
            painter.save()
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            painter.setPen(Qt.PenStyle.NoPen)
            painter.setBrush(self.palette().color(role))
            rect = QRectF(option.rect).adjusted(2, 1, -2, -1)
            rect.setLeft(2)
            painter.drawRoundedRect(rect, 6, 6)
            painter.restore()
        super().drawRow(painter, option, index)

    def dropEvent(self, event: QDropEvent) -> None:  # noqa: N802
        dragged = self.currentItem()
        target = self.itemAt(event.position().toPoint())
        if dragged is None:
            event.ignore()
            return
        pos = self.dropIndicatorPosition()
        event.setDropAction(Qt.DropAction.IgnoreAction)
        event.accept()
        self.dropped.emit(
            dragged.data(0, ROLE),
            target.data(0, ROLE) if target else None,
            int(pos.value),
        )


class Sidebar(QWidget):
    open_sheet = Signal(str)  # rel path
    open_help = Signal()
    open_trashed = Signal(str)  # name in trash
    new_sheet = Signal(str)  # folder
    new_folder = Signal(str)  # parent folder
    rename = Signal(str)
    trash = Signal(str)
    restore = Signal(str)
    delete_forever = Signal(str)
    empty_trash = Signal()
    show_in_folder = Signal(str)
    changed = Signal()  # something changed on disk

    def __init__(self, store: SheetStore, tr, parent: QWidget | None = None):
        super().__init__(parent)
        self.store = store
        self.tr_ = tr
        saved = QSettings().value("sidebar/expanded", [])
        self.expanded: set[str] = {str(k) for k in (saved if isinstance(saved, list) else [saved])}
        self.expanded.discard("")
        self.current: tuple[str, str] | None = None  # (kind, key) of the open sheet
        layout = QVBoxLayout(self)
        layout.setContentsMargins(8, 8, 8, 4)
        layout.setSpacing(6)
        self.search = QLineEdit()
        self.search.setObjectName("search")
        self.search.setClearButtonEnabled(True)
        self.search.textChanged.connect(self.rebuild)
        layout.addWidget(self.search)
        self.tree = SheetTree()
        self.tree.itemClicked.connect(self._clicked)
        self.tree.itemActivated.connect(self._clicked)
        self.tree.itemExpanded.connect(lambda it: self._remember(it, True))
        self.tree.itemCollapsed.connect(lambda it: self._remember(it, False))
        self.tree.customContextMenuRequested.connect(self._menu)
        self.tree.dropped.connect(self._dropped)
        layout.addWidget(self.tree, 1)
        buttons = QHBoxLayout()
        buttons.setContentsMargins(0, 0, 0, 0)
        self.btn_sheet = QToolButton()
        self.btn_sheet.setObjectName("sidebarButton")
        self.btn_sheet.clicked.connect(lambda: self.new_sheet.emit(self.current_folder()))
        self.btn_folder = QToolButton()
        self.btn_folder.setObjectName("sidebarButton")
        self.btn_folder.clicked.connect(lambda: self.new_folder.emit(self.current_folder()))
        buttons.addWidget(self.btn_sheet)
        buttons.addWidget(self.btn_folder)
        buttons.addStretch()
        layout.addLayout(buttons)
        self._rename_action = QAction(self)
        self._rename_action.setShortcut(QKeySequence(Qt.Key.Key_F2))
        self._rename_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._rename_action.triggered.connect(self._rename_selected)
        self._delete_action = QAction(self)
        self._delete_action.setShortcut(QKeySequence(QKeySequence.StandardKey.Delete))
        self._delete_action.setShortcutContext(Qt.ShortcutContext.WidgetWithChildrenShortcut)
        self._delete_action.triggered.connect(self._trash_selected)
        self.tree.addAction(self._rename_action)
        self.tree.addAction(self._delete_action)
        self.watcher = QFileSystemWatcher(self)
        self.watcher.directoryChanged.connect(lambda _p: self._debounce.start())
        self._debounce = QTimer(self)
        self._debounce.setSingleShot(True)
        self._debounce.setInterval(300)
        self._debounce.timeout.connect(self._disk_changed)
        self.retranslate()

    # --- text -----------------------------------------------------------------------

    def t(self, key: str, **kw) -> str:
        return self.tr_(key, **kw)

    def retranslate(self) -> None:
        self.search.setPlaceholderText(self.t("search"))
        self.btn_sheet.setToolTip(self.t("new_sheet"))
        self.btn_folder.setToolTip(self.t("new_folder"))
        self.btn_sheet.setIcon(icons.icon("new_sheet"))
        self.btn_folder.setIcon(icons.icon("new_folder"))
        size = QSize(icons.ICON_SIZE, icons.ICON_SIZE)
        self.btn_sheet.setIconSize(size)
        self.btn_folder.setIconSize(size)
        self.tree.setIconSize(size)
        self.rebuild()

    # --- building -------------------------------------------------------------------

    def set_store(self, store: SheetStore) -> None:
        self.store = store
        self.expanded.clear()
        QSettings().setValue("sidebar/expanded", [])
        self.rebuild()

    def _snapshot(self) -> tuple:
        """What the list shows, to skip rebuilds when only a sheet's text was saved."""

        def walk(node) -> tuple:
            return tuple((c.rel, c.is_dir, walk(c) if c.is_dir else ()) for c in node.children)

        return (
            walk(self.store.tree()),
            tuple(n.rel for n in self.store.pinned()),
            tuple(self.store.trashed()),
        )

    def _disk_changed(self) -> None:
        self.store.meta = self.store._load_meta()
        if self._snapshot() != getattr(self, "_signature", None):
            self.rebuild()
        self.changed.emit()

    def _watch(self) -> None:
        dirs = [str(self.store.root)]
        for path in self.store.root.rglob("*"):
            if path.is_dir() and not any(
                p.startswith(".") for p in path.relative_to(self.store.root).parts
            ):
                dirs.append(str(path))
        if self.store.trash_dir.is_dir():
            dirs.append(str(self.store.trash_dir))
        old = self.watcher.directories()
        if old:
            self.watcher.removePaths(old)
        self.watcher.addPaths(dirs)

    def _item(self, text: str, kind: str, key: str, icon: QIcon | None = None) -> QTreeWidgetItem:
        it = QTreeWidgetItem([text])
        it.setData(0, ROLE, (kind, key))
        if icon is not None:
            it.setIcon(0, icon)
        flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsSelectable
        if kind in (SHEET, PINNED, FOLDER):
            flags |= Qt.ItemFlag.ItemIsDragEnabled
        if kind in (FOLDER, SECTION):
            flags |= Qt.ItemFlag.ItemIsDropEnabled
        if kind == SECTION:
            flags = Qt.ItemFlag.ItemIsEnabled | Qt.ItemFlag.ItemIsDropEnabled
            f = QFont(self.tree.font())
            f.setBold(True)
            f.setPointSizeF(f.pointSizeF() * 0.8)
            it.setFont(0, f)
        it.setFlags(flags)
        if kind in (SHEET, PINNED):
            it.setToolTip(0, key)
        return it

    def rebuild(self) -> None:
        tree = self.tree
        scroll = tree.verticalScrollBar().value()
        tree.setAnimated(False)  # re-adding open folders must not replay the open animation
        tree.blockSignals(True)
        tree.clear()
        sheet_icon = icons.icon("sheet")
        pin_icon = icons.icon("pin")
        folder_icon = icons.icon("folder")
        query = self.search.text().strip()
        selected: QTreeWidgetItem | None = None
        if query:
            hits = self.store.search(query)
            for rel in hits:
                it = self._item(self.store.display_name(rel), SHEET, rel, sheet_icon)
                folder = rel.rsplit("/", 1)[0] if "/" in rel else ""
                if folder:
                    it.setText(0, f"{self.store.display_name(rel)}  ·  {folder}")
                tree.addTopLevelItem(it)
                if self.current == (SHEET, rel):
                    selected = it
            if not hits:
                empty = QTreeWidgetItem([self.t("no_results")])
                empty.setFlags(Qt.ItemFlag.NoItemFlags)
                tree.addTopLevelItem(empty)
        else:
            pinned = self.store.pinned()
            if pinned:
                sec = self._item(self.t("pinned").upper(), SECTION, PINNED)
                tree.addTopLevelItem(sec)
                for node in pinned:
                    it = self._item(node.name, PINNED, node.rel, pin_icon)
                    sec.addChild(it)
                    if self.current == (SHEET, node.rel):
                        selected = it
                sec.setExpanded(True)
            sec = self._item(self.t("sheets").upper(), SECTION, "")
            tree.addTopLevelItem(sec)

            def add(parent: QTreeWidgetItem, nodes) -> None:
                nonlocal selected
                for node in nodes:
                    if node.is_dir:
                        it = self._item(node.name, FOLDER, node.rel, folder_icon)
                        parent.addChild(it)
                        add(it, node.children)
                        it.setExpanded(node.rel in self.expanded)
                    else:
                        it = self._item(node.name, SHEET, node.rel, sheet_icon)
                        parent.addChild(it)
                        if self.current == (SHEET, node.rel):
                            selected = it

            add(sec, self.store.tree().children)
            sec.setExpanded(True)
            help_item = self._item(
                self.t("help"),
                HELP,
                "",
                icons.icon("help"),
            )
            tree.addTopLevelItem(help_item)
            if self.current == (HELP, ""):
                selected = help_item
            trashed = self.store.trashed()
            trash = self._item(
                f"{self.t('trash')} ({len(trashed)})" if trashed else self.t("trash"),
                TRASH,
                "",
                icons.icon("trash"),
            )
            tree.addTopLevelItem(trash)
            for name, original in trashed:
                it = self._item(self.store.display_name(name), TRASHED, name, sheet_icon)
                it.setToolTip(0, original)
                trash.addChild(it)
                if self.current == (TRASHED, name):
                    selected = it
            trash.setExpanded(TRASH_DIR in self.expanded)
        if selected is not None:
            self._show_current(selected)
        tree.verticalScrollBar().setValue(scroll)
        tree.blockSignals(False)
        QTimer.singleShot(0, lambda: tree.setAnimated(True))
        self._signature = self._snapshot()
        self._watch()

    def _show_current(self, item: QTreeWidgetItem) -> None:
        """Select an item and open the folders it sits in, remembering them as open."""
        p = item.parent()
        while p is not None:
            if not p.isExpanded():
                p.setExpanded(True)
            self._remember(p, True)
            p = p.parent()
        self.tree.setCurrentItem(item)
        self.tree.scrollToItem(item)

    def _remember(self, item: QTreeWidgetItem, expanded: bool) -> None:
        data = item.data(0, ROLE)
        if not data:
            return
        kind, key = data
        key = TRASH_DIR if kind == TRASH else key
        if kind in (FOLDER, TRASH):
            (self.expanded.add if expanded else self.expanded.discard)(key)
            QSettings().setValue("sidebar/expanded", sorted(self.expanded))

    def select(self, kind: str, key: str) -> None:
        """Highlight the open sheet. Only moves the selection; the list stays as it is."""
        self.current = (SHEET if kind == PINNED else kind, key)
        item = self._find(*self.current)
        if item is None or self.search.text().strip():
            self.rebuild()
            return
        tree = self.tree
        tree.blockSignals(True)
        self._show_current(item)
        tree.blockSignals(False)

    def _find(self, kind: str, key: str) -> QTreeWidgetItem | None:
        wanted = {(kind, key)} | ({(PINNED, key)} if kind == SHEET else set())
        it = QTreeWidgetItemIterator(self.tree)
        found = None
        while it.value():
            data = it.value().data(0, ROLE)
            if data and tuple(data) in wanted:
                if tuple(data)[0] == kind:  # prefer the item in the folder tree over the pin
                    return it.value()
                found = found or it.value()
            it += 1
        return found

    def current_folder(self) -> str:
        it = self.tree.currentItem()
        data = it.data(0, ROLE) if it else None
        if not data:
            return ""
        kind, key = data
        if kind == FOLDER:
            return key
        if kind in (SHEET, PINNED) and "/" in key:
            return key.rsplit("/", 1)[0]
        return ""

    # --- interaction ----------------------------------------------------------------

    def _clicked(self, item: QTreeWidgetItem) -> None:
        data = item.data(0, ROLE)
        if not data:
            return
        kind, key = data
        if kind in (SHEET, PINNED):
            self.open_sheet.emit(key)
        elif kind == HELP:
            self.open_help.emit()
        elif kind == TRASHED:
            self.open_trashed.emit(key)
        elif kind in (FOLDER, TRASH):
            item.setExpanded(not item.isExpanded())

    def _selected(self) -> tuple[str, str] | None:
        it = self.tree.currentItem()
        return it.data(0, ROLE) if it else None

    def _rename_selected(self) -> None:
        data = self._selected()
        if data and data[0] in (SHEET, PINNED, FOLDER):
            self.rename.emit(data[1])

    def _trash_selected(self) -> None:
        data = self._selected()
        if data and data[0] in (SHEET, PINNED, FOLDER):
            self.trash.emit(data[1])
        elif data and data[0] == TRASHED:
            self.delete_forever.emit(data[1])

    def _menu(self, pos: QPoint) -> None:
        item = self.tree.itemAt(pos)
        data = item.data(0, ROLE) if item else None
        kind, key = data if data else (SECTION, "")
        menu = QMenu(self)

        def add(name: str, slot, icon_name: str | None = None) -> None:
            menu.addAction(icons.icon(icon_name or name), self.t(name), slot)

        if kind in (SHEET, PINNED, FOLDER, SECTION):
            folder = key if kind == FOLDER else (key.rsplit("/", 1)[0] if "/" in key else "")
            if kind == SECTION:
                folder = ""
            add("new_sheet", lambda: self.new_sheet.emit(folder))
            add("new_folder", lambda: self.new_folder.emit(folder))
        if kind in (SHEET, PINNED, FOLDER):
            menu.addSeparator()
            add("rename", lambda: self.rename.emit(key))
            if kind in (SHEET, PINNED):
                if self.store.is_pinned(key):
                    add("unpin", lambda: self._unpin(key))
                else:
                    add("pin", lambda: self._pin(key))
            add("show_in_folder", lambda: self.show_in_folder.emit(key), "open_folder")
            menu.addSeparator()
            add("move_to_trash", lambda: self.trash.emit(key), "trash")
        elif kind == TRASHED:
            add("restore", lambda: self.restore.emit(key))
            add("delete_forever", lambda: self.delete_forever.emit(key))
        elif kind == TRASH and self.store.trashed():
            add("empty_trash", self.empty_trash.emit)
        if not menu.isEmpty():
            menu.exec(self.tree.viewport().mapToGlobal(pos))

    def _pin(self, rel: str) -> None:
        self.store.pin(rel)
        self.rebuild()

    def _unpin(self, rel: str) -> None:
        self.store.unpin(rel)
        self.rebuild()

    def _dropped(self, dragged, target, position: int) -> None:
        """Reorder, move into folders, pin or unpin by dragging."""
        if not dragged:
            return
        kind, rel = dragged
        tkind, tkey = target if target else (SECTION, "")
        # position: 0 on item, 1 above, 2 below, 3 viewport
        try:
            if tkind == SECTION and tkey == PINNED or tkind == PINNED:
                if kind in (SHEET, PINNED):
                    index = None
                    if tkind == PINNED:
                        pins = self.store.meta["pinned"]
                        index = pins.index(tkey) + (1 if position == 2 else 0)
                        if rel in pins and pins.index(rel) < index:
                            index -= 1
                    self.store.pin(rel, index)
            elif tkind in (FOLDER, SECTION) and position == 0:
                if kind == PINNED:
                    self.store.unpin(rel)
                self.store.move(rel, tkey if tkind == FOLDER else "")
            elif tkind in (SHEET, FOLDER):
                if kind == PINNED:
                    self.store.unpin(rel)
                folder = tkey.rsplit("/", 1)[0] if "/" in tkey else ""
                siblings = [n.rel for n in self._siblings(folder)]
                siblings = [s for s in siblings if s != rel]
                index = (
                    siblings.index(tkey) + (1 if position == 2 else 0) if tkey in siblings else None
                )
                self.store.move(rel, folder, index)
            elif tkind == TRASH and kind in (SHEET, PINNED, FOLDER):
                self.trash.emit(rel)
                return
        except OSError:
            pass
        self.rebuild()
        self.changed.emit()

    def _siblings(self, folder: str):
        node = self.store.tree()
        if folder:
            for part in folder.split("/"):
                node = next((c for c in node.children if c.is_dir and c.rel.endswith(part)), node)
        return node.children
