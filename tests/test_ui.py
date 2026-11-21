"""UI smoke tests: the real window, offscreen, with every user directory in a temp dir."""

import os
import subprocess
import sys
import time
from dataclasses import replace
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest
import shiboken6
from PySide6.QtCore import (
    QByteArray,
    QCoreApplication,
    QEvent,
    QPoint,
    QRect,
    QSettings,
    QSize,
    Qt,
    QTimer,
)
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QFontMetrics,
    QGuiApplication,
    QHelpEvent,
    QImage,
    QInputMethodEvent,
    QKeyEvent,
    QKeySequence,
    QPainter,
    QStandardItem,
    QStandardItemModel,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtTest import QTest
from PySide6.QtWidgets import (
    QApplication,
    QDialogButtonBox,
    QMenu,
    QMessageBox,
    QPushButton,
    QStyle,
    QStyleOptionFocusRect,
    QStyleOptionViewItem,
    QToolTip,
    QWidget,
)

from calculon import settings, spelling
from calculon.engine import RateTable
from calculon.settings import Settings
from calculon.spelling import SpellChecker, Status, probe
from calculon.storage import SheetStore
from calculon.translations import tr
from calculon.ui import directory_dialog, icons, main_window, settings_dialog
from calculon.ui import theme as themes
from calculon.ui.about_dialog import AboutDialog
from calculon.ui.editor import KIND_ROLE, SheetScrollBar, fit_menu, sheet_text
from calculon.ui.settings_dialog import SettingsDialog
from calculon.ui.shortcuts_dialog import ShortcutsDialog, key_text
from calculon.ui.sidebar import DIRECTORY, HELP, ROLE, Sidebar
from calculon.ui.theme import GLACIER_DARK
from tests.test_directory_dialog import assert_error_colour


def pump(app) -> None:
    for _ in range(5):
        app.processEvents()


def test_warning_tooltip_has_an_opaque_themed_frame(window, app) -> None:
    ed = window.editor
    ed.setPlainText("18/11/2026")
    ed.recalculate()
    pump(app)
    pos = line_pos(ed, 0, 3)
    hover = QHelpEvent(QEvent.Type.ToolTip, pos, ed.viewport().mapToGlobal(pos))
    QApplication.sendEvent(ed.viewport(), hover)
    try:
        assert "2026-11-18" in QToolTip.text()
        tooltip = next(
            w
            for w in app.topLevelWidgets()
            if w.isVisible() and w.windowType() == Qt.WindowType.ToolTip
        )
        assert tooltip.grab().toImage().pixelColor(0, 0) == QColor(window.theme.border)
    finally:
        QToolTip.hideText()


def off_centre(label, app) -> int:
    """How far the middle of a status bar label is from the middle of the window, in
    pixels. A pixel or two off is fine: QStatusBar keeps 2 px of margin on its left only."""
    pump(app)
    window = label.window()
    return label.mapTo(window, label.rect().center()).x() - window.rect().center().x()


def test_first_start_creates_welcome_sheet(open_window, app) -> None:
    window = open_window()
    assert window.store.all_sheets() == ["Welcome.txt"]
    assert window.current == ("sheet", "Welcome.txt")
    pump(app)
    texts = [line.text for line in window.editor.result.lines]
    assert "$64.00" in texts  # 20% off $80


def drive_directory_dialog(
    monkeypatch, *directories: str
) -> list[directory_dialog.DirectoryDialog]:
    """Stand in for the user: type each directory in turn and press "Use this directory".
    With no directories, press Quit. Returns the dialogs that opened."""
    opened = []

    def run(dialog) -> int:
        opened.append(dialog)
        for directory in directories:
            dialog.directory.setText(directory)
            dialog.try_directory()
            if dialog.result() == directory_dialog.QDialog.DialogCode.Accepted:
                break
        return dialog.result()

    monkeypatch.setattr(directory_dialog.DirectoryDialog, "exec", run)
    return opened


def test_first_start_asks_for_sheets_directory(app, home, tmp_path, monkeypatch) -> None:
    qs = QSettings()
    qs.clear()
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    chosen = tmp_path / "My sheets"
    opened = drive_directory_dialog(monkeypatch, str(blocker / "Calculon"), str(chosen))
    try:
        assert directory_dialog.choose_sheets_directory() is not None
        dialog = opened[0]
        assert dialog.error.text().startswith(f"Calculon can't create or write to {blocker}")
        assert Settings.load().sheets_dir == str(chosen)
        assert chosen.is_dir()
    finally:
        qs.clear()


def test_first_start_suggests_documents(app, home, monkeypatch) -> None:
    QSettings().clear()
    opened = drive_directory_dialog(monkeypatch)
    assert directory_dialog.choose_sheets_directory() is None
    assert opened[0].directory.text() == settings.default_sheets_dir()
    assert opened[0].error.isHidden()
    assert Settings.load().sheets_dir == ""


def test_directory_dialog_uses_dark_theme_with_saved_light_settings(
    app, tmp_path, monkeypatch
) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(blocker / "Calculon"))
    qs.setValue("theme", "light")
    opened = drive_directory_dialog(monkeypatch)
    try:
        assert directory_dialog.choose_sheets_directory() is None
        dialog = opened[0]
        dialog.show()
        pump(app)
        assert_error_colour(dialog.error, GLACIER_DARK.error)
        page = dialog.findChild(QWidget, "page")
        assert page.palette().color(page.backgroundRole()).name() == GLACIER_DARK.bg
    finally:
        if opened:
            opened[0].close()
            opened[0].deleteLater()
            QCoreApplication.sendPostedEvents(opened[0], QEvent.Type.DeferredDelete)
        qs.clear()


def test_chosen_directory_reaches_the_window_when_settings_cannot_be_saved(
    open_window, tmp_path, monkeypatch
) -> None:
    """In a home directory Calculon can't write to, QSettings drops the save without an
    error. So the window must get the directory from the dialog, not from the settings file."""
    QSettings().clear()
    monkeypatch.setattr(Settings, "save", lambda self: None)
    chosen = tmp_path / "My sheets"
    drive_directory_dialog(monkeypatch, str(chosen))
    w = open_window(directory_dialog.choose_sheets_directory(), show=False)
    assert w.store.root == chosen


def test_saved_sheets_directory_opens_without_asking(app, tmp_path, monkeypatch) -> None:
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(tmp_path / "sheets"))
    opened = drive_directory_dialog(monkeypatch)
    try:
        assert directory_dialog.choose_sheets_directory() is not None
        assert opened == []
    finally:
        qs.clear()


def test_blocked_saved_directory_asks_again_and_explains(app, tmp_path, monkeypatch) -> None:
    """Windows' Controlled folder access can block Documents. Say why and ask again,
    with the saved directory in the box so a retry is one click."""
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    blocked = blocker / "Calculon"
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(blocked))
    monkeypatch.setattr(directory_dialog, "sys", SimpleNamespace(platform="win32"))
    opened = drive_directory_dialog(monkeypatch)
    try:
        assert directory_dialog.choose_sheets_directory() is None
        dialog = opened[0]
        assert dialog.directory.text() == str(blocked)
        assert str(blocked) in dialog.error.text()
        assert "Controlled folder access" in dialog.error.text()
        assert Settings.load().sheets_dir == str(blocked)
    finally:
        qs.clear()


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions")
def test_directory_error_names_the_reason_not_the_test_file(app, tmp_path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    dialog = directory_dialog.DirectoryDialog(str(locked), "", "en")
    try:
        dialog.try_directory()
    finally:
        locked.chmod(0o700)
    assert dialog.error.text() == (
        f"Calculon can't create or write to {locked}. Permission denied.\n\nPick another directory."
    )


def test_directory_dialog_fits_the_error(app, tmp_path) -> None:
    blocker = tmp_path / "not-a-directory"
    blocker.write_text("")
    themes.apply(app, GLACIER_DARK)
    dialog = directory_dialog.DirectoryDialog(str(blocker / "Calculon"), "", "en")
    dialog.show()
    pump(app)
    height = dialog.height()
    QTest.keyClick(dialog.directory, Qt.Key.Key_Return)  # Enter means "Use this directory"
    pump(app)
    error = dialog.error
    try:
        assert dialog.isVisible() and error.isVisible()
        assert_error_colour(error, GLACIER_DARK.error)
        page = dialog.findChild(QWidget, "page")
        assert page.palette().color(page.backgroundRole()).name() == GLACIER_DARK.bg
        assert dialog.use_button.objectName() == "primary"
        assert not dialog.icon.pixmap().isNull() and dialog.icon.isVisible()
        # the whole wrapped message shows without resizing the window by hand
        assert dialog.height() > height
        assert error.height() >= error.heightForWidth(error.width())
        assert error.mapTo(dialog, error.rect().bottomLeft()).y() < dialog.height()
    finally:
        dialog.close()
        dialog.deleteLater()
        QCoreApplication.sendPostedEvents(dialog, QEvent.Type.DeferredDelete)
        themes.apply(app, GLACIER_DARK)


def test_typing_saves_and_calculates(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("a = 5\na * 2")
    pump(app)
    assert window.editor.result_text(1) == "10"
    window.save_current()
    assert window.store.read(window.current[1]) == "a = 5\na * 2"


def test_high_precision_total_updates(window, app) -> None:
    window.settings.max_decimals = 20
    window.apply_settings()
    window.new_sheet("")
    window.editor.setPlainText("99000000")
    pump(app)
    assert window.total_label.text() == "Total: 99,000,000"

    window.editor.setPlainText("99000000\n99000000")
    pump(app)
    assert window.editor.result_text(1) == "99,000,000"
    assert window.total_label.text() == "Total: 198,000,000"


def test_total_label_shows_missing_exchange_rate(window, app) -> None:
    window.rates.table = RateTable()
    window.rates.changed.emit()
    window.new_sheet("")
    window.editor.setPlainText("100 CHF\n50 USD")
    pump(app)
    assert "no exchange rate for CHF" in window.total_label.text()

    window.editor.setPlainText("50 USD")
    pump(app)
    assert window.total_label.text() == "Total: $50.00"


def test_external_edit_is_not_overwritten_by_unsaved_changes(window) -> None:
    window.new_sheet("")
    path = window.current[1]
    window.editor.setPlainText("local edit")
    window.store.write(path, "external edit")
    window._file_changed(str(window.store.path(path)))
    assert not window.save_current()
    assert window.store.read(path) == "external edit"
    assert window.editor.toPlainText() == "local edit"
    assert window._dirty


@pytest.mark.parametrize(("size", "step"), [(8, -1), (40, 1)])
def test_zoom_does_not_reapply_at_limit(window, monkeypatch, size, step) -> None:
    window.settings.font_size = size
    saved = []
    applied = []
    monkeypatch.setattr(window.settings, "save", lambda: saved.append(True))
    monkeypatch.setattr(window, "apply_settings", lambda: applied.append(True))

    for _ in range(10):
        window.zoom(step)

    assert window.settings.font_size == size
    assert not saved
    assert not applied


def test_new_sheet_prompts_for_name(window, monkeypatch) -> None:
    prompts = []

    def ask(title, default):
        prompts.append((title, default))
        return "Budget", True

    monkeypatch.setattr(window, "_ask_text", ask)
    window.new_sheet()
    assert prompts == [(window.t("new_sheet"), window.t("untitled"))]
    assert window.current == ("sheet", "Budget.txt")

    monkeypatch.setattr(window, "_ask_text", lambda *_: ("", False))
    window.new_sheet()
    assert window.current == ("sheet", "Budget.txt")
    assert window.store.all_sheets().count("Budget.txt") == 1


def test_switch_number_style_recalculates_without_touching_the_sheet(window, monkeypatch) -> None:
    window.new_sheet("")
    ed = window.editor
    text = "$75.000,00\n$75,000.00\n10.1111\n1000\u00a0500"
    ed.setPlainText(text)
    ed.recalculate()
    assert [line.text for line in ed.result.lines] == ["", "$75,000.00", "10.111", ""]
    assert window.save_current()
    document = ed.document()

    def accept(dialog):
        dialog.number_style.setCurrentIndex(dialog.number_style.findData("dot_comma"))
        return SettingsDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", accept)
    window.open_settings()
    assert [line.text for line in ed.result.lines] == ["$75.000,00", "", "", ""]
    assert ed.document() is document
    assert sheet_text(document) == window.store.read(window.current[1]) == text
    assert Settings.load().number_style == "dot_comma"


@pytest.mark.parametrize(
    ("style", "group", "point"),
    [
        ("comma_dot", ",", "."),
        ("dot_comma", ".", ","),
        ("space_comma", " ", ","),
        ("space_dot", " ", "."),
    ],
)
def test_pasting_and_typing_numbers_preserves_sheet_text(window, app, style, group, point):
    window.settings.number_style = style
    window.apply_settings()
    window.new_sheet("")
    ed = window.editor
    typed = f"1{group}2"
    QTest.keyClicks(ed, typed)
    pump(app)
    assert ed.result.lines[0].kind == "unfinished"
    assert ed.result_text(0) == ""
    assert not ed.document().firstBlock().layout().formats()
    QTest.keyClicks(ed, "34")
    pump(app)
    assert ed.result.lines[0].value.mag == 1234
    QTest.keyClick(ed, Qt.Key.Key_Return)
    pasted_group = "\u00a0" if group == " " else group
    pasted = f"3{pasted_group}456{point}5\n2{group}9999"
    QGuiApplication.clipboard().setText(pasted)
    ed.paste()
    pump(app)
    assert sheet_text(ed.document()) == f"{typed}34\n{pasted}"
    assert ed.result.lines[1].value.mag == 3456.5
    assert ed.result.lines[2].spans == [(0, len(pasted.splitlines()[1]), "invalid_number")]
    assert ed.result.total.mag == 4690.5


def test_directories_pins_trash_restore(window, app) -> None:
    store = window.store
    directory = store.create_directory("", "Work")
    rel = store.create_sheet(directory, "Budget", "$5")
    window.open_sheet(rel)
    store.pin(rel)
    window.sidebar.rebuild()
    top = [window.sidebar.tree.topLevelItem(i).text(0) for i in range(4)]
    assert top[0] == "PINNED"
    window.trash(rel)
    assert window.current[1] != rel
    assert store.trashed()[0][1] == "Work/Budget.txt"
    window.restore(store.trashed()[0][0])
    assert window.current == ("sheet", "Work/Budget.txt")


def test_trashed_directory_shows_its_sheets(window, app) -> None:
    store = window.store
    store.create_directory("", "Work")
    store.create_directory("Work", "Plans")
    store.create_sheet("Work/Plans", "Budget", "123")
    window.trash("Work")
    root = window.sidebar.tree
    trash = root.topLevelItem(root.topLevelItemCount() - 1)
    work = trash.child(0)
    assert work.text(0) == "Work"
    plans = work.child(0)
    assert plans.text(0) == "Plans"
    budget = plans.child(0)
    assert budget.text(0) == "Budget"
    window.sidebar._clicked(budget)
    assert window.editor.toPlainText() == "123"
    window.restore("Work")
    assert window.current == ("sheet", "Work/Plans/Budget.txt")
    assert window.editor.toPlainText() == "123"


def test_restoring_a_directory_with_a_txt_suffix(window, monkeypatch) -> None:
    store = window.store
    directory = store.create_directory(name="Archive.txt")
    sheet = store.create_sheet(directory, "Budget", "123")
    current = window.current
    warnings = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args[-1]))
    window.trash(directory)
    name, _ = store.trashed()[0]

    window.restore(name)

    assert warnings == []
    assert window.current == current
    assert store.read(sheet) == "123"
    assert window.sidebar._find(DIRECTORY, directory) is not None


