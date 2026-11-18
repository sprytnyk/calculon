"""Vim mode through side-vim: how Calculon hooks it up. side-vim's own keys are tested there."""

import sys
from pathlib import Path

import pytest
from PySide6.QtCore import QEvent, QPoint, Qt, QTimer
from PySide6.QtGui import QGuiApplication, QKeyEvent, qt_set_sequence_auto_mnemonic
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication
from side_vim import Mode
from side_vim.keys import control_modifier

from calculon.ui.settings_dialog import SettingsDialog
from calculon.ui.shortcuts_dialog import ShortcutsDialog
from calculon.ui.vim import ctrl
from tests.test_ui import off_centre, pump, spell_window, underlined

# Qt's Ctrl, for the app's shortcuts, is Cmd on macOS. Vim's Ctrl is the Control key there.
APP_CTRL = Qt.KeyboardModifier.ControlModifier
VIM_CTRL = control_modifier()
TEXT = "rent = $900\nfood = $300\nrent + food"


@pytest.fixture
def vim(window, app):
    """The window with vim mode on and a new sheet holding TEXT, cursor at the start."""
    window.settings.vim_mode = True
    window.apply_settings()
    window.new_sheet("")
    ed = window.editor
    ed.setPlainText(TEXT)
    ed.moveCursor(ed.textCursor().MoveOperation.Start)
    ed.setFocus()
    pump(app)
    return window


def esc(widget) -> None:
    QTest.keyClick(widget, Qt.Key.Key_Escape)


def type_ukrainian(widget, text: str) -> None:
    """Key presses with Cyrillic text, as the Ukrainian layout sends them. QTest's
    keyClicks aborts the test run on anything past Latin-1."""
    for ch in text:
        for kind in (QEvent.Type.KeyPress, QEvent.Type.KeyRelease):
            event = QKeyEvent(kind, ord(ch.upper()), Qt.KeyboardModifier.NoModifier, ch)
            QApplication.sendEvent(widget, event)


def test_off_by_default(window) -> None:
    assert window.settings.vim_mode is False
    assert not window.editor.vim_on()
    assert window.editor.vim is None  # side-vim isn't even attached
    assert window.vim_mode_label.isHidden()


def test_mode_and_pending_keys_in_the_status_bar(vim, app) -> None:
    ed, mode, pending = vim.editor, vim.vim_mode_label, vim.vim_pending_label
    bar = vim.statusBar()
    assert mode.isHidden()  # Normal mode shows nothing, as in vim
    QTest.keyClicks(ed, "i")
    assert mode.text() == "-- INSERT --" and mode.isVisible()
    pump(app)
    assert mode.mapTo(bar, QPoint()).x() < vim.total_label.mapTo(bar, QPoint()).x()
    esc(ed)
    assert mode.isHidden()
    QTest.keyClicks(ed, "V")
    assert mode.text() == "-- VISUAL LINE --"
    esc(ed)
    QTest.keyClicks(ed, "2d")
    assert pending.text() == "2d" and pending.isVisible()
    pump(app)
    pending_x = pending.mapTo(bar, QPoint()).x()
    rates_x = vim.rates_label.mapTo(bar, QPoint()).x()
    assert bar.width() // 2 < pending_x < rates_x
    esc(ed)
    assert pending.isHidden()


def test_normal_mode_types_nothing_and_edits_like_vim(vim) -> None:
    ed = vim.editor
    QTest.keyClicks(ed, "xyz")
    assert ed.toPlainText() == TEXT[1:]
    QTest.keyClicks(ed, "u")
    assert ed.toPlainText() == TEXT


def test_yank_uses_the_system_clipboard(vim) -> None:
    QTest.keyClicks(vim.editor, "yy")
    assert QGuiApplication.clipboard().text() == "rent = $900\n"


def test_esc_closes_autocomplete_before_leaving_insert(vim, app) -> None:
    ed = vim.editor
    QTest.keyClicks(ed, "Go")
    QTest.keyClicks(ed, "re")
    pump(app)
    popup = ed._completer.popup()
    assert popup.isVisible()
    esc(popup)  # keys go to the popup while it's open
    assert not popup.isVisible()
    assert ed.vim.mode is Mode.INSERT
    esc(ed)
    assert ed.vim.mode is Mode.NORMAL


