"""Main window."""

import logging
from datetime import datetime
from pathlib import Path

from PySide6.QtCore import (
    QEvent,
    QFileSystemWatcher,
    QLibraryInfo,
    QObject,
    QSettings,
    Qt,
    QTimer,
    QTranslator,
    QUrl,
    Signal,
)
from PySide6.QtGui import (
    QAction,
    QActionGroup,
    QCloseEvent,
    QDesktopServices,
    QFont,
    QFontDatabase,
    QGuiApplication,
    QKeyEvent,
    QKeySequence,
    QMouseEvent,
    QTextDocument,
)
from PySide6.QtWidgets import (
    QApplication,
    QInputDialog,
    QLabel,
    QMainWindow,
    QMenu,
    QMessageBox,
    QPushButton,
    QSplitter,
    QVBoxLayout,
    QWidget,
)

from .. import __version__
from ..engine import format_value
from ..engine.format import MONTHS_UK
from ..paths import FONTS, HELP_DIR
from ..rates import RatesService
from ..settings import Settings
from ..storage import SheetStore, StorageError
from ..translations import LANGUAGES, tr
from . import icons
from . import theme as themes
from .editor import KIND_ORDER, SheetEdit
from .find_bar import FindBar
from .settings_dialog import SettingsDialog
from .shortcuts_dialog import ShortcutsDialog
from .sidebar import HELP, SHEET, TRASHED, Sidebar

log = logging.getLogger(__name__)
FONT_FAMILY = "Fira Code"
SAVE_DELAY_MS = 500

WELCOME = """# My first sheet
// Type a line, get an answer on the right. Help is in the sidebar (F1).

groceries = $45
rent = €900 in USD
20% off $80
total
"""


class ClickLabel(QLabel):
    clicked = Signal()

    def mousePressEvent(self, event: QMouseEvent) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self.clicked.emit()


def load_fonts() -> str:
    family = ""
    for path in sorted(FONTS.glob("*.ttf")):
        font_id = QFontDatabase.addApplicationFont(str(path))
        families = QFontDatabase.applicationFontFamilies(font_id) if font_id >= 0 else []
        if families:
            family = families[0]
    return family or QFontDatabase.systemFont(QFontDatabase.SystemFont.FixedFont).family()


