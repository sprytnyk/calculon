"""UI smoke tests: the real window, offscreen, with every user folder in a temp dir."""

import os
import subprocess
import sys
import time
from functools import partial
from pathlib import Path
from types import SimpleNamespace

import pytest
import shiboken6
from PySide6.QtCore import QByteArray, QPoint, QRect, QSettings, QSize, Qt
from PySide6.QtGui import (
    QColor,
    QContextMenuEvent,
    QFont,
    QGuiApplication,
    QKeySequence,
    QPalette,
    QTextCharFormat,
    QTextCursor,
)
from PySide6.QtNetwork import QNetworkReply
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialogButtonBox, QMenu, QStyle, QWidget

from calculon import rates, settings, spelling
from calculon.settings import Settings
from calculon.spelling import SpellChecker, Status, probe
from calculon.storage import SheetStore
from calculon.translations import tr
from calculon.ui import folder_dialog, icons, settings_dialog
from calculon.ui import theme as themes
from calculon.ui.about_dialog import AboutDialog
from calculon.ui.editor import KIND_ROLE, SheetScrollBar, fit_menu
from calculon.ui.main_window import MainWindow
from calculon.ui.settings_dialog import SettingsDialog
from calculon.ui.shortcuts_dialog import ShortcutsDialog, key_text
from calculon.ui.sidebar import Sidebar
from calculon.ui.theme import GLACIER_DARK, GLACIER_LIGHT


def pump(app) -> None:
    for _ in range(5):
        app.processEvents()


def off_centre(label, app) -> int:
    """How far the middle of a status bar label is from the middle of the window, in
    pixels. A pixel or two off is fine: QStatusBar keeps 2 px of margin on its left only."""
    pump(app)
    window = label.window()
    return label.mapTo(window, label.rect().center()).x() - window.rect().center().x()


def test_first_start_creates_welcome_sheet(window, app) -> None:
    assert window.store.all_sheets() == ["Welcome.txt"]
    assert window.current == ("sheet", "Welcome.txt")
    pump(app)
    texts = [line.text for line in window.editor.result.lines]
    assert "$64.00" in texts  # 20% off $80


def drive_folder_dialog(monkeypatch, *folders: str) -> list[folder_dialog.FolderDialog]:
    """Stand in for the user: type each folder in turn and press "Use this folder".
    With no folders, press Quit. Returns the dialogs that opened."""
    opened = []

    def run(dialog) -> int:
        opened.append(dialog)
        for folder in folders:
            dialog.folder.setText(folder)
            dialog.try_folder()
            if dialog.result() == folder_dialog.QDialog.DialogCode.Accepted:
                break
        return dialog.result()

    monkeypatch.setattr(folder_dialog.FolderDialog, "exec", run)
    return opened


def test_first_start_asks_for_sheets_folder(app, home, tmp_path, monkeypatch) -> None:
    qs = QSettings()
    qs.clear()
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("")
    chosen = tmp_path / "My sheets"
    opened = drive_folder_dialog(monkeypatch, str(blocker / "Calculon"), str(chosen))
    try:
        assert folder_dialog.choose_sheets_folder() is not None
        dialog = opened[0]
        assert dialog.error.text().startswith(f"Calculon can't create or write to {blocker}")
        assert Settings.load().sheets_dir == str(chosen)
        assert chosen.is_dir()
    finally:
        qs.clear()


def test_first_start_suggests_documents(app, home, monkeypatch) -> None:
    QSettings().clear()
    opened = drive_folder_dialog(monkeypatch)
    assert folder_dialog.choose_sheets_folder() is None
    assert opened[0].folder.text() == settings.default_sheets_dir()
    assert opened[0].error.isHidden()
    assert Settings.load().sheets_dir == ""


def test_chosen_folder_reaches_the_window_when_settings_cannot_be_saved(
    app, home, tmp_path, monkeypatch
) -> None:
    """In a home folder Calculon can't write to, QSettings drops the save without an
    error. So the window must get the folder from the dialog, not from the settings file."""
    QSettings().clear()
    monkeypatch.setattr(Settings, "save", lambda self: None)
    monkeypatch.setattr(rates.RatesService, "refresh", lambda self: None)
    chosen = tmp_path / "My sheets"
    drive_folder_dialog(monkeypatch, str(chosen))
    w = MainWindow(folder_dialog.choose_sheets_folder())
    try:
        assert w.store.root == chosen
    finally:
        w.close()
        w.deleteLater()