def test_slash_searches_and_enter_goes_back_to_the_sheet(vim, app) -> None:
    ed, bar = vim.editor, vim.find_bar
    QTest.keyClicks(ed, "/")
    assert bar.isVisible() and bar.field.hasFocus()
    QTest.keyClicks(bar.field, "rent")
    QTest.keyClick(bar.field, Qt.Key.Key_Return)
    assert not bar.isVisible()
    assert ed.hasFocus()
    cur = ed.textCursor()
    assert not cur.hasSelection()
    assert cur.position() == TEXT.index("rent + food")  # the next one after the cursor
    QTest.keyClicks(ed, "n")  # goes round to the first
    assert ed.textCursor().position() == 0
    QTest.keyClicks(ed, "N")
    assert ed.textCursor().position() == TEXT.index("rent + food")


def test_question_mark_searches_backward(vim) -> None:
    ed, bar = vim.editor, vim.find_bar
    QTest.keyClicks(ed, "G")
    QTest.keyClicks(ed, "?")
    QTest.keyClicks(bar.field, "food")
    QTest.keyClick(bar.field, Qt.Key.Key_Return)
    assert ed.textCursor().position() == TEXT.index("food")
    QTest.keyClicks(ed, "n")  # n keeps going backward
    assert ed.textCursor().position() == TEXT.rindex("food")


def test_esc_in_the_find_bar_puts_the_cursor_back(vim, app) -> None:
    ed, bar = vim.editor, vim.find_bar
    QTest.keyClicks(ed, "j")
    start = ed.textCursor().position()
    QTest.keyClicks(ed, "/")
    QTest.keyClicks(bar.field, "rent")
    pump(app)
    assert ed.textCursor().position() != start  # the live search moved it
    esc(bar.field)
    assert not bar.isVisible()
    assert ed.textCursor().position() == start
    assert not ed.textCursor().hasSelection()
    assert ed.vim.mode is Mode.NORMAL


def test_ctrl_f_is_vims_in_normal_mode_and_find_in_insert(vim, app) -> None:
    ed, bar = vim.editor, vim.find_bar
    QTest.keyClick(ed, Qt.Key.Key_F, VIM_CTRL)
    assert not bar.isVisible()  # page down, as in vim
    QTest.keyClicks(ed, "ggi")
    QTest.keyClick(ed, Qt.Key.Key_F, APP_CTRL)
    assert bar.isVisible()
    QTest.keyClicks(bar.field, "food")
    QTest.keyClick(bar.field, Qt.Key.Key_Return)
    assert ed.vim.mode is Mode.NORMAL  # Enter goes back to Normal mode
    assert ed.textCursor().position() == TEXT.index("food")
    assert ed.toPlainText() == TEXT


def test_calculon_commands_still_work_in_normal_mode(vim, app) -> None:
    ed = vim.editor
    QTest.keyClicks(ed, "G$")
    vim.activateWindow()
    QTest.keyClick(ed, Qt.Key.Key_T, APP_CTRL)  # insert total
    assert "total" in ed.toPlainText()
    assert ed.vim.mode is Mode.NORMAL


def test_delete_to_line_edge_only_types_in_insert_mode(vim) -> None:
    ed = vim.editor
    edge = Qt.KeyboardModifier.ControlModifier | Qt.KeyboardModifier.ShiftModifier
    QTest.keyClicks(ed, "$")
    QTest.keyClick(ed, Qt.Key.Key_Backspace, edge)
    assert ed.toPlainText() == TEXT
    QTest.keyClicks(ed, "A")
    QTest.keyClick(ed, Qt.Key.Key_Backspace, edge)
    assert ed.toPlainText() == TEXT.replace("rent = $900", "", 1)


def test_every_sheet_opens_in_normal_mode(vim) -> None:
    ed = vim.editor
    QTest.keyClicks(ed, "i")
    vim.new_sheet("")
    assert ed.vim.mode is Mode.NORMAL
    assert vim.vim_mode_label.isHidden()
    QTest.keyClicks(ed, "i")
    vim.open_help()
    assert ed.vim.mode is Mode.NORMAL