def test_trash_directories_stay_above_sheets(window) -> None:
    store = window.store
    store.create_sheet("", "A", "1")
    store.create_directory("", "Z")
    window.trash("A.txt")
    window.trash("Z")
    trash = window.sidebar.tree.topLevelItem(window.sidebar.tree.topLevelItemCount() - 1)
    assert [trash.child(i).text(0) for i in range(trash.childCount())] == ["Z", "A"]


def test_trashed_directories_with_same_name_show_original_locations(window) -> None:
    store = window.store
    store.create_directory("", "New directory")
    store.create_directory("New directory", "New directory 2")
    store.create_directory("", "New directory 2")
    store.create_sheet("New directory/New directory 2", "Inside", "1")
    store.create_sheet("New directory 2", "Outside", "2")
    window.trash("New directory/New directory 2")
    window.trash("New directory 2")
    trash = window.sidebar.tree.topLevelItem(window.sidebar.tree.topLevelItemCount() - 1)
    entries = {trash.child(i).text(0): trash.child(i) for i in range(trash.childCount())}
    assert set(entries) == {"New directory", "New directory 2"}
    parent = entries["New directory"]
    assert parent.childCount() == 1
    assert parent.child(0).text(0) == "New directory 2"
    assert parent.child(0).child(0).text(0) == "Inside"
    assert entries["New directory 2"].child(0).text(0) == "Outside"
    for name, _original in store.trashed():
        window.restore(name)
    assert store.read("New directory/New directory 2/Inside.txt") == "1"
    assert store.read("New directory 2/Outside.txt") == "2"


def test_trash_combines_original_paths_with_a_deleted_parent(window) -> None:
    store = window.store
    store.create_directory("", "Work")
    store.create_directory("Work", "Plans")
    store.create_sheet("Work/Plans", "Old", "1")
    store.create_sheet("Work/Plans", "Current", "2")
    window.trash("Work/Plans/Old.txt")
    window.trash("Work")
    trash = window.sidebar.tree.topLevelItem(window.sidebar.tree.topLevelItemCount() - 1)
    assert trash.childCount() == 1
    work = trash.child(0)
    assert work.text(0) == "Work"
    assert work.childCount() == 1
    plans = work.child(0)
    assert plans.text(0) == "Plans"
    assert {plans.child(i).text(0) for i in range(plans.childCount())} == {"Old", "Current"}


@pytest.mark.parametrize("action_name", ["new_directory", "move_to_trash"])
def test_sidebar_context_menu_finishes_before_action(window, app, action_name) -> None:
    sidebar = window.sidebar
    sheet = window.current[1]
    calls = []
    during_menu = []
    signal = sidebar.new_directory if action_name == "new_directory" else sidebar.trash
    signal.disconnect()
    signal.connect(lambda path: calls.append(path))

    def choose():
        menu = QApplication.activePopupWidget()
        assert isinstance(menu, QMenu)
        action = next(a for a in menu.actions() if a.text() == window.t(action_name))
        menu.setActiveAction(action)
        QTest.keyClick(menu, Qt.Key.Key_Return)
        during_menu.extend(calls)

    QTimer.singleShot(0, choose)
    item = sidebar.tree.topLevelItem(0)
    if action_name == "move_to_trash":
        item = item.child(0)
    sidebar._menu(sidebar.tree.visualItemRect(item).center())
    assert during_menu == []
    assert calls == []
    pump(app)
    assert calls == ([""] if action_name == "new_directory" else [sheet])


def test_context_menu_trashes_directory_with_open_nested_sheet(window, app) -> None:
    store = window.store
    store.create_directory("", "Work")
    store.create_directory("Work", "Plans")
    store.create_sheet("Work/Plans", "Budget", "123")
    window.open_sheet("Work/Plans/Budget.txt")
    window.sidebar.rebuild()
    directory = window.sidebar._find("directory", "Work")
    assert directory is not None

    def choose():
        menu = QApplication.activePopupWidget()
        assert isinstance(menu, QMenu)
        action = next(a for a in menu.actions() if a.text() == window.t("move_to_trash"))
        menu.setActiveAction(action)
        QTest.keyClick(menu, Qt.Key.Key_Return)

    QTimer.singleShot(0, choose)
    pos = window.sidebar.tree.visualItemRect(directory).center()
    window.sidebar._menu(pos)
    pump(app)
    assert not store.path("Work").exists()
    assert store.read_trashed("Work/Plans/Budget.txt") == "123"
    assert window.current != ("sheet", "Work/Plans/Budget.txt")


def test_trashing_directory_releases_watches_before_move(window, monkeypatch) -> None:
    store = window.store
    store.create_directory("", "Work")
    store.create_directory("Work", "Plans")
    store.create_sheet("Work/Plans", "Budget", "123")
    window.open_sheet("Work/Plans/Budget.txt")
    window.sidebar.rebuild()
    directory = store.path("Work")
    assert str(directory) in window.sidebar.watcher.directories()
    assert window.file_watcher.files()
    trash = store.trash

    def move(rel):
        assert all(
            not Path(p).is_relative_to(directory) for p in window.sidebar.watcher.directories()
        )
        assert all(not Path(p).is_relative_to(directory) for p in window.file_watcher.files())
        return trash(rel)

    monkeypatch.setattr(store, "trash", move)
    window.trash("Work")
    assert store.read_trashed("Work/Plans/Budget.txt") == "123"


def test_creating_a_directory_selects_it_in_the_sidebar(window) -> None:
    sidebar = window.sidebar
    directory = window.store.create_directory(name="Work")
    sidebar.rebuild()
    sidebar.tree.setCurrentItem(sidebar._find(DIRECTORY, directory))
    current = window.current

    sidebar.btn_directory.click()

    created = f"{directory}/{window.t('directory')}"
    assert window.store.path(created).is_dir()
    assert sidebar.tree.currentItem().data(0, ROLE) == (DIRECTORY, created)
    assert window.current == current


@pytest.mark.parametrize("open_inside", [False, True])
def test_deleting_a_directory_selects_the_next_sibling(window, open_inside) -> None:
    store, sidebar = window.store, window.sidebar
    initial = window.current
    parent = store.create_directory(name="Work")
    removed = store.create_directory(parent, "First")
    next_directory = store.create_directory(parent, "Second")
    sheet = store.create_sheet(removed, "Budget", "123")
    if open_inside:
        window.open_sheet(sheet)
    sidebar.rebuild()
    sidebar.tree.setCurrentItem(sidebar._find(DIRECTORY, removed))

    sidebar.delete_current()

    assert not store.path(removed).exists()
    assert sidebar.tree.currentItem().data(0, ROLE) == (DIRECTORY, next_directory)
    sidebar.rebuild()
    assert sidebar.tree.currentItem().data(0, ROLE) == (DIRECTORY, next_directory)
    assert window.current == initial


def test_failed_directory_trash_restores_watches(window, monkeypatch) -> None:
    store = window.store
    store.create_directory("", "Work")
    sheet = store.create_sheet("Work", "Budget", "123")
    window.open_sheet(sheet)
    window.sidebar.rebuild()
    directory = str(store.path("Work"))
    sheet_path = str(store.path(sheet))
    warnings = []

    def fail(_rel):
        raise PermissionError("access denied")

    monkeypatch.setattr(store, "trash", fail)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: warnings.append(args))
    window.trash("Work")
    assert warnings
    assert directory in window.sidebar.watcher.directories()
    assert sheet_path in window.file_watcher.files()
    assert window.current == ("sheet", sheet)


def test_search_filters_sheets(window, app) -> None:
    window.store.create_sheet("", "Holiday", "flights $400")
    window.sidebar.search.setText("flights")
    pump(app)
    tree = window.sidebar.tree
    assert [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())] == ["Holiday"]


def test_sidebar_watches_only_real_sheet_directories(window, tmp_path: Path) -> None:
    root = window.store.root
    window.store.create_directory(name="Work")
    (root / ".hidden").mkdir()
    window.store.trash_dir.mkdir()
    outside = tmp_path / "Music"
    outside.mkdir()
    try:
        (root / "linked").symlink_to(outside, target_is_directory=True)
        (root / "cycle").symlink_to(root, target_is_directory=True)
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {exc}")
    window.sidebar.rebuild()
    assert {Path(p) for p in window.sidebar.watcher.directories()} == {
        root,
        root / "Work",
        window.store.trash_dir,
    }