def test_saved_sheets_folder_opens_without_asking(app, tmp_path, monkeypatch) -> None:
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(tmp_path / "sheets"))
    opened = drive_folder_dialog(monkeypatch)
    try:
        assert folder_dialog.choose_sheets_folder() is not None
        assert opened == []
    finally:
        qs.clear()


def test_blocked_saved_folder_asks_again_and_explains(app, tmp_path, monkeypatch) -> None:
    """Windows' Controlled folder access can block Documents. Say why and ask again,
    with the saved folder in the box so a retry is one click."""
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("")
    blocked = blocker / "Calculon"
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(blocked))
    monkeypatch.setattr(folder_dialog, "sys", SimpleNamespace(platform="win32"))
    opened = drive_folder_dialog(monkeypatch)
    try:
        assert folder_dialog.choose_sheets_folder() is None
        dialog = opened[0]
        assert dialog.folder.text() == str(blocked)
        assert str(blocked) in dialog.error.text()
        assert "Controlled folder access" in dialog.error.text()
        assert Settings.load().sheets_dir == str(blocked)
    finally:
        qs.clear()


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions")
def test_folder_error_names_the_reason_not_the_test_file(app, tmp_path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    dialog = folder_dialog.FolderDialog(str(locked), "", "en", GLACIER_DARK)
    try:
        dialog.try_folder()
    finally:
        locked.chmod(0o700)
    assert dialog.error.text() == (
        f"Calculon can't create or write to {locked}. Permission denied.\n\nPick another folder."
    )


@pytest.mark.parametrize("theme", [GLACIER_DARK, GLACIER_LIGHT])
def test_folder_dialog_follows_the_theme_and_fits_the_error(app, tmp_path, theme) -> None:
    blocker = tmp_path / "not-a-folder"
    blocker.write_text("")
    themes.apply(app, theme)
    dialog = folder_dialog.FolderDialog(str(blocker / "Calculon"), "", "en", theme)
    dialog.show()
    pump(app)
    height = dialog.height()
    QTest.keyClick(dialog.folder, Qt.Key.Key_Return)  # Enter means "Use this folder"
    pump(app)
    error = dialog.error
    try:
        assert dialog.isVisible() and error.isVisible()
        assert error.palette().color(QPalette.ColorRole.WindowText).name() == theme.error
        page = dialog.findChild(QWidget, "page")
        assert page.palette().color(page.backgroundRole()).name() == theme.bg
        assert dialog.use_button.objectName() == "primary"
        assert not dialog.icon.pixmap().isNull() and dialog.icon.isVisible()
        # the whole wrapped message shows without resizing the window by hand
        assert dialog.height() > height
        assert error.height() >= error.heightForWidth(error.width())
        assert error.mapTo(dialog, error.rect().bottomLeft()).y() < dialog.height()
    finally:
        dialog.close()
        themes.apply(app, GLACIER_DARK)


def test_typing_saves_and_calculates(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("a = 5\na * 2")
    pump(app)
    assert window.editor.result_text(1) == "10"
    window.save_current()
    assert window.store.read(window.current[1]) == "a = 5\na * 2"


def test_folders_pins_trash_restore(window, app) -> None:
    store = window.store
    folder = store.create_folder("", "Work")
    rel = store.create_sheet(folder, "Budget", "$5")
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


def test_search_filters_sheets(window, app) -> None:
    window.store.create_sheet("", "Holiday", "flights $400")
    window.sidebar.search.setText("flights")
    pump(app)
    tree = window.sidebar.tree
    assert [tree.topLevelItem(i).text(0) for i in range(tree.topLevelItemCount())] == ["Holiday"]


def test_sidebar_watches_only_real_sheet_folders(window, tmp_path: Path) -> None:
    root = window.store.root
    window.store.create_folder(name="Work")
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
    ("colours", "mode", "accent", "selection", "on_accent"),
    [
        ("ember", "dark", "#f0a35e", "#45382e", "#1a1b20"),
        ("ember", "light", "#c2410c", "#f6dcc3", "#ffffff"),
        ("glacier", "dark", "#60a5fa", "#1c3767", "#0f172a"),
        ("glacier", "light", "#2563eb", "#dbeafe", "#ffffff"),
    ],
)
def test_each_theme_uses_its_accent(
    window, app, colours, mode, accent, selection, on_accent
) -> None:
    # links, selection, focus borders and primary buttons follow each theme's accent
    window.set_colours(colours)
    window.set_theme(mode)
    palette = QApplication.palette()
    assert palette.link().color().name() == accent
    assert palette.highlight().color().name() == selection
    sheet = app.styleSheet()
    assert f"QLineEdit#search:focus {{ border-color: {accent}; }}" in sheet
    assert f"QPushButton#primary {{ background: {accent}; border-color: {accent};" in sheet
    assert f"color: {on_accent}; font-weight: 600;" in sheet


def test_ukrainian_numbers_follow_language(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("1 234,5 + 10\n5 кг у г")
    window.set_language("uk")
    pump(app)
    assert window.editor.result_text(0) == "1 244,5"
    assert window.editor.result_text(1) == "5 000 г"
    window.set_language("en")
    window.editor.setPlainText("1,234.5 + 10")
    pump(app)
    assert window.editor.result_text(0) == "1,244.5"


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


def test_sidebar_toggle_keeps_the_tick_and_survives_a_restart(window, app) -> None:
    tick = window._actions["toggle_sidebar"]
    window.sidebar_button.click()
    assert window.sidebar.isHidden() and not tick.isChecked()
    window._focus_search()  # Ctrl+P shows the sidebar again and ticks the menu item
    assert not window.sidebar.isHidden() and tick.isChecked()
    tick.trigger()
    window.close()
    w = MainWindow()
    w.show()
    pump(app)
    assert w.sidebar.isHidden() and not w._actions["toggle_sidebar"].isChecked()
    w.set_sidebar_visible(True)
    w.splitter.moveSplitter(0, 1)  # the divider dragged all the way left
    assert w.splitter.sizes()[0] > 0
    w.close()


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


def test_focus_mode_brings_the_sidebar_back_as_it_was(window, app) -> None:
    window.set_sidebar_visible(False)
    window.set_focus_mode(True)
    window.close()
    w = MainWindow()  # focus mode survives a restart
    w.show()
    pump(app)
    assert w.menuBar().isHidden() and w.sidebar.isHidden()
    w.set_focus_mode(False)
    assert not w.menuBar().isHidden() and w.sidebar.isHidden()  # it was hidden before
    w.set_sidebar_visible(True)
    w.set_focus_mode(True)
    w.close()
    w = MainWindow()
    w.show()
    pump(app)
    w.set_focus_mode(False)
    assert not w.sidebar.isHidden()
    w.close()


def test_shortcuts_dialog_lists_menu_and_sidebar_keys(window) -> None:
    rows = dict(ShortcutsDialog(window.menuBar(), window.t, window).rows())
    assert rows["New Sheet"] == key_text(QKeySequence.StandardKey.New)
    assert rows["Comment Line"] == key_text("Ctrl+/")
    assert rows["Line Numbers"] == key_text("Ctrl+Shift+L")
    assert rows["Rename"] == "F2"
    assert "Keyboard Shortcuts" in rows


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
    dlg = SettingsDialog(window.settings, window.t, window)
    pages = [dlg.nav.item(i).text() for i in range(dlg.nav.count())]
    assert pages == ["General", "Appearance", "Numbers", "Exchange Rates", "Spell Check", "Vim"]
    assert dlg.pages.count() == len(pages)
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


@pytest.mark.parametrize("same_name", [False, True])
def test_settings_switch_to_folder_with_directory_link(
    window, tmp_path: Path, monkeypatch: pytest.MonkeyPatch, same_name: bool
) -> None:
    old_store = window.store
    old_sheet = window.current[1]
    documents = tmp_path / "Documents"
    store = SheetStore(documents)
    store.create_folder(name="Work")
    new_sheet = old_sheet if same_name else "Work/Budget.txt"
    store.write(new_sheet, "5 + 6")
    music = tmp_path / "Music"
    music.mkdir()
    (music / "Other.txt").write_text("outside the sheets folder", encoding="utf-8")
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
    monkeypatch.setattr(
        settings_dialog.QFileDialog, "getExistingDirectory", lambda *_: str(documents)
    )

    def accept(dialog):
        dialog._browse()
        return SettingsDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", accept)
    window.open_settings()

    assert old_store.read(old_sheet) == "7 + 8"
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
    window.store.create_folder("", "Work")
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


def test_switching_sheets_between_folders_keeps_the_sidebar_still(
    app, home, tmp_path, monkeypatch
) -> None:
    """Startup: folder A closed, B open, last sheet in A. Switching between them must not
    close A again or move any row (it used to collapse A, so the list jumped)."""
    monkeypatch.setattr(rates.RatesService, "refresh", lambda self: None)
    sheets = tmp_path / "sheets"
    store = SheetStore(sheets)
    for folder in ("A", "B"):
        store.create_folder("", folder)
        for n in range(3):
            store.create_sheet(folder, f"{folder}{n}", "1")
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(sheets))
    qs.setValue("last_sheet", "A/A1.txt")
    qs.setValue("sidebar/expanded", ["B"])
    qs.sync()
    w = MainWindow()
    w.show()
    pump(app)
    tree = w.sidebar.tree

    def row_of(name: str) -> int:
        item = tree.findItems(name, Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive)[0]
        return tree.visualItemRect(item).y()

    folder_a = tree.findItems("A", Qt.MatchFlag.MatchExactly | Qt.MatchFlag.MatchRecursive)[0]
    assert folder_a.isExpanded()
    before = {name: row_of(name) for name in ("A0", "B0", "B2")}
    items_before = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    for rel in ("B/B2.txt", "A/A0.txt", "B/B0.txt", "A/A2.txt"):
        w.open_sheet(rel)
        pump(app)
        assert folder_a.isExpanded()
        assert {name: row_of(name) for name in before} == before
    # the same row objects: nothing was rebuilt
    assert [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())] == items_before
    assert "A" in w.sidebar.expanded
    w.close()


