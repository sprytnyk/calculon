"""Vim mode through side-vim: how Calculon hooks it up. side-vim's own keys are tested there."""

import pytest
from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtTest import QTest
from side_vim import Mode

from calculon.ui.settings_dialog import SettingsDialog
from calculon.ui.shortcuts_dialog import ShortcutsDialog
from tests.test_ui import off_centre, pump

CTRL = Qt.KeyboardModifier.ControlModifier
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


def test_off_by_default(window) -> None:
    assert window.settings.vim_mode is False
    assert not window.editor.vim_on()
    assert window.editor.vim is None  # side-vim isn't even attached
    assert window.vim_mode_label.isHidden()


def test_mode_and_pending_keys_in_the_status_bar(vim, app) -> None:
    ed, mode, pending = vim.editor, vim.vim_mode_label, vim.vim_pending_label
    assert mode.isHidden()  # Normal mode shows nothing, as in vim
    QTest.keyClicks(ed, "i")
    assert mode.text() == "-- INSERT --" and mode.isVisible()
    pump(app)
    assert mode.x() < vim.total_label.x()  # far left, before the total
    esc(ed)
    assert mode.isHidden()
    QTest.keyClicks(ed, "V")
    assert mode.text() == "-- VISUAL LINE --"
    esc(ed)
    QTest.keyClicks(ed, "2d")
    assert pending.text() == "2d" and pending.isVisible()
    pump(app)
    assert vim.statusBar().width() // 2 < pending.x() < vim.rates_label.x()
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
    QTest.keyClick(ed, Qt.Key.Key_F, CTRL)
    assert not bar.isVisible()  # page down, as in vim
    QTest.keyClicks(ed, "ggi")
    QTest.keyClick(ed, Qt.Key.Key_F, CTRL)
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
    QTest.keyClick(ed, Qt.Key.Key_T, CTRL)  # insert total
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
    QTest.keyClicks(ed, "jwxddi")
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
    assert rows["Back to Normal mode"] == "Esc, Ctrl+["
    rows = dict(ShortcutsDialog(vim.menuBar(), vim.t, vim).rows())
    assert "Vim mode" not in rows


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


def test_the_total_stays_put_as_vim_labels_come_and_go(vim, app) -> None:
    ed = vim.editor
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
    QTest.keyClick(widget, Qt.Key.Key_W, CTRL)
    QTest.keyClicks(widget, key)


def test_ctrl_w_moves_between_the_list_the_sheet_and_the_answers(vim, app) -> None:
    ed, tree, results = vim.editor, vim.sidebar.tree, vim.editor.results
    pending = vim.vim_pending_label
    vim.activateWindow()
    QTest.keyClick(ed, Qt.Key.Key_W, CTRL)
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
    QTest.keyClick(tree, Qt.Key.Key_W, CTRL)
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
    QTest.keyClick(ed, Qt.Key.Key_W, CTRL)
    QTest.keyClick(ed, Qt.Key.Key_H, CTRL)
    assert app.focusWidget() is tree
    QTest.keyClick(tree, Qt.Key.Key_W, CTRL)
    QTest.keyClick(tree, Qt.Key.Key_L, CTRL)
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
    store.create_folder("", "Work")
    other = store.create_sheet("Work", "Plans", "1 + 1")
    sidebar.rebuild()
    pump(app)
    ctrl_w(ed, "h")
    tree = sidebar.tree
    folder = tree.findItems("Work", Qt.MatchFlag.MatchRecursive)[0]
    folder.setExpanded(False)
    tree.setCurrentItem(folder)
    QTest.keyClick(tree, Qt.Key.Key_Return)  # Enter opens a folder
    assert folder.isExpanded()
    QTest.keyClicks(tree, "j")
    assert tree.currentItem().text(0) == "Plans"
    QTest.keyClicks(tree, "k")
    assert tree.currentItem() is folder
    QTest.keyClicks(tree, "j")
    QTest.keyClick(tree, Qt.Key.Key_Return)  # Enter opens a sheet and goes to it
    assert vim.current == ("sheet", other)
    assert app.focusWidget() is ed


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


def test_pane_keys_are_off_without_vim_mode(window, app) -> None:
    ed = window.editor
    window.activateWindow()
    ed.setFocus()
    pump(app)
    ed.setPlainText("")
    ctrl_w(ed, "h")
    assert app.focusWidget() is ed
    assert ed.toPlainText() == "h"  # a plain editor types the h