def test_help_sheet_allows_movement_but_no_edits(vim) -> None:
    vim.open_help()
    ed = vim.editor
    before = ed.toPlainText()
    QTest.keyClicks(ed, "jwxddrX~i")
    assert ed.toPlainText() == before
    assert ed.textCursor().position() > 0


@pytest.mark.parametrize("start", ["i", "2d"])  # in Insert mode, or with keys pending
def test_turning_it_off_gives_the_plain_editor_back(vim, start) -> None:
    ed = vim.editor
    QTest.keyClicks(ed, start)
    vim.settings.vim_mode = False
    vim.apply_settings()
    assert not ed.vim_on()
    assert vim.vim_mode_label.isHidden()
    assert vim.vim_pending_label.isHidden()
    QTest.keyClicks(ed, "x")
    assert ed.toPlainText() == "x" + TEXT


def test_shortcuts_window_lists_vim_keys_only_when_on(vim) -> None:
    rows = dict(ShortcutsDialog(vim.menuBar(), vim.t, vim, vim=True).rows())
    assert rows["Vim mode"] == ""  # the section heading
    assert rows["Move"].startswith("h j k l")
    assert rows["Back to Normal mode"] == f"Esc, {ctrl('[')}"
    rows = dict(ShortcutsDialog(vim.menuBar(), vim.t, vim).rows())
    assert "Vim mode" not in rows


@pytest.mark.parametrize("language", ["en", "uk"])
def test_shortcuts_window_fits_every_row(vim, app, language) -> None:
    vim.settings.language = language
    vim.apply_settings()
    dlg = ShortcutsDialog(vim.menuBar(), vim.t, vim, vim=True)
    dlg.show()
    pump(app)
    tree = dlg.tree
    assert tree.columnWidth(0) >= tree.sizeHintForColumn(0)  # no text cut short
    dlg.close()


def test_settings_switch(window) -> None:
    dlg = SettingsDialog(window.settings, window.t, window)
    assert not dlg.vim_mode.isChecked()
    dlg.vim_mode.setChecked(True)
    assert dlg.result_settings().vim_mode is True


def test_every_vim_text_is_translated(window) -> None:
    from calculon.translations import en, uk

    names = [k for k in en.T if k.startswith(("vim_", "shortcuts_vim", "hint_vim"))]
    assert len(names) > 10
    assert [k for k in names if k not in uk.T] == []


def test_switching_sheets_closes_the_search(vim, app) -> None:
    ed, bar = vim.editor, vim.find_bar
    QTest.keyClicks(ed, "/")
    QTest.keyClicks(bar.field, "food")
    pump(app)
    vim.new_sheet("")
    pump(app)
    assert not bar.isVisible()
    assert ed.find_matches() == []
    assert ed.toPlainText() == ""  # the new sheet, untouched


def test_esc_never_brings_back_a_cursor_from_another_sheet(vim, app) -> None:
    ed, bar = vim.editor, vim.find_bar
    QTest.keyClicks(ed, "/")
    QTest.keyClicks(bar.field, "food")
    vim.settings.vim_mode = False  # without vim mode the bar stays open on a new sheet
    vim.apply_settings()
    vim.new_sheet("")
    vim.settings.vim_mode = True
    vim.apply_settings()
    assert bar.isVisible()
    esc(bar.field)
    assert ed.textCursor().document() is ed.document()
    assert ed.toPlainText() == ""


@pytest.mark.parametrize("repeats", [1, 3])
def test_the_total_stays_put_as_vim_labels_come_and_go(vim, app, repeats: int) -> None:
    ed = vim.editor
    vim.rates_label.setText("Rates from a very long time ago, click to refresh " * repeats)
    ed.recalculate()
    assert vim.total_label.text()
    where = off_centre(vim.total_label, app)
    assert abs(where) <= 2
    QTest.keyClicks(ed, "i")  # -- INSERT -- at the left
    assert off_centre(vim.total_label, app) == where
    esc(ed)
    QTest.keyClicks(ed, "2d")  # pending keys at the right
    assert off_centre(vim.total_label, app) == where
    esc(ed)
    assert off_centre(vim.total_label, app) == where