def test_comment_toggle_and_copy(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("2 + 2")
    pump(app)
    window._copy_current_result()
    assert QGuiApplication.clipboard().text() == "4"
    window.editor.toggle_comment()
    assert window.editor.toPlainText() == "// 2 + 2"
    window.editor.toggle_comment()
    assert window.editor.toPlainText() == "2 + 2"


def test_help_is_read_only_and_translated(window, app) -> None:
    window.open_help()
    assert window.editor.isReadOnly()
    window.set_language("uk")
    assert window.editor.toPlainText().startswith("# Ласкаво просимо")
    assert window.menuBar().actions()[0].text() == "&Файл"
    window.set_language("en")


def test_settings_language_change_reloads_open_help(window, monkeypatch) -> None:
    window.open_help()

    def accept(dialog):
        dialog.language.setCurrentIndex(dialog.language.findData("uk"))
        return SettingsDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", accept)
    window.open_settings()
    assert window.editor.toPlainText().startswith("# Ласкаво просимо")
    assert window.editor.isReadOnly()


def test_settings_number_format_reloads_open_help(window, monkeypatch) -> None:
    now = window.editor.config.now()
    engine_config = Settings.engine_config
    monkeypatch.setattr(
        Settings, "engine_config", lambda s: replace(engine_config(s), now=lambda: now)
    )
    window.apply_settings()
    window.open_help()
    ed = window.editor
    assert "round(3.14159; 2)" in ed.toPlainText()
    values = [line.value for line in ed.result.lines]

    def accept(dialog):
        dialog.number_style.setCurrentIndex(dialog.number_style.findData("space_comma"))
        return SettingsDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", accept)
    window.open_settings()
    assert "round(3,14159; 2)" in ed.toPlainText()
    assert "1\u202f234,56" in sheet_text(ed.document())
    assert ed.isReadOnly()
    assert [line.value for line in ed.result.lines] == values


def test_theme_switch(window, app) -> None:
    window.set_theme("light")
    assert QApplication.palette().base().color().name() == "#f8fafc"
    window.set_theme("dark")
    assert QApplication.palette().base().color().name() == "#0f172a"


def test_colours_switch(window, app) -> None:
    window.set_colours("ember")
    assert QApplication.palette().base().color().name() == "#1a1b20"
    window.set_theme("light")
    assert QApplication.palette().base().color().name() == "#fbfbf9"
    window.set_theme("dark")
    window.set_colours("glacier")
    assert QApplication.palette().base().color().name() == "#0f172a"


@pytest.mark.parametrize(
    ("colours", "mode", "accent", "selection", "fill", "on_fill"),
    [
        ("ember", "dark", "#f0a35e", "#45382e", "#ec9550", "#1a1b20"),
        ("ember", "light", "#c2410c", "#f6dcc3", "#9a3412", "#ffffff"),
        ("glacier", "dark", "#60a5fa", "#1c3767", "#1d4ed8", "#ffffff"),
        ("glacier", "light", "#2563eb", "#dbeafe", "#1d4ed8", "#ffffff"),
    ],
)
def test_each_theme_uses_its_accent(
    window, app, colours, mode, accent, selection, fill, on_fill
) -> None:
    # links, selection and focus borders follow each theme's accent; main buttons its fill
    window.set_colours(colours)
    window.set_theme(mode)
    palette = QApplication.palette()
    assert palette.link().color().name() == accent
    assert palette.highlight().color().name() == selection
    sheet = app.styleSheet()
    assert f"QLineEdit#search:focus {{ border-color: {accent}; }}" in sheet
    assert f"QPushButton:focus {{ border-color: {accent}; }}" in sheet
    assert f"stop: 1 {fill});" in sheet
    assert f"color: {on_fill}; font-weight: 600;" in sheet


@pytest.mark.parametrize("colours", ["glacier", "ember"])
def test_main_button_text_is_readable(window, app, colours) -> None:
    """The main button's text reads at 4.5:1 or more on all of its gradient, at rest and on
    hover, in both modes."""

    def luminance(name: str) -> float:
        c = QColor(name)
        channels = [v / 255 for v in (c.red(), c.green(), c.blue())]
        lin = [v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4 for v in channels]
        return 0.2126 * lin[0] + 0.7152 * lin[1] + 0.0722 * lin[2]

    for mode in ("dark", "light"):
        window.set_colours(colours)
        window.set_theme(mode)
        t = window.theme
        for fill in (t.fill_top, t.fill, themes.lighter(t.fill)):
            hi, lo = sorted((luminance(fill), luminance(t.on_fill)), reverse=True)
            assert (hi + 0.05) / (lo + 0.05) >= 4.5, (colours, mode, fill)
        assert f"stop: 0 {t.fill_top}, stop: 1 {themes.lighter(t.fill)});" in app.styleSheet()


def test_dialog_button_has_no_extra_inner_focus_rectangle(window) -> None:
    button = QPushButton("Delete", window)
    option = QStyleOptionFocusRect()
    option.initFrom(button)
    option.rect = QRect(2, 2, 80, 24)
    option.state |= QStyle.StateFlag.State_HasFocus | QStyle.StateFlag.State_KeyboardFocusChange
    image = QImage(100, 40, QImage.Format.Format_ARGB32)
    image.fill(QColor("white"))
    painter = QPainter(image)
    themes._style[0].drawPrimitive(
        QStyle.PrimitiveElement.PE_FrameFocusRect, option, painter, button
    )
    painter.end()
    assert all(image.pixelColor(x, y) == QColor("white") for y in range(40) for x in range(100))


def test_default_formats_are_independent_of_ui_language(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("1,234.5 + 10\n5 кг у г\n15:45")
    window.set_language("uk")
    pump(app)
    assert window.editor.result_text(0) == "1,244.5"
    assert window.editor.result_text(1) == "5,000 г"
    assert window.editor.result_text(2) == "15:45"
    window.set_language("en")
    assert window.editor.result_text(0) == "1,244.5"
    assert window.editor.result_text(2) == "15:45"


def test_line_numbers_toggle(window, app) -> None:
    ed = window.editor
    assert ed.gutter.isVisible()
    assert ed.viewportMargins().left() == ed.gutter.width_needed()
    window._toggle_line_numbers()
    assert not ed.gutter.isVisible()
    assert ed.viewportMargins().left() == 0
    window._toggle_line_numbers()
    assert ed.gutter.isVisible()


def test_menu_icons(window) -> None:
    file_menu = window.menuBar().actions()[0].menu()
    first = file_menu.actions()[0]
    assert not first.icon().isNull()
    view = window.menuBar().actions()[2].menu()
    top = window._actions["always_on_top"]
    assert not top.icon().isNull()
    checkable = [a for a in view.actions() if a.isCheckable() and a is not top]
    assert checkable and all(a.icon().isNull() for a in checkable)


def test_icons_are_coloured_from_the_start(window) -> None:
    trash = window.menuBar().actions()[0].menu().actions()[-1]  # Quit, red group
    image = trash.icon().pixmap(icons.ICON_SIZE).toImage()
    colours = {
        QColor(image.pixel(x, y)).name()
        for x in range(image.width())
        for y in range(image.height())
        if QColor.fromRgba(image.pixel(x, y)).alpha() == 255
    }
    assert icons.color_for("quit") in colours


def test_sidebar_toggle_keeps_the_tick_and_survives_a_restart(window, app, open_window) -> None:
    tick = window._actions["toggle_sidebar"]
    window.sidebar_button.click()
    assert window.sidebar.isHidden() and not tick.isChecked()
    window._focus_search()  # Ctrl+P shows the sidebar again and ticks the menu item
    assert not window.sidebar.isHidden() and tick.isChecked()
    tick.trigger()
    window.close()
    w = open_window()
    pump(app)
    assert w.sidebar.isHidden() and not w._actions["toggle_sidebar"].isChecked()
    w.set_sidebar_visible(True)
    w.splitter.moveSplitter(0, 1)  # the divider dragged all the way left
    assert w.splitter.sizes()[0] > 0


def test_focus_mode_hides_everything_but_the_sheet(window, app) -> None:
    keys = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    window.activateWindow()
    assert QTest.qWaitForWindowActive(window)
    hidden_in_focus = (window.menuBar(), window.sidebar, window.rates_label)
    QTest.keyClick(window.editor, Qt.Key.Key_F, keys)
    assert all(w.isHidden() for w in hidden_in_focus) and window._actions["focus_mode"].isChecked()
    assert window.editor.isVisible() and window.total_label.isVisible()
    window.set_language("uk")  # rebuilding the menus keeps focus mode and its shortcut
    assert window.menuBar().isHidden() and window._actions["focus_mode"].isChecked()
    QTest.keyClick(window.editor, Qt.Key.Key_F, keys)  # works with the menu bar hidden
    assert not any(w.isHidden() for w in hidden_in_focus)
    window.set_language("en")


def test_focus_mode_brings_the_sidebar_back_as_it_was(window, app, open_window) -> None:
    window.set_sidebar_visible(False)
    window.set_focus_mode(True)
    window.close()
    w = open_window()  # focus mode survives a restart
    pump(app)
    assert w.menuBar().isHidden() and w.sidebar.isHidden()
    w.set_focus_mode(False)
    assert not w.menuBar().isHidden() and w.sidebar.isHidden()  # it was hidden before
    w.set_sidebar_visible(True)
    w.set_focus_mode(True)
    w.close()
    w = open_window()
    pump(app)
    w.set_focus_mode(False)
    assert not w.sidebar.isHidden()


@pytest.mark.parametrize(
    ("platform", "help_key", "shortcuts_key", "spelling_key"),
    [
        ("darwin", "Ctrl+Shift+H", "Ctrl+Shift+K", "Ctrl+Alt+S"),
        ("linux", "F1", "Shift+F1", "F7"),
        ("win32", "F1", "Shift+F1", "F7"),
    ],
)
def test_platform_help_shortcuts_and_spelling(
    window, app, monkeypatch: pytest.MonkeyPatch, platform, help_key, shortcuts_key, spelling_key
) -> None:
    monkeypatch.setattr(main_window, "sys", SimpleNamespace(platform=platform))
    window.spell_status = Status(library=True, dictionaries={"en": "/x/en_US"})
    window._spell = FakeSpell()
    window.build_menus()
    keys = {
        "help_sheet": help_key,
        "shortcuts": shortcuts_key,
        "toggle_spelling": spelling_key,
    }
    for name, key in keys.items():
        assert window._actions[name].shortcuts() == [QKeySequence(key)]  # no extra aliases
    opened: list[ShortcutsDialog] = []
    monkeypatch.setattr(ShortcutsDialog, "exec", lambda dialog: opened.append(dialog) or 0)
    window.activateWindow()
    assert QTest.qWaitForWindowActive(window)
    QTest.keySequence(window.editor, QKeySequence(help_key))
    assert window.current[0] == HELP
    QTest.keySequence(window.editor, QKeySequence(shortcuts_key))
    assert len(opened) == 1
    window.new_sheet("")
    QTest.keySequence(window.editor, QKeySequence(spelling_key))
    assert window.settings.spell_check and window.editor.spell is window._spell
    window.set_language("uk")
    for name, key in keys.items():
        assert window._actions[name].shortcuts() == [QKeySequence(key)]
    QTest.keySequence(window.editor, QKeySequence(spelling_key))
    assert not window.settings.spell_check and window.editor.spell is None


def test_shortcuts_dialog_lists_menu_and_sidebar_keys(window) -> None:
    rows = dict(ShortcutsDialog(window.menuBar(), window.t, window).rows())
    assert rows["New Sheet"] == key_text(QKeySequence.StandardKey.New)
    assert rows["Comment Line"] == key_text("Ctrl+/")
    assert rows["Line Numbers"] == key_text("Ctrl+Shift+L")
    assert rows["Rename"] == "F2"
    mac = sys.platform == "darwin"
    assert rows["Help Sheet"] == key_text("Ctrl+Shift+H" if mac else "F1")
    assert rows["Keyboard Shortcuts"] == key_text("Ctrl+Shift+K" if mac else "Shift+F1")


def test_find_next_and_previous_have_no_extra_shortcuts(window) -> None:
    assert not window._actions["find_next"].shortcuts()
    assert not window._actions["find_previous"].shortcuts()
    assert window._actions["find_next"].text().endswith("\tEnter")
    assert window._actions["find_previous"].text().endswith("\tShift+Enter")
    rows = dict(ShortcutsDialog(window.menuBar(), window.t, window).rows())
    assert rows["Find Next"] == "Enter"
    assert rows["Find Previous"] == "Shift+Enter"


def test_find_labels_do_not_intercept_enter_in_sheet(window, app) -> None:
    window.new_sheet("")
    window.editor.setFocus()
    QTest.keyClicks(window.editor, "10")
    QTest.keyClick(window.editor, Qt.Key.Key_Return)
    QTest.keyClicks(window.editor, "20")
    assert window.editor.toPlainText() == "10\n20"


def test_qt_buttons_follow_language(window) -> None:
    window.set_language("uk")
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    assert box.button(QDialogButtonBox.StandardButton.Close).text().replace("&", "") == "Закрити"
    window.set_language("en")
    box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
    assert box.button(QDialogButtonBox.StandardButton.Close).text().replace("&", "") == "Close"


def test_ligatures_form_across_coloured_operators(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("a = 5\na <= 6 -> 7 >= a")
    pump(app)
    block = window.editor.document().findBlockByNumber(1)
    ranges = {(r.start, r.length) for r in block.layout().formats()}
    assert (2, 2) in ranges  # "<=" coloured as one piece
    assert (7, 2) in ranges  # "->"

    def shot(on: bool):
        window.settings.ligatures = on
        window.apply_settings()
        pump(app)
        return window.editor.viewport().grab().toImage()

    assert shot(True) != shot(False)
    window.settings.ligatures = True
    window.apply_settings()


def test_settings_dialog_round_trip(window) -> None:
    prefs = replace(window.settings, number_style="space_comma", time_format="12h")
    dlg = SettingsDialog(prefs, window.t, window)
    pages = [dlg.nav.item(i).text() for i in range(dlg.nav.count())]
    assert pages == ["General", "Appearance", "Numbers", "Exchange Rates", "Spell Check", "Vim"]
    assert dlg.pages.count() == len(pages)
    assert dlg.number_style.count() == 4
    assert dlg.time_format.count() == 2
    assert dlg.number_style.currentData() == prefs.number_style
    assert dlg.time_format.currentData() == prefs.time_format
    dlg.max_decimals.setValue(4)
    dlg.rates_url.setText(" https://example.invalid/rates.json ")
    dlg.dollar.setCurrentText("cad")
    new = dlg.result_settings()
    assert (new.max_decimals, new.rates_url, new.dollar) == (
        4,
        "https://example.invalid/rates.json",
        "CAD",
    )
    assert new.money_decimals == window.settings.money_decimals


def test_settings_selector_border_changes_when_focused(window, app) -> None:
    dlg = SettingsDialog(window.settings, window.t, window)
    dlg.show()
    try:
        dlg.sheets_dir.setFocus()
        pump(app)
        assert not dlg.language.hasFocus()
        normal = dlg.language.grab().toImage()
        edge = normal.pixelColor(normal.width() // 2, 0)
        assert edge.name() not in (window.theme.bg, window.theme.border)

        dlg.language.setFocus()
        pump(app)
        assert dlg.language.hasFocus()
        focused = dlg.language.grab().toImage()
        assert focused.pixelColor(focused.width() // 2, 0) == QColor(window.theme.accent)
    finally:
        dlg.close()


@pytest.mark.parametrize("same_name", [False, True])
def test_settings_switch_to_directory_with_directory_link(
    window, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, same_name: bool
) -> None:
    old_store = window.store
    old_sheet = window.current[1]
    documents = tmp_path / "Documents"
    store = SheetStore(documents)
    store.create_directory(name="Work")
    new_sheet = old_sheet if same_name else "Work/Budget.txt"
    store.write(new_sheet, "5 + 6")
    music = tmp_path / "Music"
    music.mkdir()
    (music / "Other.txt").write_text("outside the sheets directory", encoding="utf-8")
    link = documents / "My Music"
    if sys.platform == "win32":
        subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(music)],
            check=True,
            capture_output=True,
        )
        assert link.is_junction()
    else:
        link.symlink_to(music, target_is_directory=True)

    window.editor.setPlainText("7 + 8")
    assert window._dirty, (
        f"edit was not marked for saving: current={window.current}, "
        f"read_only={window.editor.isReadOnly()}, signals_blocked={window.editor.signalsBlocked()}"
    )
    monkeypatch.setattr(
        settings_dialog.QFileDialog, "getExistingDirectory", lambda *_: str(documents)
    )

    def accept(dialog):
        dialog._browse()
        return SettingsDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", accept)
    window.open_settings()

    assert old_store.read(old_sheet) == "7 + 8", window.message_label.text()
    assert window.store.root == documents
    assert window.sidebar.store is window.store
    assert window.settings.sheets_dir == str(documents)
    assert Settings.load().sheets_dir == str(documents)
    assert window.current == ("sheet", new_sheet)
    assert window.editor.toPlainText() == "5 + 6"
    assert window.store.read(new_sheet) == "5 + 6"
    assert window.store.all_sheets() == [new_sheet]
    assert {Path(p) for p in window.sidebar.watcher.directories()} == {
        documents,
        documents / "Work",
    }


def test_settings_keeps_unsaved_sheet_when_save_fails(
    window, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    old_store = window.store
    old_sheet = window.current[1]
    old_text = old_store.read(old_sheet)
    old_settings = window.settings
    window.editor.setPlainText("7 + 8")
    document = window.editor.document()
    destination = tmp_path / "other-sheets"
    store = SheetStore(destination)
    store.write(old_sheet, "5 + 6")

    def accept(dialog):
        dialog.sheets_dir.setText(str(destination))
        return SettingsDialog.DialogCode.Accepted

    def fail_save(rel, text):
        raise PermissionError("sheet is locked")

    monkeypatch.setattr(SettingsDialog, "exec", accept)
    with monkeypatch.context() as blocked:
        blocked.setattr(old_store, "write", fail_save)
        window.open_settings()

    assert window.store is old_store
    assert window.sidebar.store is old_store
    assert window.settings is old_settings
    assert Settings.load().sheets_dir == str(old_store.root)
    assert window.current == ("sheet", old_sheet)
    assert window.editor.document() is document
    assert window.editor.toPlainText() == "7 + 8"
    assert window._dirty
    assert old_store.read(old_sheet) == old_text
    assert store.read(old_sheet) == "5 + 6"
    assert window.message_label.text() == "sheet is locked"

    window.open_settings()

    assert old_store.read(old_sheet) == "7 + 8"
    assert window.store.root == destination
    assert window.sidebar.store is window.store
    assert Settings.load().sheets_dir == str(destination)
    assert window.current == ("sheet", old_sheet)
    assert window.editor.toPlainText() == "5 + 6"
    assert window.store.read(old_sheet) == "5 + 6"
    assert not window._dirty


def test_dialog_buttons_have_no_stock_icons(app) -> None:
    assert app.style().styleHint(QStyle.StyleHint.SH_DialogButtonBox_ButtonsHaveIcons) == 0


def test_ligature_sample_follows_checkbox(window) -> None:
    dlg = SettingsDialog(window.settings, window.t, window)
    calt = QFont.Tag("calt")
    dlg.ligatures.setChecked(False)
    assert dlg.ligature_sample.font().featureValue(calt) == 0
    dlg.ligatures.setChecked(True)
    assert not dlg.ligature_sample.font().isFeatureSet(calt)


def test_a_freed_sidebar_leaves_no_timer_behind(app, tmp_path, monkeypatch) -> None:
    """A rebuild turns the tree's animation back on from a timer. The window fixture
    frees each window before that timer fires, so the timer must go with the sidebar."""
    errors: list[BaseException] = []
    monkeypatch.setattr(sys, "excepthook", lambda _type, error, _tb: errors.append(error))
    sidebar = Sidebar(SheetStore(tmp_path / "sheets"), lambda key, **_: key)
    sidebar.rebuild()
    shiboken6.delete(sidebar)
    app.processEvents()
    assert errors == []


def test_sidebar_draws_one_highlight_per_row(window, app) -> None:
    window.store.create_directory("", "Work")
    rel = window.store.create_sheet("Work", "Budget", "1")
    window.sidebar.expanded.add("Work")
    window.open_sheet(rel)
    pump(app)
    tree = window.sidebar.tree
    item = tree.currentItem()
    row = tree.visualItemRect(item)
    image = tree.viewport().grab().toImage()
    y = row.center().y()
    # the highlight starts at the left edge, in the indent, not only under the text
    assert image.pixelColor(6, y) == tree.palette().highlight().color()


def test_switching_sheets_between_directories_keeps_the_sidebar_still(
    app, tmp_path, window_settings, open_window
) -> None:
    """Startup: directory A closed, B open, last sheet in A. Switching between them must not
    close A again or move any row (it used to collapse A, so the list jumped)."""
    sheets = tmp_path / "sheets"
    store = SheetStore(sheets)
    for directory in ("A", "B"):
        store.create_directory("", directory)
        for n in range(3):
            store.create_sheet(directory, f"{directory}{n}", "1")
    window_settings.setValue("sheets_dir", str(sheets))
    window_settings.setValue("last_sheet", "A/A1.txt")
    window_settings.setValue("sidebar/expanded", ["B"])
    w = open_window()
    pump(app)
    tree = w.sidebar.tree

    def row_of(name: str) -> int:
        item = tree.findItems(name, Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive)[0]
        return tree.visualItemRect(item).y()

    directory_a = tree.findItems("A", Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive)[0]
    assert directory_a.isExpanded()
    before = {name: row_of(name) for name in ("A0", "B0", "B2")}
    items_before = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    for rel in ("B/B2.txt", "A/A0.txt", "B/B0.txt", "A/A2.txt"):
        w.open_sheet(rel)
        pump(app)
        assert directory_a.isExpanded()
        assert {name: row_of(name) for name in before} == before
    # the same row objects: nothing was rebuilt
    assert [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())] == items_before
    assert "A" in w.sidebar.expanded


def test_unknown_settings_fall_back_to_defaults(app) -> None:
    """A hand-edited or newer config must not leave the app in a state it can't show."""
    qs = QSettings()
    qs.clear()
    for key, value in {
        "language": "xx",
        "theme": "zzz",
        "colours": "zzz",
        "number_style": "bogus",
        "time_format": "bogus",
        "dollar": "XYZ",
        "font_size": "abc",
        "max_decimals": "999",
    }.items():
        qs.setValue(key, value)
    qs.sync()
    s = Settings.load()
    qs.clear()
    assert (s.language, s.theme, s.number_style, s.time_format, s.dollar) == (
        "en",
        "dark",
        "comma_dot",
        "24h",
        "USD",
    )
    assert (s.font_size, s.max_decimals) == (14, 20)
    assert s.colours == "glacier"


@pytest.mark.parametrize(
    ("saved", "expected"),
    [
        ((None, None), ("comma_dot", "24h")),
        (("auto", "auto"), ("comma_dot", "24h")),
        (("dot_comma", "12h"), ("dot_comma", "12h")),
        (("space_comma", "auto"), ("space_comma", "24h")),
        (("auto", "12h"), ("comma_dot", "12h")),
    ],
)
def test_format_preferences_on_startup(window_settings, open_window, saved, expected) -> None:
    for key, value in zip(("number_style", "time_format"), saved, strict=True):
        if value is None:
            window_settings.remove(key)
        else:
            window_settings.setValue(key, value)

    restored = open_window()
    assert (restored.settings.number_style, restored.settings.time_format) == expected
    assert restored.editor.config.number_style == expected[0]
    assert restored.editor.opts.time_24h == (expected[1] == "24h")


def test_legacy_date_order_uses_24_hour_default(window_settings, open_window, monkeypatch) -> None:
    window_settings.setValue("date_order", "MDY")
    restored = open_window()
    restored.open_sheet(restored.store.create_sheet("", "Time", "15:45"))
    assert restored.settings.time_format == "24h"
    assert restored.editor.result_text(0) == "15:45"

    def accept(dialog):
        dialog.time_format.setCurrentIndex(dialog.time_format.findData("12h"))
        return SettingsDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", accept)
    restored.open_settings()
    assert restored.editor.result_text(0) == "3:45pm"
    assert Settings.load().time_format == "12h"
    assert open_window().editor.result_text(0) == "3:45pm"


@pytest.mark.parametrize(
    "action", ["other_sheet", "same_sheet", "help", "trashed", "new", "rename", "trash", "close"]
)
def test_failed_save_keeps_edited_sheet_open(window, monkeypatch, action) -> None:
    store = window.store
    first = store.create_sheet("", "First", "1 + 1")
    second = store.create_sheet("", "Second", "2 + 2")
    trashed = store.trash(store.create_sheet("", "Discard", "3 + 3"))
    window.open_sheet(first)
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.insertPlainText(" + 5")
    document = window.editor.document()
    watched = window.file_watcher.files()
    sheets = store.all_sheets()
    actions = {
        "other_sheet": partial(window.open_sheet, second),
        "same_sheet": partial(window.open_sheet, first),
        "help": window.open_help,
        "trashed": partial(window.open_trashed, trashed),
        "new": window.new_sheet,
        "rename": partial(window.rename, first),
        "trash": partial(window.trash, first),
        "close": window.close,
    }

    def fail_save(rel, text):
        raise PermissionError("sheet is locked")

    with monkeypatch.context() as blocked:
        blocked.setattr(store, "write", fail_save)
        blocked.setattr(window, "_ask_text", lambda *_: ("Renamed", True))
        actions[action]()

    assert window.isVisible()
    assert window.current == ("sheet", first)
    assert window.editor.document() is document
    assert window.editor.toPlainText() == "1 + 1 + 5"
    assert window._dirty
    assert window.file_watcher.files() == watched
    assert window.settings.last_sheet == first
    assert store.all_sheets() == sheets
    assert store.read(first) == "1 + 1"
    assert window.message_label.text() == "sheet is locked"
    window.editor.undo()
    assert window.editor.toPlainText() == "1 + 1"
    window.editor.redo()
    window.save_current()
    assert store.read(first) == "1 + 1 + 5"


def test_reopening_current_sheet_keeps_edits_and_undo(window) -> None:
    first = window.store.create_sheet("", "First", "1 + 1")
    window.open_sheet(first)
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.insertPlainText(" + 5")

    window.open_sheet(first)

    assert window.editor.toPlainText() == "1 + 1 + 5"
    assert window.store.read(first) == "1 + 1 + 5"
    window.editor.undo()
    assert window.editor.toPlainText() == "1 + 1"


def test_save_conflict_can_recover_edits_to_a_separate_sheet(window, monkeypatch) -> None:
    store = window.store
    original = store.create_sheet("Expenses", "Budget", "1 + 1")
    window.open_sheet(original)
    window.editor.setPlainText("local edits")
    store.write(original, "external edits")

    assert not window.save_current()
    assert window.conflict_notice.isVisible()
    assert store.read(original) == "external edits"

    def fail_create(*args):
        raise PermissionError("directory is locked")

    with monkeypatch.context() as blocked:
        blocked.setattr(store, "create_sheet", fail_create)
        blocked.setattr(QMessageBox, "warning", lambda *_: None)
        window.save_copy_button.click()
    assert window.conflict_notice.isVisible()
    assert window.editor.toPlainText() == "local edits"
    assert window.current == ("sheet", original)

    window.save_copy_button.click()
    _, copy = window.current
    assert copy != original and copy.startswith("Expenses/")
    assert store.read(copy) == "local edits"
    assert store.read(original) == "external edits"
    assert window.conflict_notice.isHidden()
    window.open_sheet(original)
    assert window.editor.toPlainText() == "external edits"


def test_failed_trash_preview_reports_error_and_leaves_sheet_open(window, monkeypatch) -> None:
    trashed = window.store.trash(window.store.create_sheet("", "Discard", "1 + 1"))
    current = window.current
    document = window.editor.document()
    messages = []

    def fail_read(name):
        raise PermissionError("sheet is locked")

    monkeypatch.setattr(window.store, "read_trashed", fail_read)
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: messages.append(args[-1]))
    window.open_trashed(trashed)

    assert window.current == current
    assert window.editor.document() is document
    assert len(messages) == 1 and "Discard" in messages[0] and "sheet is locked" in messages[0]


def test_undo_survives_switching_sheets(window, app) -> None:
    store = window.store
    first = store.create_sheet("", "First", "1 + 1")
    second = store.create_sheet("", "Second", "2 + 2")
    window.open_sheet(first)
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.insertPlainText(" + 5")
    pump(app)
    window.open_sheet(second)
    window.open_help()
    window.open_sheet(first)
    assert window.editor.toPlainText() == "1 + 1 + 5"
    assert window.editor.textCursor().position() == len("1 + 1 + 5")  # cursor kept too
    assert window.editor.document().isUndoAvailable()
    window.editor.undo()
    pump(app)
    assert window.editor.toPlainText() == "1 + 1"
    assert window.editor.result_text(0) == "2"


def test_tab_is_four_spaces_wide_in_every_sheet(window, app) -> None:
    sheet = window.store.create_sheet("", "Tabs", "a\tb")
    window.open_sheet(sheet)
    editor = window.editor
    for _ in range(2):  # and again after zooming in
        space = editor.fontMetrics().horizontalAdvance(" ")
        assert editor.tabStopDistance() == pytest.approx(space * 4)
        window.zoom(1)
    window.zoom(0)


def test_find_in_sheet(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("rent = $900\nfood = $300\nrent + food")
    pump(app)
    bar = window.find_bar
    bar.open()
    bar.field.setText("RENT")  # any case
    pump(app)
    assert window.editor.match_count() == (1, 2)
    assert bar.count.text() == "1 of 2"
    bar.step()
    assert window.editor.match_count() == (2, 2)
    bar.step()  # goes round to the first
    assert window.editor.match_count() == (1, 2)
    bar.step(backward=True)
    assert window.editor.match_count() == (2, 2)
    bar.field.setText("nothing like this")
    assert bar.count.text() == "No results"
    bar.close_bar()
    assert not bar.isVisible()
    assert window.editor._matches == []
    window.open_help()  # works in the read-only help too
    bar.open()
    bar.field.setText("percent")
    assert window.editor.match_count()[1] > 0


def test_shortcuts_work_while_a_menu_is_open(window, app) -> None:
    fired = []
    help_menu = window.menuBar().actions()[-1].menu()
    refresh = next(a for a in help_menu.actions() if a.text() == "Refresh Exchange Rates")
    refresh.triggered.connect(lambda: fired.append(1))
    help_menu.popup(window.mapToGlobal(window.rect().center()))
    pump(app)
    QTest.keyClick(help_menu, Qt.Key.Key_R, Qt.KeyboardModifier.ControlModifier)
    pump(app)
    assert fired == [1]
    assert QApplication.activePopupWidget() is None


def test_autocomplete_lists_variables_first_with_their_kind(window, app) -> None:
    window.new_sheet("")
    ed = window.editor
    ed.setPlainText("metres_walked = 5 km\n")
    ed.moveCursor(ed.textCursor().MoveOperation.End)
    pump(app)
    QTest.keyClicks(ed, "me")
    pump(app)
    model = ed._completer.completionModel()
    rows = [(model.index(i, 0).data(), model.index(i, 0).data(KIND_ROLE)) for i in range(5)]
    assert rows[0] == ("metres_walked", "variable")
    assert all(kind for _, kind in rows)
    assert ed.kind_label("unit") == "unit"
    ed._completer.popup().hide()


def test_autocomplete_shows_the_kind_as_a_pill_in_its_sheet_colour(window, app) -> None:
    ed = window.editor
    delegate = ed._completer.popup().itemDelegate()
    theme = ed.theme
    assert delegate.kind_colour("variable") == theme.variable
    assert delegate.kind_colour("unit") == theme.unit
    assert delegate.kind_colour("function") == theme.keyword
    assert delegate.kind_colour("keyword") == theme.keyword

    model = QStandardItemModel()
    item = QStandardItem("metres_walked")
    item.setData("variable", KIND_ROLE)
    model.appendRow(item)
    index = model.index(0, 0)
    option = QStyleOptionViewItem()
    option.rect = QRect(QPoint(0, 0), delegate.sizeHint(option, index))
    image = QImage(option.rect.size(), QImage.Format.Format_RGB32)
    surface = QColor(theme.surface)
    image.fill(surface)
    painter = QPainter(image)
    delegate.paint(painter, option, index)
    painter.end()

    # the pill: the variable colour, mostly see-through, over the list's background
    def rgb(c: QColor) -> tuple[int, int, int]:
        return c.red(), c.green(), c.blue()

    alpha = 36 / 255
    expected = [
        round(a * (1 - alpha) + b * alpha)
        for a, b in zip(rgb(surface), rgb(QColor(theme.variable)), strict=True)
    ]
    y = option.rect.height() // 2 + 4  # below the label's middle, inside the pill
    right = [rgb(image.pixelColor(x, y)) for x in range(image.width() // 2, image.width())]
    assert any(all(abs(c - e) <= 3 for c, e in zip(px, expected, strict=True)) for px in right)


def test_autocomplete_long_word_stops_before_the_pill(window, app) -> None:
    """In a row narrower than the word, the word is cut short instead of running under the pill."""
    ed = window.editor
    delegate = ed._completer.popup().itemDelegate()
    theme = ed.theme
    model = QStandardItemModel()
    item = QStandardItem("w" * 80)
    item.setData("variable", KIND_ROLE)
    model.appendRow(item)
    index = model.index(0, 0)
    option = QStyleOptionViewItem()
    option.rect = QRect(0, 0, 220, delegate.sizeHint(option, index).height())
    image = QImage(option.rect.size(), QImage.Format.Format_RGB32)
    image.fill(QColor(theme.surface))
    painter = QPainter(image)
    delegate.paint(painter, option, index)
    painter.end()

    _font, _bold, small = delegate._fonts()
    pill = QFontMetrics(small).horizontalAdvance(ed.kind_label("variable"))
    pill += 2 * delegate.BADGE_PAD
    right = option.rect.right() - 4 - 6  # the row's inner edge, as paint() works it out
    text = QColor(theme.text)

    def is_text(c: QColor) -> bool:
        return (
            max(
                abs(c.red() - text.red()),
                abs(c.green() - text.green()),
                abs(c.blue() - text.blue()),
            )
            < 40
        )

    under_pill = [
        image.pixelColor(x, y) for x in range(right - pill, right) for y in range(image.height())
    ]
    assert not any(is_text(c) for c in under_pill)
    # the word itself is drawn, up to just before the pill
    left = [image.pixelColor(x, y) for x in range(20, 120) for y in range(image.height())]
    assert any(is_text(c) for c in left)


def test_autocomplete_suggests_months(window, app) -> None:
    window.new_sheet("")
    ed = window.editor
    QTest.keyClicks(ed, "jan")
    pump(app)
    model = ed._completer.completionModel()
    assert "january" in [model.index(i, 0).data() for i in range(model.rowCount())]
    assert "січня" in ed._static_words
    ed._completer.popup().hide()


def test_ukrainian_month_autocomplete_after_language_change(window, app) -> None:
    window.set_language("uk")
    window.new_sheet("")
    ed = window.editor
    QTest.keyClicks(ed, "18 ")
    for letter in "січ":
        QApplication.sendEvent(
            ed, QKeyEvent(QEvent.Type.KeyPress, 0, Qt.KeyboardModifier.NoModifier, letter)
        )
    pump(app)
    model = ed._completer.completionModel()
    assert "січня" in [model.index(i, 0).data() for i in range(model.rowCount())]
    assert ed._completer.popup().isVisible()
    QTest.keyClick(ed, Qt.Key.Key_Return)
    assert ed.toPlainText() == "18 січня"


def test_ukrainian_month_completion_for_input_method(window, app) -> None:
    window.set_language("uk")
    window.new_sheet("")
    ed = window.editor
    QTest.keyClicks(ed, "18 ")
    for letter in "січ":
        event = QInputMethodEvent()
        event.setCommitString(letter)
        QApplication.sendEvent(ed, event)
    pump(app)
    assert ed._completer.popup().isVisible()
    QTest.keyClick(ed, Qt.Key.Key_Return)
    assert ed.toPlainText() == "18 січня"


def test_failed_rates_url_test_is_red(window, app, monkeypatch) -> None:
    dlg = SettingsDialog(window.settings, window.t, window)
    result = (None, "<b>Host not found</b>")
    monkeypatch.setattr(settings_dialog, "fetch_rates", lambda manager, url, done: done(*result))
    dlg.rates_url.setText("https://example.invalid/rates")
    dlg._test_url()
    pump(app)
    assert "<b>Host not found</b>" in dlg.test_result.text()
    assert dlg.test_result.textFormat() == Qt.TextFormat.PlainText
    assert window.rates_label.textFormat() == Qt.TextFormat.PlainText
    dlg.test_result.ensurePolished()
    assert (
        dlg.test_result.palette().color(dlg.test_result.foregroundRole()).name()
        == window.theme.error
    )
    result = (RateTable.parse('{"base":"USD","rates":{"EUR":0.9}}'), "")
    dlg._test_url()
    assert dlg.test_result.text() == window.t("test_ok", count=2, base="USD")
    assert (
        dlg.test_result.palette().color(dlg.test_result.foregroundRole()).name()
        != window.theme.error
    )


def test_sheet_scrollbar_shows_while_scrolling_then_fades(window, app) -> None:
    window.open_help()
    pump(app)
    bar = window.editor.verticalScrollBar()
    assert isinstance(bar, SheetScrollBar)
    # Settle layout and leave the scrollbar before simulating a scroll and idle period.
    QCoreApplication.sendEvent(bar, QEvent(QEvent.Type.Leave))
    timer = bar._hide_timer
    timer.stop()
    assert bar.maximum() > bar.minimum()
    bar.setValue(bar.maximum() if bar.value() != bar.maximum() else bar.minimum())
    assert bar.opacity == 1.0
    assert timer.isActive()
    timer.stop()
    timer.timeout.emit()
    bar._fade.setCurrentTime(bar._fade.duration() // 2)
    assert 0.0 < bar.opacity < 1.0
    bar._fade.setCurrentTime(bar._fade.duration())
    assert bar.opacity == 0.0
    window.find_bar.open()
    window.find_bar.field.setText("percent")
    assert bar.width() == 12 and window.editor.find_matches()  # marks stay on the bar
    window.find_bar.close_bar()


def test_every_shortcut_belongs_to_one_action(window) -> None:
    seen: dict[str, str] = {}
    for menu in window.menuBar().findChildren(QMenu):
        for action in menu.actions():
            for key in action.shortcuts():
                text = key.toString(QKeySequence.SequenceFormat.PortableText)
                assert seen.setdefault(text, action.text()) == action.text(), text
    by_name = {a.text(): a for m in window.menuBar().findChildren(QMenu) for a in m.actions()}
    assert by_name["Settings…"].shortcut() == QKeySequence("Ctrl+,")  # shown in the menu
    assert by_name["Keyboard Shortcuts"].shortcut() == QKeySequence(
        "Ctrl+Shift+K" if sys.platform == "darwin" else "Shift+F1"
    )


def test_ctrl_shift_backspace_deletes_to_the_line_start(window, app) -> None:
    keys = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    window.new_sheet("")
    ed = window.editor
    ed.setPlainText("rent = $900\nfood is $300 a month")
    cur = ed.textCursor()
    cur.setPosition(len("rent = $900\nfood is $300"))
    ed.setTextCursor(cur)
    QTest.keyClick(ed, Qt.Key.Key_Backspace, keys)
    assert ed.toPlainText() == "rent = $900\n a month"
    QTest.keyClick(ed, Qt.Key.Key_Delete, keys)
    assert ed.toPlainText() == "rent = $900\n"
    QTest.keyClick(ed, Qt.Key.Key_Backspace, keys)  # at the start: joins the line above
    assert ed.toPlainText() == "rent = $900"
    ed.undo()
    ed.undo()
    assert ed.toPlainText() == "rent = $900\n a month"  # one undo step each
    ed.moveCursor(QTextCursor.MoveOperation.End)


def test_ctrl_t_and_ctrl_l_type_total_and_references(window, app) -> None:
    acts = {
        a.shortcut().toString(): a
        for m in window.menuBar().findChildren(QMenu)
        for a in m.actions()
    }
    window.new_sheet("")
    ed = window.editor
    ed.setPlainText("$1000\n$200\nmonthly =")
    ed.moveCursor(ed.textCursor().MoveOperation.End)
    acts["Ctrl+T"].trigger()
    assert ed.toPlainText().endswith("\nmonthly = total")
    QTest.keyClick(ed, Qt.Key.Key_Return)
    QTest.keyClicks(ed, "2 *")
    acts["Ctrl+L"].trigger()  # nothing typed: the answer above
    QTest.keyClicks(ed, " + 1")
    acts["Ctrl+L"].trigger()  # a number just typed: that line
    assert ed.toPlainText().endswith("\n2 * prev + line1")
    pump(app)
    assert [ed.result_text(n) for n in (2, 3)] == ["$1,200.00", "$3,400.00"]
    ed.undo()
    assert ed.toPlainText().endswith("\n2 * prev + 1")  # one undo step


def test_insert_words_follow_the_interface_language(window, app) -> None:
    window.set_language("uk")
    window.new_sheet("")
    ed = window.editor
    ed.setPlainText("5\n")
    ed.moveCursor(ed.textCursor().MoveOperation.End)
    ed.insert_total()
    ed.insert_line_reference()
    assert ed.toPlainText() == "5\nразом попередній"


def test_double_click_an_answer_inserts_a_reference(window, app) -> None:
    window.new_sheet("")
    ed = window.editor
    ed.setPlainText("$1000\n$200\nx = ")
    ed.moveCursor(ed.textCursor().MoveOperation.End)
    pump(app)

    def answer(n: int) -> QPoint:
        geo = ed.blockBoundingGeometry(ed.document().findBlockByNumber(n))
        y = int(geo.translated(ed.contentOffset()).center().y())
        return QPoint(ed.results.width() // 2, y)

    QTest.mouseDClick(ed.results, Qt.MouseButton.LeftButton, pos=answer(1))
    assert ed.toPlainText().endswith("\nx = line2")
    pump(app)
    assert ed.result_text(2) == "$200.00"
    QTest.mouseDClick(ed.results, Qt.MouseButton.LeftButton, pos=answer(2))  # its own line
    assert ed.toPlainText().endswith("\nx = line2")


def test_hovering_a_variable_shows_its_value(window, app) -> None:
    window.new_sheet("")
    ed = window.editor
    ed.setPlainText("rent = $900\nrent * 12")
    pump(app)
    block = ed.document().findBlockByNumber(1)
    cur = ed.textCursor()
    cur.setPosition(block.position() + 2)
    over = ed.cursorRect(cur).center()
    assert ed.hint_at(over) == "$900.00"
    cur.setPosition(block.position() + len("rent * 1"))
    assert ed.hint_at(ed.cursorRect(cur).center()) == ""  # over the number
    assert ed.hint_at(over + type(over)(400, 0)) == ""  # past the end of the line


def test_help_sheet_ignores_the_insert_keys(window, app) -> None:
    window.open_help()
    ed = window.editor
    before = ed.toPlainText()
    ed.insert_total()
    ed.insert_line_reference()
    assert not ed.insert_reference(0)
    assert ed.toPlainText() == before


class FakeSpell(SpellChecker):
    """Knows a few typos; no Hunspell needed."""

    TYPOS = {"teh": ["the", "tech"], "rnet": ["rent"], "оредна": ["оренда"]}

    def _check(self, word: str) -> bool:
        if word in self.own or word in self.ignored:
            return True
        return word.lower() not in self.TYPOS

    def suggest(self, word: str, limit: int = 5) -> list[str]:
        return self.TYPOS.get(word.lower(), [])[:limit]


def underlined(editor, line: int) -> list[str]:
    block = editor.document().findBlockByNumber(line)
    return [
        block.text()[r.start : r.start + r.length]
        for r in block.layout().formats()
        if r.format.underlineStyle() == QTextCharFormat.UnderlineStyle.SpellCheckUnderline
    ]


def spell_window(window, app, text: str, tmp_path: Path) -> FakeSpell:
    window.new_sheet("")
    spell = FakeSpell(tmp_path / "words.txt")
    window.editor.set_spell_checker(spell)
    window.editor.setPlainText(text)
    window.editor.moveCursor(QTextCursor.MoveOperation.Start)
    pump(app)
    return spell


def test_spelling_underlines_prose_only(window, app, tmp_path: Path) -> None:
    text = "teh = 5\nrnet: teh + 2 // оредна\n# teh plan\nteh"
    spell_window(window, app, text, tmp_path)
    ed = window.editor
    assert underlined(ed, 0) == []  # a variable name is the user's to choose
    assert underlined(ed, 1) == ["rnet", "оредна"]  # label and comment; teh is the variable
    assert underlined(ed, 2) == ["teh"]  # heading
    ed.set_spell_checker(None)
    assert all(underlined(ed, n) == [] for n in range(4))


@pytest.mark.parametrize("palette", ["glacier", "ember"])
@pytest.mark.parametrize("mode", ["light", "dark"])
def test_diagnostic_underlines_show_yellow_for_spelling_and_red_for_format(
    window, app, tmp_path, palette, mode
):
    window.set_colours(palette)
    window.set_theme(mode)
    text = "🧾 teh $1..23"
    spell_window(window, app, text, tmp_path)
    ed = window.editor
    ranges = {
        r.format.underlineStyle(): (r.start, r.length, r.format.underlineColor().name())
        for r in ed.document().firstBlock().layout().formats()
        if r.format.underlineStyle() != QTextCharFormat.UnderlineStyle.NoUnderline
    }
    spelling_style = QTextCharFormat.UnderlineStyle.SpellCheckUnderline
    format_style = QTextCharFormat.UnderlineStyle.WaveUnderline
    assert ranges == {
        spelling_style: (3, 3, window.theme.misspelled),
        format_style: (8, 5, window.theme.invalid_number),
    }
    spelling_hue = QColor(ranges[spelling_style][2]).hue()
    format_hue = QColor(ranges[format_style][2]).hue()
    assert 40 <= spelling_hue <= 65
    assert format_hue >= 330 or 0 <= format_hue <= 15
    assert ed.result_text(0) == ""
    assert "1,234.56" in ed.hint_at(line_pos(ed, 0, 10))
    assert ed.hint_at(line_pos(ed, 0, 4)) == ""


def test_unsupported_date_has_a_format_wave_and_iso_hint(window, app):
    ed = window.editor
    ed.setPlainText("18/11/2026")
    ed.recalculate()
    pump(app)
    formats = ed.document().firstBlock().layout().formats()
    assert any(
        r.format.underlineStyle() == QTextCharFormat.UnderlineStyle.WaveUnderline
        and r.format.underlineColor().name() == window.theme.invalid_number
        for r in formats
    )
    assert "2026-11-18" in ed.hint_at(line_pos(ed, 0, 3))


def test_invalid_iso_date_shows_the_reason(window, app):
    ed = window.editor
    ed.setPlainText("salary = 2026-19-11")
    ed.recalculate()
    pump(app)
    formats = ed.document().firstBlock().layout().formats()
    assert any(
        r.format.underlineStyle() == QTextCharFormat.UnderlineStyle.WaveUnderline
        and r.format.underlineColor().name() == window.theme.invalid_number
        for r in formats
    )
    assert "date" in ed.hint_at(line_pos(ed, 0, 12)).lower()


def test_result_warnings_show_on_hover_and_stay_out_of_copied_answers(window, app) -> None:
    window.set_language("uk")
    ed = window.editor
    ed.setPlainText("10 / 0\n// 10 / 0\ngo to the shop\n1e+\n1 +\nline99\n24:60")
    ed.recalculate()
    pump(app)

    def hover(row):
        y = line_pos(ed, row, 0).y()
        QTest.mouseMove(ed.results, QPoint(ed.results.width() - 12, y))
        return ed.results.toolTip()

    assert hover(0) == "Ділення на нуль."
    assert hover(5) == "Такого рядка не існує."
    assert hover(6) == ed.hint_at(line_pos(ed, 6, 2)) == "Такого часу не існує."
    assert all(hover(row) == "" for row in range(1, 5))
    assert ed.result_text(0) == ""
    assert ed.text_with_results() == ed.toPlainText()


def test_spelling_waits_until_the_word_is_typed(window, app, tmp_path: Path) -> None:
    spell_window(window, app, "", tmp_path)
    ed = window.editor
    QTest.keyClicks(ed, "rent teh")
    pump(app)
    assert underlined(ed, 0) == []  # the cursor is still on it
    QTest.keyClicks(ed, " ")
    pump(app)
    assert underlined(ed, 0) == ["teh"]


def test_spelling_menu_replaces_adds_and_ignores(window, app, tmp_path: Path) -> None:
    spell = spell_window(window, app, "pay teh rnet // оредна", tmp_path)
    ed = window.editor
    ed.moveCursor(QTextCursor.MoveOperation.End)
    pump(app)

    def menu_at(word: str) -> list:
        block = ed.document().firstBlock()
        cur = QTextCursor(block)
        cur.setPosition(block.text().index(word) + 1)
        found = ed.misspelled_at(ed.cursorRect(cur).center())
        assert found is not None and found.selectedText() == word
        return ed.spelling_actions(found, ed)

    actions = menu_at("teh")
    assert [a.text() for a in actions] == ["the", "tech", "Add to Dictionary", "Ignore"]
    actions[0].trigger()
    assert ed.toPlainText() == "pay the rnet // оредна"

    menu_at("rnet")[-2].trigger()  # Add to Dictionary
    assert (tmp_path / "words.txt").read_text(encoding="utf-8") == "rnet\n"
    menu_at("оредна")[-1].trigger()  # Ignore
    assert "оредна" in spell.ignored
    pump(app)
    assert underlined(ed, 0) == []
    ed.undo()
    assert ed.toPlainText() == "pay teh rnet // оредна"


def test_spelling_menu_without_suggestions(window, app, tmp_path: Path) -> None:
    spell_window(window, app, "", tmp_path)
    cur = QTextCursor(window.editor.document())
    cur.insertText("zzz")
    cur.select(QTextCursor.SelectionType.WordUnderCursor)
    actions = window.editor.spelling_actions(cur, window.editor)
    assert [a.text() for a in actions] == ["No suggestions", "Add to Dictionary", "Ignore"]
    assert not actions[0].isEnabled()


def test_no_spelling_in_read_only_sheets(window, app, tmp_path: Path) -> None:
    spell_window(window, app, "teh rnet", tmp_path)
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    QTest.keyClicks(window.editor, " ")
    pump(app)
    assert underlined(window.editor, 0) == ["teh", "rnet"]
    window.editor.setReadOnly(True)
    assert underlined(window.editor, 0) == []
    window.editor.setReadOnly(False)
    assert underlined(window.editor, 0) == ["teh", "rnet"]


def pretend_os(monkeypatch: pytest.MonkeyPatch, key: str) -> None:
    """Make spell check act as on `key` ("linux", "darwin", ...), whatever OS runs the tests."""
    monkeypatch.setattr(spelling, "platform_key", lambda: key)
    monkeypatch.setattr(settings_dialog, "platform_key", lambda: key)


def test_spelling_toggle_and_settings(window, app, monkeypatch: pytest.MonkeyPatch) -> None:
    pretend_os(monkeypatch, "linux")
    status = Status(library=True, dictionaries={"en": "/x/en_US"})
    window.spell_status = status
    window._spell = FakeSpell()
    window.build_menus()
    view = window.menuBar().actions()[2].menu()
    act = next(a for a in view.actions() if a.text() == "Check Spelling")
    assert act.isEnabled() and not act.isChecked()
    assert act.shortcut() == QKeySequence("Ctrl+Alt+S" if sys.platform == "darwin" else "F7")

    window._toggle_spelling()
    assert window.settings.spell_check and window.editor.spell is window._spell
    assert Settings.load().spell_check
    dlg = SettingsDialog(window.settings, window.t, window)
    assert dlg.spell_check.isEnabled() and dlg.spell_check.isChecked()
    assert dlg.spell_hint.text() == "English, with the system's Hunspell dictionaries. " + (
        "No dictionary for Ukrainian. To add it: sudo apt install hunspell-uk"
    )
    dlg.spell_check.setChecked(False)
    assert not dlg.result_settings().spell_check
    window._toggle_spelling()
    assert window.editor.spell is None


@pytest.mark.parametrize(
    ("status", "hint"),
    [
        pytest.param(
            Status(library=False),
            "sudo apt install libhunspell-1.7-0",
            id="no hunspell",
        ),
        pytest.param(
            Status(library=True),
            "sudo apt install hunspell-en-us hunspell-uk",
            id="no dictionaries",
        ),
    ],
)
def test_spelling_greyed_out_without_hunspell(
    window, monkeypatch: pytest.MonkeyPatch, status: Status, hint: str
) -> None:
    pretend_os(monkeypatch, "linux")
    window.spell_status = status
    window.settings.spell_check = True
    window.build_menus()
    window.apply_settings()
    view = window.menuBar().actions()[2].menu()
    act = next(a for a in view.actions() if a.text() == "Check Spelling")
    assert not act.isEnabled() and not act.isChecked()
    assert window.editor.spell is None
    dlg = SettingsDialog(window.settings, window.t, window)
    assert not dlg.spell_check.isEnabled()
    assert hint in dlg.spell_hint.text()
    assert dlg.result_settings().spell_check  # kept for when Hunspell turns up


MAC_DICTS = (
    "To add one, put the .aff and .dic files in ~/Library/Spelling. The README has the steps."
)


@pytest.mark.parametrize(
    ("os_key", "status", "hint"),
    [
        pytest.param(
            "linux",
            Status(library=False),
            "Needs Hunspell. To install it: "
            "sudo apt install libhunspell-1.7-0 hunspell-en-us hunspell-uk",
            id="linux no hunspell",
        ),
        pytest.param(
            "linux",
            Status(library=True),
            "No dictionary for English, Ukrainian. "
            "To add it: sudo apt install hunspell-en-us hunspell-uk",
            id="linux no dictionaries",
        ),
        pytest.param(
            "darwin",
            Status(library=False),
            "Needs Hunspell: run brew install hunspell, then put the .aff and .dic "
            "dictionary files in ~/Library/Spelling. The README has the steps.",
            id="macos no hunspell",
        ),
        pytest.param(
            "darwin",
            Status(library=True),
            f"No dictionary for English, Ukrainian. {MAC_DICTS}",
            id="macos no dictionaries",
        ),
        pytest.param(
            "darwin",
            Status(library=True, dictionaries={"en": "/x/en_US"}),
            "English, with the system's Hunspell dictionaries. "
            f"No dictionary for Ukrainian. {MAC_DICTS}",
            id="macos no ukrainian",
        ),
        pytest.param(
            "win32",
            Status(library=False),
            "This Windows has no spell checker.",
            id="windows no spell checker",
        ),
        pytest.param(
            "win32",
            Status(library=True, dictionaries={"en": "en-US"}),
            "English, with the Windows spell checker. No dictionary for Ukrainian. Add the "
            "language in Windows Settings, under Time & language > Language & region.",
            id="windows no ukrainian",
        ),
        pytest.param(
            "win32",
            Status(library=True, dictionaries={"en": "en-US", "uk": "uk-UA"}),
            "English, Ukrainian, with the Windows spell checker.",
            id="windows",
        ),
    ],
)
def test_spell_hint(
    monkeypatch: pytest.MonkeyPatch, os_key: str, status: Status, hint: str
) -> None:
    pretend_os(monkeypatch, os_key)
    assert settings_dialog.spell_hint(status, partial(tr, "en")) == hint


# Look for dictionaries before the tests move HOME. On macOS they're in ~/Library/Spelling.
SYSTEM_SPELLING = probe()


@pytest.mark.skipif(not SYSTEM_SPELLING.available, reason="needs the system's Hunspell")
def test_spelling_loads_real_dictionaries_in_background(
    window, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    # the window looks in the test's HOME, so point it at the dictionaries found above
    directories = {str(Path(base).parent) for base in SYSTEM_SPELLING.dictionaries.values()}
    monkeypatch.setenv("DICPATH", os.pathsep.join(sorted(directories)))
    window.spell_status = probe()
    window.new_sheet("")
    window.editor.setPlainText("Taxi to airprot\n")
    window._toggle_spelling()
    deadline = time.monotonic() + 10
    while window.editor.spell is None and time.monotonic() < deadline:
        app.processEvents()
        time.sleep(0.01)
    assert window.editor.spell is not None
    pump(app)
    assert underlined(window.editor, 0) == ["airprot"]


def menu_rows(menu: QMenu) -> list[str]:
    """The menu as text: each item's name without its shortcut, "---" for a line."""
    return ["---" if a.isSeparator() else a.text().split("\t")[0] for a in menu.actions()]


def line_pos(editor, line: int, column: int = 0) -> QPoint:
    block = editor.document().findBlockByNumber(line)
    cur = QTextCursor(block)
    cur.setPosition(block.position() + column)
    return editor.cursorRect(cur).center()


def test_right_click_menu_copies_the_edit_menu(window, app) -> None:
    window.new_sheet("")
    ed = window.editor
    QTest.keyClicks(ed, "a = 5")
    QTest.keyClick(ed, Qt.Key.Key_Return)
    QTest.keyClicks(ed, "a * 2")
    QGuiApplication.clipboard().setText("7")
    pump(app)
    menu = ed.context_menu(line_pos(ed, 1))
    assert menu_rows(menu) == [
        "Undo", "Redo", "---",
        "Cut", "Copy", "Paste", "Select All", "---",
        "Comment Line", "Copy Line Result", "Insert Line Reference",
    ]  # fmt: skip
    edit_menu = window.menuBar().actions()[1].menu()
    keys = {
        a.text(): a.shortcut().toString(QKeySequence.SequenceFormat.NativeText)
        for a in edit_menu.actions()
    }
    for act in menu.actions():
        if act.isSeparator():
            continue
        name, _, shortcut = act.text().partition("\t")
        assert shortcut == keys[name], name  # the same keys as the Edit menu
        assert not act.icon().isNull(), name
    enabled = {a.text().split("\t")[0]: a.isEnabled() for a in menu.actions()}
    assert enabled["Undo"] and not enabled["Redo"]
    assert not enabled["Cut"] and not enabled["Copy"]  # nothing selected
    assert enabled["Paste"] and enabled["Copy Line Result"]

    next(a for a in menu.actions() if a.text().startswith("Comment Line")).trigger()
    assert ed.toPlainText() == "a = 5\n// a * 2"


def test_right_click_menu_follows_the_language(window) -> None:
    window.set_language("uk")
    rows = menu_rows(window.editor.context_menu(QPoint(5, 5)))
    window.set_language("en")
    assert rows[0] == "Скасувати" and "Закоментувати рядок" in rows


def test_right_click_menu_in_read_only_sheets(window, app) -> None:
    window.open_help()
    pump(app)
    ed = window.editor
    assert ed.isReadOnly()
    ed.moveCursor(QTextCursor.MoveOperation.Start)
    assert menu_rows(ed.context_menu(line_pos(ed, 0))) == [
        "Copy", "Select All", "---", "Copy Line Result",
    ]  # fmt: skip


def test_right_click_menu_puts_spelling_first(window, app, tmp_path: Path) -> None:
    spell_window(window, app, "pay teh rent", tmp_path)
    ed = window.editor
    ed.moveCursor(QTextCursor.MoveOperation.End)
    pump(app)
    menu = ed.context_menu(line_pos(ed, 0, 5))
    rows = menu_rows(menu)
    assert rows[:5] == ["the", "tech", "---", "Add to Dictionary", "Ignore"]
    assert rows[5:7] == ["---", "Undo"]
    assert not menu.actions()[3].icon().isNull() and not menu.actions()[4].icon().isNull()
    assert menu_rows(ed.context_menu(line_pos(ed, 0, 9)))[0] == "Undo"  # "rent" is fine


def test_right_click_menus_show_icons_on_macos(window, app, tmp_path: Path) -> None:
    # Qt hides every menu icon on macOS by default. Do the same here.
    app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, True)
    try:
        icons_shown: list[list[bool]] = []  # for each menu, whether each icon shows

        def look_and_close() -> None:
            # No assert here. Qt only prints a failure inside a timer, and the menu would stay open.
            menu = QApplication.activePopupWidget()
            if isinstance(menu, QMenu):
                icons_shown.append(
                    [a.isIconVisibleInMenu() for a in menu.actions() if not a.icon().isNull()]
                )
            if menu is not None:
                menu.close()

        spell_window(window, app, "pay teh rent", tmp_path)
        ed = window.editor
        QTimer.singleShot(0, look_and_close)
        ed.show_menu(ed.context_menu(line_pos(ed, 0, 5)), QPoint())  # on a misspelled word
        QTimer.singleShot(0, look_and_close)
        window.sidebar._menu(QPoint(5, 5))
        assert len(icons_shown) == 2
        assert all(icons and all(icons) for icons in icons_shown)
        assert not window._actions["new_sheet"].isIconVisibleInMenu()  # the menu bar still has none
    finally:
        app.setAttribute(Qt.ApplicationAttribute.AA_DontShowIconsInMenus, False)


def test_right_click_moves_the_cursor_unless_on_the_selection(
    window, app, monkeypatch: pytest.MonkeyPatch
) -> None:
    shown = []
    window.new_sheet("")
    ed = window.editor
    # Qt's own exec would wait for a click
    monkeypatch.setattr(ed, "show_menu", lambda menu, where: shown.append(menu_rows(menu)))
    ed.setPlainText("first line\nsecond line\nthird line")
    pump(app)

    def right_click(line: int, column: int) -> None:
        pos = line_pos(ed, line, column)
        event = QContextMenuEvent(
            QContextMenuEvent.Reason.Mouse, pos, ed.viewport().mapToGlobal(pos)
        )
        QApplication.sendEvent(ed.viewport(), event)

    ed.moveCursor(QTextCursor.MoveOperation.Start)
    right_click(2, 3)
    assert ed.textCursor().blockNumber() == 2  # Comment Line now acts on the clicked line
    assert shown and shown[-1][0] == "Undo"

    cur = ed.textCursor()
    cur.setPosition(0)
    cur.setPosition(5, QTextCursor.MoveMode.KeepAnchor)  # "first"
    ed.setTextCursor(cur)
    right_click(0, 2)
    assert ed.textCursor().selectedText() == "first"  # Cut and Copy keep the selection

    origin = QPoint(0, 0)
    event = QContextMenuEvent(QContextMenuEvent.Reason.Keyboard, origin, origin)
    QApplication.sendEvent(ed.viewport(), event)  # the Menu key: stays where it is
    assert ed.textCursor().selectedText() == "first"
    assert len(shown) == 3


def test_menu_stays_whole_on_screen() -> None:
    """The numbers from a 1603x868 laptop screen where Qt put the menu at the very top."""
    screen = QRect(0, 0, 1603, 868)
    menu = QSize(281, 502)
    assert fit_menu(QPoint(495, 100), menu, screen) == QPoint(495, 100)  # fits below
    assert fit_menu(QPoint(495, 800), menu, screen) == QPoint(495, 298)  # fits above
    assert fit_menu(QPoint(495, 417), menu, screen) == QPoint(495, 366)  # neither: low
    assert fit_menu(QPoint(5, 50), QSize(100, 2000), screen) == QPoint(5, 0)  # too tall


TOP = Qt.WindowType.WindowStaysOnTopHint


def test_always_on_top_off_by_default(window) -> None:
    action = window._actions["always_on_top"]
    assert action.isCheckable()
    assert not action.isChecked()
    assert not window.settings.always_on_top
    assert not window.windowFlags() & TOP
    assert action.icon().pixmap(20).toImage() == icons.icon("unpin").pixmap(20).toImage()


def test_always_on_top_menu_toggles_without_losing_placement_or_edits(
    window, app, monkeypatch
) -> None:
    window.setGeometry(70, 80, 700, 500)
    window.editor.setPlainText("2 + 2")
    window.editor.moveCursor(QTextCursor.MoveOperation.End)
    window.editor.insertPlainText(" + 1")
    window.activateWindow()
    window.editor.setFocus()
    pump(app)
    geometry = window.geometry()
    document = window.editor.document()
    cursor = window.editor.textCursor().position()
    activation_requests = []
    activate = window.activateWindow

    def request_activation() -> None:
        activation_requests.append(True)
        activate()

    monkeypatch.setattr(window, "activateWindow", request_activation)

    for enabled in (True, False):
        was_active = window.isActiveWindow()
        requests_before = len(activation_requests)
        window._actions["always_on_top"].trigger()
        pump(app)
        assert bool(window.windowFlags() & TOP) is enabled
        assert bool(window.windowHandle().flags() & TOP) is enabled
        assert window.settings.always_on_top is enabled
        assert window._actions["always_on_top"].isChecked() is enabled
        expected_icon = icons.icon("pin" if enabled else "unpin").pixmap(20).toImage()
        assert window._actions["always_on_top"].icon().pixmap(20).toImage() == expected_icon
        assert Settings.load().always_on_top is enabled
        assert window.isVisible()
        assert window.geometry() == geometry
        assert window.editor.document() is document
        assert window.editor.toPlainText() == "2 + 2 + 1"
        assert window.editor.textCursor().position() == cursor
        # Offscreen activation is unreliable after flag changes; check the request
        # and remembered focus here, and keyboard focus on a real desktop.
        assert window.focusWidget() is window.editor
        assert len(activation_requests) - requests_before == int(was_active)

    window.editor.undo()
    assert window.editor.toPlainText() == "2 + 2"


@pytest.mark.parametrize("enabled", [True, False])
def test_always_on_top_saved_choice_applies_before_first_show(
    window_settings, open_window, app, enabled
) -> None:
    window_settings.setValue("always_on_top", enabled)
    restored = open_window(show=False)
    assert not restored.isVisible()
    assert restored.settings.always_on_top is enabled
    assert bool(restored.windowFlags() & TOP) is enabled
    assert restored._actions["always_on_top"].isChecked() is enabled
    expected_icon = icons.icon("pin" if enabled else "unpin").pixmap(20).toImage()
    assert restored._actions["always_on_top"].icon().pixmap(20).toImage() == expected_icon
    restored.show()
    pump(app)
    assert restored.isVisible()
    assert bool(restored.windowFlags() & TOP) is enabled


@pytest.mark.parametrize("state", ["maximized", "fullscreen", "minimized"])
def test_always_on_top_toggle_keeps_window_state_and_normal_size(window, app, state) -> None:
    window.resize(650, 450)
    pump(app)
    normal = window.geometry()
    if state == "maximized":
        window.showMaximized()
    elif state == "fullscreen":
        window.showFullScreen()
    else:
        window.showMinimized()
    pump(app)
    before = window.windowState()
    for _ in range(2):
        window._actions["always_on_top"].trigger()
        pump(app)
        assert window.isVisible()
        assert window.windowState() == before
    window.showNormal()
    pump(app)
    assert window.geometry() == normal


def test_always_on_top_toggle_does_not_show_a_hidden_window(window, app) -> None:
    window.hide()
    window._actions["always_on_top"].trigger()
    pump(app)
    assert not window.isVisible()
    assert window.windowFlags() & TOP


def test_always_on_top_toggle_requests_no_activation_for_an_inactive_window(
    window, app, monkeypatch
) -> None:
    other = QWidget()
    try:
        other.show()
        other.activateWindow()
        pump(app)
        assert other.isActiveWindow()
        activation_requests = []
        show_attributes = []
        show = window.show
        attribute = Qt.WidgetAttribute.WA_ShowWithoutActivating

        def show_window() -> None:
            show_attributes.append(window.testAttribute(attribute))
            show()

        monkeypatch.setattr(window, "show", show_window)
        monkeypatch.setattr(window, "activateWindow", lambda: activation_requests.append(True))
        window._actions["always_on_top"].trigger()
        pump(app)
        assert show_attributes == [True]
        assert activation_requests == []
        assert not window.testAttribute(attribute)
    finally:
        other.close()
        other.deleteLater()


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_always_on_top_rebuilt_menus_and_settings_keep_choice(window, app, theme) -> None:
    window._actions["always_on_top"].trigger()
    window.set_theme(theme)
    window.set_language("uk")
    pump(app)
    assert window._actions["always_on_top"].isChecked()
    assert window._actions["always_on_top"].text() == "Завжди поверх інших вікон"
    expected_icon = icons.icon("pin").pixmap(20).toImage()
    assert window._actions["always_on_top"].icon().pixmap(20).toImage() == expected_icon
    assert window.windowFlags() & TOP
    dialog = SettingsDialog(window.settings, window.t, window)
    try:
        assert dialog.result_settings().always_on_top
    finally:
        dialog.deleteLater()
    window._actions["always_on_top"].trigger()
    window.set_language("en")
    assert not window._actions["always_on_top"].isChecked()
    assert window._actions["always_on_top"].text() == "Always on Top"
    expected_icon = icons.icon("unpin").pixmap(20).toImage()
    assert window._actions["always_on_top"].icon().pixmap(20).toImage() == expected_icon
    assert not window.windowFlags() & TOP


@pytest.mark.parametrize("repeats", [1, 3])
def test_total_stays_in_the_middle_of_the_window(window, app, repeats: int) -> None:
    window.new_sheet("")
    window.editor.setPlainText("rent = $900\nfood = $300")
    window.editor.recalculate()
    assert window.total_label.text()
    assert abs(off_centre(window.total_label, app)) <= 2
    window.rates_label.setText("Rates from a very long time ago, click to refresh " * repeats)
    assert abs(off_centre(window.total_label, app)) <= 2
    window.resize(window.width() + 150, window.height())
    assert abs(off_centre(window.total_label, app)) <= 2


def test_total_tooltip_follows_the_ui_language(window) -> None:
    for lang in ("en", "uk", "en"):
        window.set_language(lang)
        tip = window.total_label.toolTip()
        assert tip == tr(lang, "total_tip")
        assert tip and tip != "total_tip"


def test_a_message_takes_the_place_of_the_total(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("$10\n$20\ntotal")
    window.editor.recalculate()
    assert window.total_label.text() == "Total: $60.00"
    window._copy_total()
    message = window.message_label
    assert message.text() == "Copied $60.00"
    assert QGuiApplication.clipboard().text() == "$60.00"
    assert message.isVisible() and not window.total_label.isVisible()
    assert abs(off_centre(message, app)) <= 2
    assert window.rates_label.isVisible()
    window._message_timer.timeout.emit()  # its time is up
    assert window.total_label.isVisible() and not message.isVisible()


NoError = QNetworkReply.NetworkError.NoError


class FakeReply:
    def __init__(self, error: QNetworkReply.NetworkError, body: bytes = b"") -> None:
        self._error, self._body = error, body

    def error(self) -> QNetworkReply.NetworkError:
        return self._error

    def read(self, _max: int) -> QByteArray:
        return QByteArray(self._body)

    def deleteLater(self) -> None:  # noqa: N802
        pass


@pytest.fixture
def about(window, app, monkeypatch: pytest.MonkeyPatch):
    """Help → About, opened from the menu, with the check to GitHub held back."""
    opened = []
    monkeypatch.setattr(AboutDialog, "check", lambda self: None)
    monkeypatch.setattr(AboutDialog, "exec", lambda self: opened.append(self) or 0)
    window.about()
    dlg = opened[0]
    dlg.show()
    pump(app)
    yield dlg
    dlg.close()


def test_about_spins_while_it_checks(about, window) -> None:
    assert about.spinner.isVisible()
    assert about.spinner._timer.isActive()
    assert about.status.text() == window.t("update_checking")


def test_about_links_to_a_newer_release(about) -> None:
    about.finished_check(FakeReply(NoError, b'{"tag_name": "v99.0.0"}'))
    assert not about.spinner.isVisible()
    assert not about.spinner._timer.isActive()
    assert "href='https://github.com/sprytnyk/calculon/releases/tag/v99.0.0'" in (
        about.status.text()
    )
    assert about.status.openExternalLinks()


def test_about_says_up_to_date_in_the_accent(about, window) -> None:
    about.finished_check(FakeReply(NoError, b'{"tag_name": "v0.0.0"}'))
    assert about.status.text() == window.t("update_none")
    assert window.theme.accent in about.status.styleSheet()


def test_about_says_when_the_check_failed(about, window) -> None:
    about.finished_check(FakeReply(QNetworkReply.NetworkError.HostNotFoundError))
    assert not about.spinner.isVisible()
    assert about.status.text() == window.t("update_failed")
    assert about.status.styleSheet() == ""
