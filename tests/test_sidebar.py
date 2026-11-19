"""Sidebar tests on a sidebar of its own, without a main window around it."""

from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent
from PySide6.QtWidgets import QMenu

from calculon.storage import SheetStore
from calculon.ui import sidebar as sidebar_module
from calculon.ui.sidebar import (
    DIRECTORY,
    HELP,
    PINNED,
    ROLE,
    SECTION,
    SHEET,
    TRASH,
    TRASHED,
    TRASHED_DIR,
    Sidebar,
)

ON, ABOVE, BELOW = 0, 1, 2  # where a drop lands next to its target


@pytest.fixture
def store(tmp_path: Path) -> SheetStore:
    store = SheetStore(tmp_path / "sheets")
    store.create_directory("", "Work")
    for name in ("Rent", "Food", "Trip"):
        store.create_sheet("", name)
    store.create_sheet("Work", "Plans")
    return store


@pytest.fixture
def sidebar(window_settings, store: SheetStore):
    s = Sidebar(store, lambda key, **kw: key)
    s.rebuild()
    yield s
    s.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)


def rows(sidebar: Sidebar, kind: str, key: str) -> list[str]:
    item = sidebar._find(kind, key)
    assert item is not None
    return [item.child(i).text(0) for i in range(item.childCount())]


def unwatch(sidebar: Sidebar) -> None:
    """Windows can't move or remove a directory while it's watched."""
    sidebar.watcher.removePaths(sidebar.watcher.directories())


def test_drop_on_pinned_section_pins_sheet(sidebar: Sidebar, store: SheetStore) -> None:
    sidebar._dropped((SHEET, "Rent.txt"), (SECTION, PINNED), ON)
    sidebar._dropped((SHEET, "Food.txt"), (PINNED, "Rent.txt"), ABOVE)
    sidebar._dropped((SHEET, "Trip.txt"), (PINNED, "Rent.txt"), BELOW)
    assert store.meta["pinned"] == ["Food.txt", "Rent.txt", "Trip.txt"]
    # moving a pin down past its own old place
    sidebar._dropped((PINNED, "Food.txt"), (PINNED, "Trip.txt"), BELOW)
    assert store.meta["pinned"] == ["Rent.txt", "Trip.txt", "Food.txt"]
    assert rows(sidebar, SECTION, PINNED) == ["Rent", "Trip", "Food"]


def test_drop_pin_on_directory_unpins_and_moves_it(sidebar: Sidebar, store: SheetStore) -> None:
    store.pin("Rent.txt")
    sidebar._dropped((PINNED, "Rent.txt"), (DIRECTORY, "Work"), ON)
    assert store.meta["pinned"] == []
    assert store.path("Work/Rent.txt").is_file()
    sidebar._dropped((SHEET, "Work/Rent.txt"), None, ON)  # on empty space: back to the top
    assert store.path("Rent.txt").is_file()


def test_drop_between_sheets_reorders_them(sidebar: Sidebar, store: SheetStore) -> None:
    store.pin("Trip.txt")
    sidebar._dropped((SHEET, "Rent.txt"), (SHEET, "Food.txt"), ABOVE)
    sidebar._dropped((PINNED, "Trip.txt"), (SHEET, "Food.txt"), BELOW)
    assert store.meta["pinned"] == []
    assert rows(sidebar, SECTION, "") == ["Work", "Rent", "Food", "Trip"]
    sidebar._dropped((SHEET, "Rent.txt"), (SHEET, "Work/Plans.txt"), BELOW)
    assert rows(sidebar, DIRECTORY, "Work") == ["Plans", "Rent"]


def test_drop_on_trash_asks_to_trash(sidebar: Sidebar) -> None:
    trashed: list[str] = []
    sidebar.trash.connect(trashed.append)
    sidebar._dropped((SHEET, "Rent.txt"), (TRASH, ""), ON)
    sidebar._dropped(None, (TRASH, ""), ON)
    assert trashed == ["Rent.txt"]


def test_drop_directory_into_itself_changes_nothing(sidebar: Sidebar, store: SheetStore) -> None:
    store.create_directory("Work", "Old")
    sidebar._dropped((DIRECTORY, "Work"), (DIRECTORY, "Work/Old"), ON)
    assert store.path("Work/Old").is_dir()
    assert rows(sidebar, DIRECTORY, "Work") == ["Old", "Plans"]


def test_search_shows_directory_and_no_results(sidebar: Sidebar) -> None:
    sidebar.search.setText("plans")
    top = sidebar.tree.topLevelItem(0)
    assert top.text(0) == "Plans  ·  Work"
    assert top.data(0, ROLE) == (SHEET, "Work/Plans.txt")
    sidebar.search.setText("nothing like this")
    assert sidebar.tree.topLevelItemCount() == 1
    assert sidebar.tree.topLevelItem(0).text(0) == "no_results"
    assert sidebar.current_directory() == ""