def test_a_message_leaves_the_vim_mode_alone(vim, app) -> None:
    QTest.keyClicks(vim.editor, "i")
    vim._copy_total()
    pump(app)
    assert vim.message_label.isVisible()
    assert vim.vim_mode_label.isVisible() and vim.vim_mode_label.text() == "-- INSERT --"


def test_every_shortcut_row_has_an_icon(vim) -> None:
    tree = ShortcutsDialog(vim.menuBar(), vim.t, vim, vim=True).tree
    items = [tree.topLevelItem(i) for i in range(tree.topLevelItemCount())]
    rows = [it for it in items if it.text(1)]  # section headings have no keys
    assert [it.text(0) for it in rows if it.icon(0).isNull()] == []


def ctrl_w(widget, key: str) -> None:
    """Press Ctrl+W, then key. A keyboard sends a control character with Ctrl+W, but QTest
    would send a "w", and an editor types it when Ctrl is the Control key, as on macOS."""
    QTest.sendKeyEvent(QTest.KeyAction.Click, widget, Qt.Key.Key_W, "\x17", VIM_CTRL)
    QTest.keyClicks(widget, key)


@pytest.mark.parametrize("directory", [False, True])
def test_sidebar_highlight_follows_keyboard_focus(vim, app, directory) -> None:
    store, tree, ed = vim.store, vim.sidebar.tree, vim.editor
    store.create_directory("", "Work")
    store.create_sheet("", "Plans", "1")
    vim.sidebar.rebuild()
    item = tree.findItems("Work" if directory else "Plans", Qt.MatchFlag.MatchRecursive)[0]
    tree.setCurrentItem(item)
    tree.scrollToItem(item)
    vim.activateWindow()
    tree.setFocus()
    pump(app)
    y = tree.visualItemRect(item).center().y()
    highlight = tree.palette().highlight().color()
    assert tree.viewport().grab().toImage().pixelColor(6, y) == highlight
    ctrl_w(tree, "l")
    pump(app)
    assert app.focusWidget() is ed
    assert tree.currentItem() is item
    assert tree.viewport().grab().toImage().pixelColor(6, y) != highlight
    ctrl_w(ed, "h")
    pump(app)
    assert tree.currentItem() is item
    assert tree.viewport().grab().toImage().pixelColor(6, y) == highlight


def test_ctrl_w_moves_between_the_list_the_sheet_and_the_answers(vim, app) -> None:
    ed, tree, results = vim.editor, vim.sidebar.tree, vim.editor.results
    pending = vim.vim_pending_label
    vim.activateWindow()
    QTest.keyClick(ed, Qt.Key.Key_W, VIM_CTRL)
    assert pending.text() == "^W"  # waits for the next key, as in vim
    QTest.keyClicks(ed, "h")
    assert pending.isHidden()
    assert app.focusWidget() is tree
    ctrl_w(tree, "h")  # nothing further left
    assert app.focusWidget() is tree
    ctrl_w(tree, "l")
    assert app.focusWidget() is ed
    ctrl_w(ed, "l")
    assert app.focusWidget() is results
    ctrl_w(results, "l")  # nothing further right
    assert app.focusWidget() is results
    ctrl_w(results, "h")
    assert app.focusWidget() is ed
    assert ed.toPlainText() == TEXT
    assert ed.textCursor().position() == 0  # h and l went to Ctrl+W, not the cursor


def test_leaving_the_list_drops_a_ctrl_w(vim, app) -> None:
    ed, tree, pending = vim.editor, vim.sidebar.tree, vim.vim_pending_label
    vim.activateWindow()
    ctrl_w(ed, "h")
    QTest.keyClick(tree, Qt.Key.Key_W, VIM_CTRL)
    assert pending.text() == "^W"
    ed.setFocus()
    pump(app)
    assert pending.isHidden()
    tree.setFocus()
    pump(app)
    QTest.keyClicks(tree, "l")  # no Ctrl+W waiting: l doesn't jump
    assert app.focusWidget() is tree