class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.settings = Settings.load()
        self.theme = themes.resolve(self.settings.theme)
        self.font_family = load_fonts()
        self.store = self._open_store(self.settings.sheets_dir)
        self.current: tuple[str, str] = ("", "")  # (kind, key)
        self._saved_mtime = 0.0
        self._dirty = False
        self._qt_translator: QTranslator | None = None
        # one document per opened sheet, so undo survives switching sheets
        self._docs: dict[str, QTextDocument] = {}
        self._positions: dict[str, tuple[int, int]] = {}  # cursor and scroll per sheet
        self._loose_doc: QTextDocument | None = None  # help or trash: not kept

        self.rates = RatesService(self.settings.rates_sources(), self)
        self.rates.changed.connect(self._engine_changed)
        self.rates.status_changed.connect(self._update_rates_label)

        self.sidebar = Sidebar(self.store, self.t)
        self.editor = SheetEdit(self.theme)
        self.editor.results_width = self.settings.results_width
        self.banner = QLabel()
        self.banner.setObjectName("banner")
        self.banner.hide()
        right = QWidget()
        box = QVBoxLayout(right)
        box.setContentsMargins(0, 0, 0, 0)
        box.setSpacing(0)
        box.addWidget(self.banner)
        box.addWidget(self.editor, 1)
        self.find_bar = FindBar(self.editor, self.t)
        box.addWidget(self.find_bar)
        self.splitter = QSplitter()
        self.splitter.addWidget(self.sidebar)
        self.splitter.addWidget(right)
        self.splitter.setStretchFactor(1, 1)
        self.splitter.setSizes([230, 770])
        self.splitter.setHandleWidth(1)
        self.setCentralWidget(self.splitter)

        self.total_label = ClickLabel()
        self.total_label.setObjectName("total")
        self.total_label.clicked.connect(self._copy_total)
        self.rates_label = ClickLabel()
        self.rates_label.clicked.connect(self.rates.refresh)
        self.statusBar().addWidget(self.total_label)
        self.statusBar().addPermanentWidget(self.rates_label)
        self.statusBar().setSizeGripEnabled(False)

        self._save_timer = QTimer(self)
        self._save_timer.setSingleShot(True)
        self._save_timer.setInterval(SAVE_DELAY_MS)
        self._save_timer.timeout.connect(self.save_current)
        self.editor.textChanged.connect(self._text_changed)
        self.editor.evaluated.connect(self._show_total)
        self.editor.copied.connect(self._copy)
        self.editor.results_resized.connect(self._results_resized)
        self.file_watcher = QFileSystemWatcher(self)
        self.file_watcher.fileChanged.connect(self._file_changed)

        s = self.sidebar
        s.open_sheet.connect(lambda rel: self.open_sheet(rel))
        s.open_help.connect(self.open_help)
        s.open_trashed.connect(self.open_trashed)
        s.new_sheet.connect(self.new_sheet)
        s.new_folder.connect(self.new_folder)
        s.rename.connect(self.rename)
        s.trash.connect(self.trash)
        s.restore.connect(self.restore)
        s.delete_forever.connect(self.delete_forever)
        s.empty_trash.connect(self.empty_trash)
        s.show_in_folder.connect(self.show_in_folder)
        s.changed.connect(self._sidebar_changed)

        QGuiApplication.styleHints().colorSchemeChanged.connect(self._system_theme_changed)
        self.apply_settings()  # sets the theme first, then builds the menus with its icons
        self._restore_window()
        self._open_initial()
        QTimer.singleShot(0, self.rates.refresh_if_stale)

    def t(self, key: str, **kw) -> str:
        return tr(self.settings.language, key, **kw)

    def _open_store(self, folder: str) -> SheetStore:
        store = SheetStore(Path(folder).expanduser())
        if not store.all_sheets() and not store.trashed() and not store.meta["order"]:
            store.create_sheet("", "Welcome", WELCOME)
        return store

    def _restore_window(self) -> None:
        qs = QSettings()
        geo = qs.value("window/geometry")
        if geo is not None:
            self.restoreGeometry(geo)
        else:
            self.resize(1000, 680)
        state = qs.value("window/splitter")
        if state is not None:
            self.splitter.restoreState(state)

    def _open_initial(self) -> None:
        last = self.settings.last_sheet
        sheets = self.store.all_sheets()
        if last and last in sheets:
            self.open_sheet(last)
        elif self.store.pinned():
            self.open_sheet(self.store.pinned()[0].rel)
        elif sheets:
            self.open_sheet(sheets[0])
        else:
            self.open_help()

    # menu text key -> icon name, where they differ
    ICONS = {
        "toggle_comment": "comment",
        "find_in_sheet": "search",
        "find_next": "caret_down",
        "find_previous": "caret_up",
        "find": "sheet",
        "toggle_sidebar": "sidebar",
        "toggle_line_numbers": "line_numbers",
        "help_sheet": "help",
        "refresh_rates": "refresh",
    }

    def _action(self, menu, key: str, slot, shortcut=None, checkable: bool = False) -> QAction:
        act = QAction(self.t(key), self)
        name = self.ICONS.get(key, key)
        # checkable items keep their tick instead: Fusion hides it behind an icon
        if name in icons.NAMES and not checkable:
            act.setIcon(icons.icon(name))
        if shortcut is not None:
            if isinstance(shortcut, list):
                act.setShortcuts(shortcut)
            else:
                act.setShortcut(QKeySequence(shortcut))
        act.setCheckable(checkable)
        act.triggered.connect(slot)
        menu.addAction(act)
        return act

    def build_menus(self) -> None:
        bar = self.menuBar()
        bar.clear()
        K = QKeySequence.StandardKey
        m = bar.addMenu(self.t("menu_file"))
        self._action(m, "new_sheet", lambda: self.new_sheet(self.sidebar.current_folder()), K.New)
        self._action(
            m, "new_folder", lambda: self.new_folder(self.sidebar.current_folder()), "Ctrl+Shift+N"
        )
        self._action(m, "open_folder", lambda: self.show_in_folder(""))
        m.addSeparator()
        self._action(m, "settings", self.open_settings, "Ctrl+,")
        m.addSeparator()
        quit_act = self._action(m, "quit", self.close, K.Quit)
        quit_act.setMenuRole(QAction.MenuRole.QuitRole)

        m = bar.addMenu(self.t("menu_edit"))
        ed = self.editor
        self._action(m, "undo", ed.undo, K.Undo)
        self._action(m, "redo", ed.redo, K.Redo)
        m.addSeparator()
        self._action(m, "cut", ed.cut, K.Cut)
        self._action(m, "copy", ed.copy, K.Copy)
        self._action(m, "paste", ed.paste, K.Paste)
        self._action(m, "select_all", ed.selectAll, K.SelectAll)
        m.addSeparator()
        self._action(m, "toggle_comment", self._toggle_comment, "Ctrl+/")
        self._action(m, "copy_result", self._copy_current_result, "Ctrl+Shift+C")
        self._action(m, "copy_with_results", self._copy_with_results, "Ctrl+Alt+C")
        m.addSeparator()
        self._action(m, "insert_total", ed.insert_total, "Ctrl+T")
        self._action(m, "insert_reference", ed.insert_line_reference, "Ctrl+L")
        m.addSeparator()
        fb = self.find_bar
        self._action(m, "find_in_sheet", fb.open, K.Find)
        self._action(m, "find_next", fb.step, K.FindNext)
        self._action(m, "find_previous", lambda: fb.step(backward=True), K.FindPrevious)
        self._action(m, "find", self._focus_search, "Ctrl+P")

        m = bar.addMenu(self.t("menu_view"))
        sub = m.addMenu(icons.icon("theme"), self.t("theme"))
        group = QActionGroup(self)
        for key in ("dark", "light", "system"):
            act = self._action(
                sub, f"theme_{key}", lambda _=False, k=key: self.set_theme(k), checkable=True
            )
            act.setChecked(self.settings.theme == key)
            group.addAction(act)
        sub = m.addMenu(icons.icon("language"), self.t("language"))
        group = QActionGroup(self)
        for key, name in LANGUAGES.items():
            act = QAction(name, self, checkable=True)
            act.setChecked(self.settings.language == key)
            act.triggered.connect(lambda _=False, k=key: self.set_language(k))
            group.addAction(act)
            sub.addAction(act)
        m.addSeparator()
        self._action(
            m, "zoom_in", lambda: self.zoom(1), [QKeySequence(K.ZoomIn), QKeySequence("Ctrl+=")]
        )
        self._action(m, "zoom_out", lambda: self.zoom(-1), K.ZoomOut)
        self._action(m, "zoom_reset", lambda: self.zoom(0), "Ctrl+0")
        m.addSeparator()
        act = self._action(m, "toggle_sidebar", self._toggle_sidebar, "Ctrl+\\", checkable=True)
        act.setChecked(self.sidebar.isVisible() or not self.isVisible())
        act = self._action(
            m, "toggle_line_numbers", self._toggle_line_numbers, "Ctrl+Shift+L", checkable=True
        )
        act.setChecked(self.settings.line_numbers)

        m = bar.addMenu(self.t("menu_help"))
        self._action(m, "help_sheet", self.open_help, K.HelpContents)
        self._action(
            m,
            "shortcuts",
            self.show_shortcuts,
            "Shift+F1",  # next to F1 for help; Ctrl+? sat on top of Ctrl+/ for comments
        )
        self._action(m, "refresh_rates", self.rates.refresh, "Ctrl+R")
        m.addSeparator()
        about = self._action(m, "about", self.about)
        about.setMenuRole(QAction.MenuRole.AboutRole)
        for menu in bar.findChildren(QMenu):
            menu.installEventFilter(self)

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # noqa: N802
        """Shortcuts work while a menu is open too; Qt ignores them there by default."""
        if isinstance(obj, QMenu) and event.type() == QEvent.Type.KeyPress:
            assert isinstance(event, QKeyEvent)
            action = self._action_for_key(event)
            if action is not None:
                while (popup := QApplication.activePopupWidget()) is not None:
                    popup.close()
                QTimer.singleShot(0, action.trigger)
                return True
        return super().eventFilter(obj, event)

    def _action_for_key(self, event: QKeyEvent) -> QAction | None:
        mods = event.modifiers()
        function_key = Qt.Key.Key_F1.value <= event.key() <= Qt.Key.Key_F35.value
        chord = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.AltModifier
        if not (mods & (chord | Qt.KeyboardModifier.MetaModifier) or function_key):
            return None  # plain letters pick menu items by their underlined letter
        pressed = QKeySequence(event.keyCombination())
        for menu in self.menuBar().findChildren(QMenu):
            for action in menu.actions():
                if action.isEnabled() and any(
                    key.matches(pressed) == QKeySequence.SequenceMatch.ExactMatch
                    for key in action.shortcuts()
                ):
                    return action
        return None

    def apply_settings(self) -> None:
        s = self.settings
        app = QApplication.instance()
        self.theme = themes.resolve(s.theme)
        if isinstance(app, QApplication):
            themes.apply(app, self.theme)
        font = QFont(self.font_family)
        font.setPointSize(s.font_size)
        font.setStyleHint(QFont.StyleHint.Monospace)
        if hasattr(font, "setFeature"):
            tag = QFont.Tag("calt")
            if s.ligatures:
                font.unsetFeature(tag)
            else:
                font.setFeature(tag, 0)
        self.editor.setFont(font)
        self.editor.apply_theme(self.theme)
        self.editor.set_results_width(s.results_width)
        self.editor.set_line_numbers(s.line_numbers)
        self._engine_changed()
        self._load_qt_translation()
        self.sidebar.tr_ = self.t
        self.sidebar.retranslate()
        self.find_bar.retranslate()
        self.editor.kind_labels = {k: self.t(f"kind_{k}") for k in KIND_ORDER}
        self.editor.words = {k: self.t(f"word_{k}") for k in ("total", "prev", "line")}
        self._update_rates_label()
        self.setWindowTitle(self._title())
        self.build_menus()

    def _load_qt_translation(self) -> None:
        """Qt's own texts (Close, OK, Cancel, Yes, No) in the UI language."""
        app = QApplication.instance()
        if app is None:
            return
        if self._qt_translator is not None:
            app.removeTranslator(self._qt_translator)
            self._qt_translator = None
        if self.settings.language == "en":
            return
        translator = QTranslator(self)
        folder = QLibraryInfo.path(QLibraryInfo.LibraryPath.TranslationsPath)
        if translator.load(f"qtbase_{self.settings.language}", folder):
            app.installTranslator(translator)
            self._qt_translator = translator
        else:
            log.warning("no Qt translation for %s in %s", self.settings.language, folder)

    def _engine_changed(self) -> None:
        s = self.settings
        self.editor.set_engine(self.rates.table, s.engine_config(), s.format_options())

    def open_settings(self) -> None:
        dlg = SettingsDialog(self.settings, self.t, self)
        if dlg.exec() != SettingsDialog.DialogCode.Accepted:
            return
        new = dlg.result_settings()
        folder_changed = (
            Path(new.sheets_dir).expanduser() != Path(self.settings.sheets_dir).expanduser()
        )
        if folder_changed:
            self.save_current()
            try:
                store = self._open_store(new.sheets_dir)
            except OSError as exc:
                QMessageBox.warning(self, self.t("settings_title"), str(exc))
                new.sheets_dir = self.settings.sheets_dir
            else:
                self.store = store
                self.sidebar.set_store(store)
                self._forget_documents(lambda _rel: True)
        self.settings = new
        self.settings.save()
        self.rates.set_sources(new.rates_sources())
        self.apply_settings()
        if folder_changed:
            self._open_initial()

    def set_theme(self, key: str) -> None:
        self.settings.theme = key
        self.settings.save()
        self.apply_settings()

    def _system_theme_changed(self) -> None:
        if self.settings.theme == "system":
            self.apply_settings()

    def set_language(self, key: str) -> None:
        self.settings.language = key
        self.settings.save()
        self.apply_settings()
        if self.current[0] == HELP:
            self.open_help()

    def zoom(self, step: int) -> None:
        size = 14 if step == 0 else self.settings.font_size + step
        self.settings.font_size = max(8, min(size, 40))
        self.settings.save()
        self.apply_settings()

    def _results_resized(self, width: int) -> None:
        self.settings.results_width = width
        self.settings.save()

    def _toggle_sidebar(self) -> None:
        self.sidebar.setVisible(not self.sidebar.isVisible())

    def _toggle_line_numbers(self) -> None:
        self.settings.line_numbers = not self.settings.line_numbers
        self.settings.save()
        self.editor.set_line_numbers(self.settings.line_numbers)

    def _title(self) -> str:
        kind, key = self.current
        app = self.t("app_name")
        if kind == SHEET:
            return f"{self.store.display_name(key)} - {app}"
        if kind == HELP:
            return f"{self.t('help')} - {app}"
        if kind == TRASHED:
            return f"{self.store.display_name(key)} ({self.t('trash')}) - {app}"
        return app

    def _load(self, kind: str, key: str, text: str, read_only: bool, banner: str = "") -> None:
        self.save_current()
        if self.file_watcher.files():
            self.file_watcher.removePaths(self.file_watcher.files())
        if self.current[0] == SHEET:
            ed = self.editor
            self._positions[self.current[1]] = (
                ed.textCursor().position(),
                ed.verticalScrollBar().value(),
            )
        self.current = (kind, key)
        doc = self._docs.get(key) if kind == SHEET else None
        if doc is None:
            doc = self.editor.new_document(text, self)
            if kind == SHEET:
                self._docs[key] = doc
        elif doc.toPlainText() != text:
            doc.setPlainText(text)  # changed on disk while another sheet was open
        loose, self._loose_doc = self._loose_doc, (None if kind == SHEET else doc)
        self.editor.blockSignals(True)
        self.editor.show_document(doc)
        position, scroll = self._positions.get(key, (0, 0)) if kind == SHEET else (0, 0)
        cursor = self.editor.textCursor()
        cursor.setPosition(min(position, doc.characterCount() - 1))
        self.editor.setTextCursor(cursor)
        self.editor.blockSignals(False)
        self.editor.verticalScrollBar().setValue(scroll)
        if loose is not None and loose is not doc:
            loose.deleteLater()
        self.editor.recalculate()
        self.find_bar.sheet_changed()
        self.editor.setReadOnly(read_only)
        self.editor._cursor_moved()
        self._dirty = False
        self.banner.setText(banner)
        self.banner.setVisible(bool(banner))
        self.sidebar.select(kind, key)
        self.setWindowTitle(self._title())

    def open_sheet(self, rel: str, focus: bool = False) -> None:
        try:
            text = self.store.read(rel)
        except (OSError, UnicodeDecodeError) as exc:
            QMessageBox.warning(self, self.t("app_name"), str(exc))
            return
        self._load(SHEET, rel, text, read_only=False)
        self._saved_mtime = self.store.mtime(rel)
        self.file_watcher.addPath(str(self.store.path(rel)))
        self.settings.last_sheet = rel
        self.settings.save()
        if focus:
            self.editor.setFocus()

    def open_help(self) -> None:
        path = HELP_DIR / f"help_{self.settings.language}.txt"
        if not path.exists():
            path = HELP_DIR / "help_en.txt"
        try:
            text = path.read_text(encoding="utf-8")
        except OSError:
            text = ""
        self._load(HELP, "", text, read_only=True, banner=self.t("read_only_help"))

    def open_trashed(self, name: str) -> None:
        try:
            text = self.store.read_trashed(name)
        except OSError, UnicodeDecodeError:
            text = ""
        self._load(TRASHED, name, text, read_only=True, banner=self.t("read_only_trash"))

    def _text_changed(self) -> None:
        if self.current[0] == SHEET and not self.editor.isReadOnly():
            self._dirty = True
            self._save_timer.start()

    def save_current(self) -> None:
        self._save_timer.stop()
        kind, rel = self.current
        if kind != SHEET or not self._dirty:
            return
        try:
            self.store.write(rel, self.editor.toPlainText())
            self._saved_mtime = self.store.mtime(rel)
            self._dirty = False
        except OSError as exc:
            self.statusBar().showMessage(str(exc), 5000)
        path = str(self.store.path(rel))
        if path not in self.file_watcher.files():
            self.file_watcher.addPath(path)

    def _file_changed(self, path: str) -> None:
        kind, rel = self.current
        if kind != SHEET or str(self.store.path(rel)) != path:
            return
        mtime = self.store.mtime(rel)
        if mtime == self._saved_mtime or self._dirty:
            return
        if not self.store.path(rel).exists():
            return  # moved or deleted; the sidebar refresh handles it
        try:
            text = self.store.read(rel)
        except OSError, UnicodeDecodeError:
            return
        if text != self.editor.toPlainText():
            cursor = self.editor.textCursor().position()
            self.editor.setPlainText(text)
            c = self.editor.textCursor()
            c.setPosition(min(cursor, len(text)))
            self.editor.setTextCursor(c)
            self._dirty = False
            self.statusBar().showMessage(
                self.t("external_change", name=self.store.display_name(rel)), 4000
            )
        self._saved_mtime = mtime
        if path not in self.file_watcher.files():
            self.file_watcher.addPath(path)

    def _sidebar_changed(self) -> None:
        kind, key = self.current
        if kind == SHEET and not self.store.path(key).exists():
            sheets = self.store.all_sheets()
            if sheets:
                self.open_sheet(sheets[0])
            else:
                self.open_help()

    def new_sheet(self, folder: str = "") -> None:
        self.save_current()
        try:
            rel = self.store.create_sheet(folder, self.t("untitled"))
        except OSError as exc:
            QMessageBox.warning(self, self.t("app_name"), str(exc))
            return
        self.open_sheet(rel, focus=True)

    def new_folder(self, parent: str = "") -> None:
        name, ok = self._ask_text(self.t("new_folder"), self.t("folder"))
        if not ok or not name.strip():
            return
        try:
            rel = self.store.create_folder(parent, name)
        except OSError as exc:
            QMessageBox.warning(self, self.t("app_name"), str(exc))
            return
        self.sidebar.expanded.add(rel)
        self.sidebar.rebuild()

    def _ask_text(self, title: str, text: str) -> tuple[str, bool]:
        """A one-line prompt with room around it, OK styled as the main button."""
        dlg = QInputDialog(self)
        dlg.setWindowTitle(title)
        dlg.setLabelText(title)
        dlg.setTextValue(text)
        dlg.setOkButtonText(self.t("save"))
        dlg.setCancelButtonText(self.t("cancel"))

        def polish() -> None:  # the buttons and layout exist only once it is shown
            layout = dlg.layout()
            if layout is not None:
                layout.setContentsMargins(20, 18, 20, 16)
                layout.setSpacing(12)
            for button in dlg.findChildren(QPushButton):
                if button.text().replace("&", "") == self.t("save"):
                    button.setObjectName("primary")
                    button.style().unpolish(button)
                    button.style().polish(button)
            dlg.resize(max(dlg.width(), 380), dlg.height())

        QTimer.singleShot(0, polish)
        ok = dlg.exec() == QInputDialog.DialogCode.Accepted
        return dlg.textValue(), ok

    def rename(self, rel: str) -> None:
        old = self.store.display_name(rel)
        name, ok = self._ask_text(self.t("rename"), old)
        if not ok or not name.strip() or name == old:
            return
        self.save_current()
        try:
            new_rel = self.store.rename(rel, name)
        except (OSError, StorageError) as exc:
            QMessageBox.warning(self, self.t("rename"), str(exc))
            return
        for cache in (self._docs, self._positions):
            for old_key in [k for k in cache if k == rel or k.startswith(rel + "/")]:
                cache[new_rel + old_key[len(rel) :]] = cache.pop(old_key)
        kind, key = self.current
        if kind == SHEET and (key == rel or key.startswith(rel + "/")):
            self.current = (SHEET, new_rel + key[len(rel) :])
            self.open_sheet(self.current[1])
        else:
            self.sidebar.rebuild()

    def trash(self, rel: str) -> None:
        self.save_current()
        kind, key = self.current
        try:
            self.store.trash(rel)
        except OSError as exc:
            QMessageBox.warning(self, self.t("move_to_trash"), str(exc))
            return
        self._forget_documents(lambda k: k == rel or k.startswith(rel + "/"))
        if kind == SHEET and (key == rel or key.startswith(rel + "/")):
            self.current = ("", "")
            sheets = self.store.all_sheets()
            if sheets:
                self.open_sheet(sheets[0])
            else:
                self.open_help()
        else:
            self.sidebar.rebuild()

    def restore(self, name: str) -> None:
        try:
            rel = self.store.restore(name)
        except OSError as exc:
            QMessageBox.warning(self, self.t("restore"), str(exc))
            return
        if rel.endswith(".txt"):
            self.open_sheet(rel)
        else:
            self.sidebar.rebuild()

    def delete_forever(self, name: str) -> None:
        answer = QMessageBox.question(
            self,
            self.t("delete_forever"),
            self.t("confirm_delete", name=self.store.display_name(name)),
        )
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.delete_forever(name)
        except OSError as exc:
            QMessageBox.warning(self, self.t("delete_forever"), str(exc))
        if self.current == (TRASHED, name):
            self.open_help()
        self.sidebar.rebuild()

    def empty_trash(self) -> None:
        answer = QMessageBox.question(self, self.t("empty_trash"), self.t("confirm_empty"))
        if answer != QMessageBox.StandardButton.Yes:
            return
        try:
            self.store.empty_trash()
        except OSError as exc:
            QMessageBox.warning(self, self.t("empty_trash"), str(exc))
        if self.current[0] == TRASHED:
            self.open_help()
        self.sidebar.rebuild()

    def _forget_documents(self, which) -> None:
        """Drop kept documents (and their undo) for sheets that moved away."""
        for key in [k for k in self._docs if which(k)]:
            doc = self._docs.pop(key)
            self._positions.pop(key, None)
            if doc is self.editor.document():
                self._loose_doc = doc  # still on screen; goes when the next sheet opens
            else:
                doc.deleteLater()

    def show_in_folder(self, rel: str) -> None:
        path = self.store.path(rel) if rel else self.store.root
        folder = path if path.is_dir() else path.parent
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(folder)))

    def _copy(self, text: str) -> None:
        QGuiApplication.clipboard().setText(text)
        self.statusBar().showMessage(self.t("copied", text=text), 2000)

    def _copy_current_result(self) -> None:
        text = self.editor.current_result()
        if text:
            self._copy(text)

    def _copy_with_results(self) -> None:
        QGuiApplication.clipboard().setText(self.editor.text_with_results())
        self.statusBar().showMessage(self.t("copied", text="…"), 2000)

    def _copy_total(self) -> None:
        result = self.editor.result
        if result is not None and result.total is not None:
            self._copy(format_value(result.total, self.settings.format_options()))

    def _show_total(self, result) -> None:
        if result.total is None:
            self.total_label.setText("")
            return
        text = format_value(result.total, self.settings.format_options())
        self.total_label.setText(self.t("total", text=text))

    def _update_rates_label(self) -> None:
        r = self.rates
        if r.busy:
            text = self.t("rates_updating")
        else:
            when = self._rates_time(r.table.updated) if r.table.updated else self.t("rates_never")
            source = r.table.source or "-"
            if source == "bundled snapshot":
                source = self.t("rates_bundled")
            if r.error:
                text = self.t("rates_error", error=r.error, when=when)
            else:
                text = self.t("rates_ok", when=when, source=source)
        self.rates_label.setText(text)
        self.rates_label.setToolTip(self.t("rates_tip"))

    def _rates_time(self, stamp: float) -> str:
        dt = datetime.fromtimestamp(stamp)
        if self.settings.language == "uk":
            return f"{dt.day} {MONTHS_UK[dt.month - 1]} {dt.year}, {dt:%H:%M}"
        return f"{dt.day} {dt:%b %Y, %H:%M}"

    def _toggle_comment(self) -> None:
        if not self.editor.isReadOnly():
            self.editor.toggle_comment()

    def _focus_search(self) -> None:
        self.sidebar.show()
        self.sidebar.search.setFocus()
        self.sidebar.search.selectAll()

    def show_shortcuts(self) -> None:
        ShortcutsDialog(self.menuBar(), self.t, self).exec()

    def about(self) -> None:
        box = QMessageBox(self)
        box.setWindowTitle(self.t("about"))
        box.setTextFormat(Qt.TextFormat.RichText)
        box.setText(self.t("about_text", version=__version__))
        box.setIconPixmap(self.windowIcon().pixmap(64, 64))
        box.exec()

    def closeEvent(self, event: QCloseEvent) -> None:  # noqa: N802
        self.save_current()
        qs = QSettings()
        qs.setValue("window/geometry", self.saveGeometry())
        qs.setValue("window/splitter", self.splitter.saveState())
        self.settings.save()
        super().closeEvent(event)