def test_new_items_go_next_to_the_selected_sheet(sidebar: Sidebar) -> None:
    sidebar.tree.setCurrentItem(sidebar._find(SHEET, "Work/Plans.txt"))
    assert sidebar.current_directory() == "Work"
    sidebar.tree.setCurrentItem(sidebar._find(SHEET, "Rent.txt"))
    assert sidebar.current_directory() == ""


def test_keys_rename_and_delete_the_selection(sidebar: Sidebar, store: SheetStore) -> None:
    renamed: list[str] = []
    deleted: list[str] = []
    sidebar.rename.connect(renamed.append)
    sidebar.delete_forever.connect(deleted.append)
    sidebar.tree.setCurrentItem(sidebar._find(SHEET, "Rent.txt"))
    sidebar._rename_action.trigger()
    store.trash("Food.txt")
    sidebar.rebuild()
    sidebar.tree.setCurrentItem(sidebar._find(TRASHED, "Food.txt"))
    sidebar._delete_action.trigger()
    assert renamed == ["Rent.txt"]
    assert deleted == ["Food.txt"]


def test_open_current_opens_help(sidebar: Sidebar) -> None:
    opened: list[bool] = []
    sidebar.open_help.connect(lambda: opened.append(True))
    sidebar.tree.setCurrentItem(sidebar._find(HELP, ""))
    assert sidebar.open_current()
    sidebar.tree.setCurrentItem(None)
    assert not sidebar.open_current()
    assert opened == [True]


def test_neighbor_of_last_directory_is_the_one_before_or_the_parent(
    sidebar: Sidebar, store: SheetStore
) -> None:
    store.create_directory("Work", "Archive")
    store.path("Work/Plans.txt").unlink()
    store.create_directory("Work", "Taxes")
    sidebar.rebuild()
    assert sidebar.directory_neighbor("Work/Taxes") == (DIRECTORY, "Work/Archive")
    unwatch(sidebar)
    store.path("Work/Taxes").rmdir()
    sidebar.rebuild()
    assert sidebar.directory_neighbor("Work/Archive") == (DIRECTORY, "Work")


def test_disk_change_reloads_pins(sidebar: Sidebar, store: SheetStore) -> None:
    changed: list[bool] = []
    sidebar.changed.connect(lambda: changed.append(True))
    other = SheetStore(store.root)  # another window pins a sheet
    other.pin("Rent.txt")
    sidebar._disk_changed()
    assert rows(sidebar, SECTION, PINNED) == ["Rent"]
    assert changed == [True]


@pytest.fixture
def menu_texts(monkeypatch: pytest.MonkeyPatch) -> list[list[str]]:
    """Record each context menu's actions instead of showing it."""
    shown: list[list[str]] = []

    class RecordingMenu(QMenu):
        def exec(self, *args) -> None:  # type: ignore[override]
            shown.append([a.text() for a in self.actions() if a.text()])

    monkeypatch.setattr(sidebar_module, "QMenu", RecordingMenu)
    return shown


def open_menu(sidebar: Sidebar, kind: str, key: str) -> None:
    item = sidebar._find(kind, key)
    assert item is not None
    sidebar._menu(sidebar.tree.visualItemRect(item).center())


def test_context_menus_offer_actions_for_each_row(
    sidebar: Sidebar, store: SheetStore, menu_texts: list[list[str]]
) -> None:
    store.pin("Rent.txt")
    store.trash("Food.txt")
    unwatch(sidebar)
    store.trash("Work")
    sidebar.rebuild()
    sidebar._find(TRASH, "").setExpanded(True)
    open_menu(sidebar, PINNED, "Rent.txt")
    open_menu(sidebar, TRASHED, "Food.txt")
    open_menu(sidebar, TRASHED_DIR, "Work")
    open_menu(sidebar, TRASH, "")
    assert menu_texts == [
        ["new_sheet", "new_directory", "rename", "unpin", "show_in_directory", "move_to_trash"],
        ["restore", "delete_forever"],
        ["restore", "delete_forever"],
        ["empty_trash"],
    ]


def test_pin_and_unpin_from_the_menu_rebuild_the_list(sidebar: Sidebar, store: SheetStore) -> None:
    sidebar._pin("Trip.txt")
    assert rows(sidebar, SECTION, PINNED) == ["Trip"]
    sidebar._unpin("Trip.txt")
    assert sidebar._find(SECTION, PINNED) is None
    assert store.meta["pinned"] == []
