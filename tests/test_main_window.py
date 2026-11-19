"""Main window file actions: outside changes, rename, trash, and the error paths."""

import os
from pathlib import Path

import pytest
from PySide6.QtGui import QDesktopServices, QGuiApplication
from PySide6.QtWidgets import QMessageBox

from calculon.ui.main_window import MainWindow
from calculon.ui.sidebar import HELP, SHEET


@pytest.fixture
def warnings(monkeypatch: pytest.MonkeyPatch) -> list[str]:
    shown: list[str] = []
    monkeypatch.setattr(QMessageBox, "warning", lambda *args: shown.append(str(args[-1])))
    return shown


def answer(monkeypatch: pytest.MonkeyPatch, button: QMessageBox.StandardButton) -> None:
    monkeypatch.setattr(QMessageBox, "question", lambda *args: button)


def write_later(window: MainWindow, rel: str, text: str) -> str:
    """Change a sheet as another program would. The time is set by hand, since some
    file systems keep it to the second or coarser."""
    path = window.store.path(rel)
    path.write_text(text, encoding="utf-8")
    later = window._saved_mtime + 10
    os.utime(path, (later, later))
    return str(path)


def test_outside_change_reloads_a_saved_sheet(window: MainWindow) -> None:
    rel = window.current[1]
    other = window.store.create_sheet("", "Other")
    window._file_changed(str(window.store.path(other)))  # not the open sheet: ignored
    window.editor.setPlainText("1 + 1")
    assert window.save_current()
    path = write_later(window, rel, "2 + 2")
    window._file_changed(path)
    assert window.editor.toPlainText() == "2 + 2"
    assert not window._dirty
    assert window.message_label.text() == window.t("external_change", name="Sheet")
    assert path in window.file_watcher.files()


def test_outside_delete_leaves_the_open_sheet_alone(window: MainWindow) -> None:
    window.editor.setPlainText("1 + 1")
    assert window.save_current()
    window.store.path(window.current[1]).unlink()
    window._file_changed(str(window.store.path(window.current[1])))
    assert window.editor.toPlainText() == "1 + 1"


def test_deleted_open_sheet_moves_on_to_another_or_help(window: MainWindow) -> None:
    other = window.store.create_sheet("", "Other")
    window.store.path(window.current[1]).unlink()
    window._sidebar_changed()
    assert window.current == (SHEET, other)
    window.store.path(other).unlink()
    window._sidebar_changed()
    assert window.current[0] == HELP


def test_rename_open_sheet_and_its_directory(window: MainWindow, monkeypatch) -> None:
    store = window.store
    names = iter(["Budget", "Home"])
    monkeypatch.setattr(window, "_ask_text", lambda title, default: (next(names), True))
    window.rename(window.current[1])
    assert window.current == (SHEET, "Budget.txt")
    assert store.path("Budget.txt").is_file()
    work = store.create_directory("", "Work")
    plans = store.create_sheet(work, "Plans")
    window.open_sheet(plans)
    window.rename(work)
    assert window.current == (SHEET, "Home/Plans.txt")
    assert window._sheet_history[-1] == "Home/Plans.txt"


def test_rename_to_the_same_name_or_failing_changes_nothing(
    window: MainWindow, monkeypatch, warnings: list[str]
) -> None:
    rel = window.current[1]
    window.rename(rel)  # the fixture's prompt answers with the old name
    monkeypatch.setattr(window, "_ask_text", lambda title, default: ("Budget", True))

    def fail(*args):
        raise OSError("disk is read-only")

    monkeypatch.setattr(window.store, "rename", fail)
    window.rename(rel)
    assert window.current == (SHEET, rel)
    assert warnings == ["disk is read-only"]


def test_delete_forever_asks_first(window: MainWindow, monkeypatch) -> None:
    store = window.store
    rel = store.create_sheet("", "Old", "5")
    window.trash(rel)
    name = store.trashed()[0][0]
    window.open_trashed(name)
    answer(monkeypatch, QMessageBox.StandardButton.No)
    window.delete_forever(name)
    assert store.trashed()
    answer(monkeypatch, QMessageBox.StandardButton.Yes)
    window.delete_forever(name)
    assert store.trashed() == []
    assert window.current[0] == HELP


def test_empty_trash_asks_first(window: MainWindow, monkeypatch, warnings: list[str]) -> None:
    store = window.store
    for name in ("Old", "Older"):
        window.trash(store.create_sheet("", name))
    window.open_trashed(store.trashed()[0][0])
    answer(monkeypatch, QMessageBox.StandardButton.No)
    window.empty_trash()
    assert len(store.trashed()) == 2
    answer(monkeypatch, QMessageBox.StandardButton.Yes)
    window.empty_trash()
    assert store.trashed() == []
    assert window.current[0] == HELP
    assert warnings == []


def test_failed_file_actions_show_a_warning(
    window: MainWindow, monkeypatch, warnings: list[str]
) -> None:
    store = window.store
    window.trash(store.create_sheet("", "Old"))
    name = store.trashed()[0][0]

    def fail(*args):
        raise OSError("no space left")

    for method in ("create_sheet", "create_directory", "restore", "delete_forever"):
        monkeypatch.setattr(store, method, fail)
    answer(monkeypatch, QMessageBox.StandardButton.Yes)
    window.new_sheet("")
    window.new_directory("")
    window.restore(name)
    window.delete_forever(name)
    assert warnings == ["no space left"] * 4


def test_new_directory_needs_a_name(window: MainWindow, monkeypatch) -> None:
    monkeypatch.setattr(window, "_ask_text", lambda title, default: ("  ", True))
    window.new_directory("")
    assert [n.name for n in window.store.tree().children if n.is_dir] == []


def test_show_in_directory_opens_the_sheets_directory(window: MainWindow, monkeypatch) -> None:
    opened = []
    monkeypatch.setattr(QDesktopServices, "openUrl", lambda url: opened.append(url.toLocalFile()))
    window.store.create_directory("", "Work")
    window.show_in_directory(window.current[1])
    window.show_in_directory("Work")
    # resolve both sides: macOS links /var to /private/var, Windows has short names like RUNNER~1
    root = window.store.root.resolve()
    assert [Path(p).resolve() for p in opened] == [root, root / "Work"]


def test_copy_with_results(window: MainWindow) -> None:
    window.editor.setPlainText("2 + 2")
    window.editor.recalculate()
    window._copy_with_results()
    assert QGuiApplication.clipboard().text() == window.editor.text_with_results()
    assert "4" in QGuiApplication.clipboard().text()


def test_rates_label_says_when_rates_are_updating_or_failed(window: MainWindow) -> None:
    rates = window.rates
    rates.busy = True
    window._update_rates_label()
    assert window.rates_label.text() == window.t("rates_updating")
    rates.busy = False
    rates.error = "timed out"
    rates.table.updated = 0
    window._update_rates_label()
    assert window.rates_label.text() == window.t(
        "rates_error", error="timed out", when=window.t("rates_never")
    )


def test_results_width_is_saved(window: MainWindow) -> None:
    window._results_resized(321)
    assert window.settings.results_width == 321