def test_turning_vim_off_in_the_answers_goes_back_to_the_sheet(vim, app) -> None:
    ed = vim.editor
    vim.activateWindow()
    ctrl_w(ed, "l")
    assert app.focusWidget() is ed.results
    vim.settings.vim_mode = False
    vim.apply_settings()
    assert app.focusWidget() is ed


def test_ctrl_w_ctrl_l_isnt_the_insert_reference_shortcut(vim, app) -> None:
    ed, tree = vim.editor, vim.sidebar.tree
    vim.activateWindow()
    QTest.keyClick(ed, Qt.Key.Key_W, VIM_CTRL)
    QTest.keyClick(ed, Qt.Key.Key_H, VIM_CTRL)
    assert app.focusWidget() is tree
    QTest.keyClick(tree, Qt.Key.Key_W, VIM_CTRL)
    QTest.keyClick(tree, Qt.Key.Key_L, VIM_CTRL)
    assert app.focusWidget() is ed
    assert ed.toPlainText() == TEXT


def test_ctrl_w_h_stays_put_while_the_sidebar_is_hidden(vim, app) -> None:
    ed = vim.editor
    vim.set_sidebar_visible(False)
    ctrl_w(ed, "h")
    assert app.focusWidget() is ed
    assert ed.textCursor().position() == 0


def test_ctrl_w_is_typing_in_insert_mode(vim, app) -> None:
    ed = vim.editor
    QTest.keyClicks(ed, "i")
    ctrl_w(ed, "h")
    assert app.focusWidget() is ed
    assert ed.vim.mode is Mode.INSERT
    assert ed.toPlainText().startswith("h")


def test_j_k_and_enter_in_the_sheet_list(vim, app) -> None:
    store, sidebar, ed = vim.store, vim.sidebar, vim.editor
    store.create_directory("", "Work")
    other = store.create_sheet("Work", "Plans", "1 + 1")
    sidebar.rebuild()
    pump(app)
    ctrl_w(ed, "h")
    tree = sidebar.tree
    directory = tree.findItems("Work", Qt.MatchFlag.MatchRecursive)[0]
    directory.setExpanded(False)
    tree.setCurrentItem(directory)
    QTest.keyClick(tree, Qt.Key.Key_Return)  # Enter opens a directory
    assert directory.isExpanded()
    QTest.keyClicks(tree, "j")
    assert tree.currentItem().text(0) == "Plans"
    QTest.keyClicks(tree, "k")
    assert tree.currentItem() is directory
    QTest.keyClicks(tree, "j")
    QTest.keyClick(tree, Qt.Key.Key_Return)  # Enter opens a sheet and goes to it
    assert vim.current == ("sheet", other)
    assert app.focusWidget() is ed


def test_d_in_sheet_list_uses_the_existing_delete_actions(vim, app) -> None:
    store, sidebar = vim.store, vim.sidebar
    store.create_directory("", "Work")
    store.create_sheet("", "Plans", "1")
    store.trash(store.create_sheet("", "Old", "1"))
    sidebar.rebuild()
    tree = sidebar.tree
    calls = []
    sidebar.trash.disconnect(vim.trash)
    sidebar.empty_trash.disconnect(vim.empty_trash)
    sidebar.trash.connect(lambda path: calls.append(path))
    sidebar.empty_trash.connect(lambda: calls.append("empty"))
    tree.setFocus()
    pump(app)
    items = [tree.findItems(name, Qt.MatchFlag.MatchRecursive)[0] for name in ("Plans", "Work")]
    items.append(tree.topLevelItem(tree.topLevelItemCount() - 1))
    for item in items:
        tree.setCurrentItem(item)
        QTest.keyClicks(tree, "d")
    assert calls == ["Plans.txt", "Work", "empty"]


@pytest.mark.parametrize("directory", [False, True])
def test_r_restores_selected_trash_item(vim, app, directory) -> None:
    store = vim.store
    if directory:
        store.create_directory("", "Work")
        path = store.create_sheet("Work", "Plans", "saved content")
        store.trash("Work")
        name = "Work"
    else:
        path = store.create_sheet("", "Plans", "saved content")
        store.trash(path)
        name = "Plans"
    vim.sidebar.rebuild()
    tree = vim.sidebar.tree
    tree.setCurrentItem(tree.findItems(name, Qt.MatchFlag.MatchRecursive)[0])
    tree.setFocus()
    pump(app)
    QTest.keyClicks(tree, "r")
    assert store.read(path) == "saved content"
    assert not store.trashed()