def test_unknown_settings_fall_back_to_defaults(app) -> None:
    """A hand-edited or newer config must not leave the app in a state it can't show."""
    qs = QSettings()
    qs.clear()
    for key, value in {
        "language": "xx",
        "theme": "zzz",
        "colours": "zzz",
        "number_style": "bogus",
        "date_order": "YDM",
        "dollar": "XYZ",
        "font_size": "abc",
        "max_decimals": "999",
    }.items():
        qs.setValue(key, value)
    qs.sync()
    s = Settings.load()
    qs.clear()
    assert (s.language, s.theme, s.number_style, s.date_order, s.dollar) == (
        "en",
        "dark",
        "auto",
        "DMY",
        "USD",
    )
    assert (s.font_size, s.max_decimals) == (14, 20)
    assert s.colours == "glacier"


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


def test_sheet_scrollbar_shows_while_scrolling_then_fades(window, app) -> None:
    window.open_help()
    bar = window.editor.verticalScrollBar()
    assert isinstance(bar, SheetScrollBar)
    bar.HIDE_AFTER_MS = 0
    bar._hide_timer.setInterval(0)
    bar.setValue(bar.maximum() // 2)
    assert bar.opacity == 1.0
    end = time.time() + 1
    while bar.opacity > 0 and time.time() < end:
        app.processEvents()
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
    assert by_name["Keyboard Shortcuts"].shortcut() == QKeySequence("Shift+F1")


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
    assert act.shortcut() == QKeySequence("F7")

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
    folders = {str(Path(base).parent) for base in SYSTEM_SPELLING.dictionaries.values()}
    monkeypatch.setenv("DICPATH", os.pathsep.join(sorted(folders)))
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
def test_always_on_top_saved_choice_applies_before_first_show(window, app, enabled) -> None:
    QSettings().setValue("always_on_top", enabled)
    restored = MainWindow()
    try:
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
    finally:
        restored.close()
        restored.deleteLater()


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


def test_a_message_takes_the_place_of_the_total(window, app) -> None:
    window.new_sheet("")
    window.editor.setPlainText("$10\n$20")
    window.editor.recalculate()
    window._copy_total()
    message = window.message_label
    assert message.text() == "Copied $30.00"
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
