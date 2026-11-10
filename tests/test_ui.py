"""UI smoke tests: the real window, offscreen, with every user folder in a temp dir."""

import os
from pathlib import Path

import pytest


@pytest.fixture(scope="module")
def home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    h = tmp_path_factory.mktemp("home")
    os.environ.update(
        HOME=str(h),
        XDG_CONFIG_HOME=str(h / ".config"),
        XDG_DATA_HOME=str(h / ".local" / "share"),
        XDG_CACHE_HOME=str(h / ".cache"),
        QT_QPA_PLATFORM="offscreen",
    )
    return h


@pytest.fixture(scope="module")
def app(home: Path):
    from PySide6.QtCore import QCoreApplication
    from PySide6.QtWidgets import QApplication

    QCoreApplication.setOrganizationName("calculon-tests")
    QCoreApplication.setApplicationName("Calculon")
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    from PySide6.QtCore import QSettings

    from calculon import rates
    from calculon.ui.main_window import MainWindow

    monkeypatch.setattr(rates.RatesService, "refresh", lambda self: None)
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(tmp_path / "sheets"))
    qs.sync()
    w = MainWindow()
    w.show()
    yield w
    w.close()
    w.deleteLater()


def pump(app) -> None:
    for _ in range(5):
        app.processEvents()


def test_first_start_creates_welcome_sheet(window, app) -> None:
    assert window.store.all_sheets() == ["Welcome.txt"]
    assert window.current == ("sheet", "Welcome.txt")
    pump(app)
    texts = [line.text for line in window.editor.result.lines]
    assert "$64.00" in texts  # 20% off $80


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


def test_comment_toggle_and_copy(window, app) -> None:
    from PySide6.QtGui import QGuiApplication

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
    from PySide6.QtWidgets import QApplication

    window.set_theme("light")
    assert QApplication.palette().base().color().name() == "#fbfbf9"
    window.set_theme("dark")
    assert QApplication.palette().base().color().name() == "#1a1b20"


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
    checkable = [a for a in view.actions() if a.isCheckable()]
    assert checkable and all(a.icon().isNull() for a in checkable)


def test_icons_are_coloured_from_the_start(window) -> None:
    from PySide6.QtGui import QColor

    from calculon.ui import icons

    trash = window.menuBar().actions()[0].menu().actions()[-1]  # Quit, red group
    image = trash.icon().pixmap(icons.ICON_SIZE).toImage()
    colours = {
        QColor(image.pixel(x, y)).name()
        for x in range(image.width())
        for y in range(image.height())
        if QColor.fromRgba(image.pixel(x, y)).alpha() == 255
    }
    assert icons.color_for("quit") in colours


def test_shortcuts_dialog_lists_menu_and_sidebar_keys(window) -> None:
    from PySide6.QtGui import QKeySequence

    from calculon.ui.shortcuts_dialog import ShortcutsDialog, key_text

    rows = dict(ShortcutsDialog(window.menuBar(), window.t, window).rows())
    assert rows["New Sheet"] == key_text(QKeySequence.StandardKey.New)
    assert rows["Comment Line"] == key_text("Ctrl+/")
    assert rows["Line Numbers"] == key_text("Ctrl+Shift+L")
    assert rows["Rename"] == "F2"
    assert "Keyboard Shortcuts" in rows


def test_qt_buttons_follow_language(window) -> None:
    from PySide6.QtWidgets import QDialogButtonBox

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
    from calculon.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(window.settings, window.t, window)
    assert dlg.nav.count() == 3
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


def test_dialog_buttons_have_no_stock_icons(app) -> None:
    from PySide6.QtWidgets import QStyle

    assert app.style().styleHint(QStyle.StyleHint.SH_DialogButtonBox_ButtonsHaveIcons) == 0


def test_ligature_sample_follows_checkbox(window) -> None:
    from PySide6.QtGui import QFont

    from calculon.ui.settings_dialog import SettingsDialog

    dlg = SettingsDialog(window.settings, window.t, window)
    calt = QFont.Tag("calt")
    dlg.ligatures.setChecked(False)
    assert dlg.ligature_sample.font().featureValue(calt) == 0
    dlg.ligatures.setChecked(True)
    assert not dlg.ligature_sample.font().isFeatureSet(calt)


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
    from PySide6.QtCore import QSettings, Qt

    from calculon import rates
    from calculon.storage import SheetStore
    from calculon.ui.main_window import MainWindow

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
    from PySide6.QtCore import QSettings

    from calculon.settings import Settings

    qs = QSettings()
    qs.clear()
    for key, value in {
        "language": "xx",
        "theme": "zzz",
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


def test_undo_survives_switching_sheets(window, app) -> None:
    from PySide6.QtGui import QTextCursor

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


def test_autocomplete_lists_variables_first_with_their_kind(window, app) -> None:
    from PySide6.QtTest import QTest

    from calculon.ui.editor import KIND_ROLE

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