def test_j_k_and_enter_in_the_answers(vim, app) -> None:
    ed, results = vim.editor, vim.editor.results
    ed.setPlainText("rent = $900\n\n// food\nfood = $300")
    ed.recalculate()
    ctrl_w(ed, "l")
    QTest.keyClicks(results, "j")  # past the empty line and the comment
    assert ed.textCursor().blockNumber() == 3
    QTest.keyClicks(results, "j")  # no answer below: stays
    assert ed.textCursor().blockNumber() == 3
    QTest.keyClick(results, Qt.Key.Key_Return)
    assert QGuiApplication.clipboard().text() == ed.result_text(3)
    QTest.keyClicks(results, "kx")  # x does nothing here, it's not the sheet
    assert ed.textCursor().blockNumber() == 0
    assert ed.toPlainText() == "rent = $900\n\n// food\nfood = $300"


def test_r_replaces_characters_in_the_sheet(vim, app) -> None:
    ed = vim.editor
    QTest.keyClicks(ed, "3rX")
    assert ed.toPlainText() == "XXXt = $900" + TEXT[11:]
    assert ed.textCursor().position() == 2  # on the last one, as in vim
    QTest.keyClicks(ed, "u")
    assert ed.toPlainText() == TEXT
    type_ukrainian(ed, "кц")  # the Ukrainian r, and the character stays as typed
    assert ed.toPlainText() == "цent" + TEXT[4:]
    QTest.keyClicks(ed, "r")
    assert vim.vim_pending_label.text() == "r"
    esc(ed)  # Esc cancels r
    assert vim.vim_pending_label.isHidden()
    assert ed.toPlainText() == "цent" + TEXT[4:]


def test_tilde_switches_case_in_the_sheet(vim) -> None:
    ed = vim.editor
    QTest.keyClicks(ed, "3~")
    assert ed.toPlainText() == "RENt = $900" + TEXT[11:]
    assert ed.textCursor().position() == 3  # past them, as in vim
    QTest.keyClicks(ed, "u")
    assert ed.toPlainText() == TEXT
    QTest.keyClicks(ed, "jv$~")
    assert ed.toPlainText() == "rent = $900\nFOOD = $300\nrent + food"
    assert ed.textCursor().position() == 12  # back at the start of the selection
    assert ed.vim.mode is Mode.NORMAL


def test_r_does_nothing_in_the_sheet_list_or_the_answers(vim, app) -> None:
    ed, tree, results = vim.editor, vim.sidebar.tree, vim.editor.results
    all_items = Qt.MatchFlag.MatchContains | Qt.MatchFlag.MatchRecursive
    names = [it.text(0) for it in tree.findItems("", all_items)]
    vim.activateWindow()
    ctrl_w(ed, "h")
    assert app.focusWidget() is tree
    QTest.keyClicks(tree, "rX~")
    type_ukrainian(tree, "кц")
    ctrl_w(tree, "l")
    ctrl_w(ed, "l")
    assert app.focusWidget() is results
    QTest.keyClicks(results, "rX~")
    type_ukrainian(results, "кц")
    assert ed.toPlainText() == TEXT
    assert vim.vim_pending_label.isHidden()
    assert [it.text(0) for it in tree.findItems("", all_items)] == names  # nothing renamed


def test_pending_r_in_the_sheet_ends_when_it_loses_the_focus(vim, app) -> None:
    ed, tree = vim.editor, vim.sidebar.tree
    vim.activateWindow()
    QTest.keyClicks(ed, "r")
    tree.setFocus()
    pump(app)
    QTest.keyClicks(tree, "X")
    ed.setFocus()
    pump(app)
    QTest.keyClicks(ed, "l")  # a motion again, not r's character
    assert ed.toPlainText() == TEXT
    assert ed.textCursor().position() == 1
    assert vim.vim_pending_label.isHidden()


def test_pane_keys_are_off_without_vim_mode(window, app) -> None:
    ed = window.editor
    window.activateWindow()
    ed.setFocus()
    pump(app)
    ed.setPlainText("")
    ctrl_w(ed, "h")
    assert app.focusWidget() is ed
    assert ed.toPlainText() == "h"  # a plain editor types the h


def test_spelling_keys(vim, app, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    spell = spell_window(vim, app, "pay teh rnet\n# оредна plan", tmp_path)
    ed = vim.editor
    ed.setFocus()
    menus: list[list[str]] = []

    def texts(menu) -> list[str]:
        return [act.text() for act in menu.actions()]

    monkeypatch.setattr(ed, "show_menu", lambda menu, _: menus.append(texts(menu)))

    def keys(typed: str) -> int:
        QTest.keyClicks(ed, typed)
        return ed.textCursor().position()

    assert [keys("]s"), keys("2]s"), keys("]s"), keys("[s")] == [4, 15, 4, 15]  # round past the end
    assert keys("2[s") == 4
    keys("z=")
    assert menus == [["1 the", "2 tech", "", "Add to Dictionary", "Ignore"]]
    keys("2z=")  # the second suggestion, without the menu
    assert (ed.toPlainText(), len(menus)) == ("pay tech rnet\n# оредна plan", 1)
    keys("u")
    assert ed.toPlainText() == "pay teh rnet\n# оредна plan"
    assert keys("2]szg") == 8
    assert (tmp_path / "words.txt").read_text(encoding="utf-8") == "rnet\n"
    assert keys("]szG") == 15
    assert "оредна" in spell.ignored
    assert keys("gg]s") == 4  # only teh is left
    pump(app)
    assert underlined(ed, 0) == ["teh"] and underlined(ed, 1) == []
    ed.set_spell_checker(None)
    assert keys("0]sz=") == 0  # spell check is off: nothing to find
    assert len(menus) == 1


@pytest.mark.parametrize("mnemonics", [True, False], ids=["menu shortcuts", "macOS"])
def test_z_equals_picks_a_suggestion_by_its_number(
    vim, app, tmp_path: Path, mnemonics: bool
) -> None:
    """1 to 9 pick from the z= list. macOS turns off Qt's &1 menu shortcuts."""
    spell_window(vim, app, "pay teh rent", tmp_path)
    ed = vim.editor
    ed.setFocus()
    QTest.keyClicks(ed, "]s")

    def press_two() -> None:
        menu = QApplication.activePopupWidget()
        if menu is not None:
            QTest.keyClicks(menu, "2")
            menu.close()  # when 2 didn't pick, the test then fails instead of waiting

    qt_set_sequence_auto_mnemonic(mnemonics)
    try:
        QTimer.singleShot(0, press_two)
        QTest.keyClicks(ed, "z=")
    finally:
        qt_set_sequence_auto_mnemonic(sys.platform != "darwin")  # Qt's own default
    assert ed.toPlainText() == "pay tech rent"


def test_only_insert_mode_hides_the_word_being_typed(vim, app, tmp_path: Path) -> None:
    spell_window(vim, app, "pay teh", tmp_path)
    ed = vim.editor
    ed.setFocus()
    QTest.keyClicks(ed, "$")
    pump(app)
    assert underlined(ed, 0) == ["teh"]  # Normal mode: the cursor is on it, not typing it
    QTest.keyClicks(ed, "a")
    pump(app)
    assert underlined(ed, 0) == []
    esc(ed)
    pump(app)
    assert underlined(ed, 0) == ["teh"]


def test_focus_mode_key_gets_past_vim(vim) -> None:
    """Vim keeps Ctrl+F for itself. Ctrl+Shift+F must still reach focus mode, or Normal
    mode would leave you in focus mode with the menu bar hidden."""
    keys = APP_CTRL | Qt.KeyboardModifier.ShiftModifier
    vim.activateWindow()
    assert QTest.qWaitForWindowActive(vim)
    assert vim.vim_mode_label.isHidden()  # Normal mode
    QTest.keyClick(vim.editor, Qt.Key.Key_F, keys)
    assert vim.menuBar().isHidden()
    QTest.keyClick(vim.editor, Qt.Key.Key_F, keys)
    assert not vim.menuBar().isHidden()
