import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest

from calculon.storage import SheetStore, StorageError


def names(nodes):
    return [n.name for n in nodes]


def test_create_read_write(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    rel = store.create_sheet(text="1 + 1")
    assert rel == "Untitled.txt"
    assert store.read(rel) == "1 + 1"
    assert store.create_sheet() == "Untitled 2.txt"
    store.write(rel, "2 + 2")
    assert (tmp_path / "Untitled.txt").read_text() == "2 + 2"


def test_folders_and_tree(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    folder = store.create_folder(name="Work")
    store.create_sheet(folder, "Budget")
    store.create_sheet(name="Groceries")
    tree = store.tree()
    assert names(tree.children) == ["Work", "Groceries"]
    assert names(tree.children[0].children) == ["Budget"]


def test_rename_keeps_pin(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    rel = store.create_sheet(name="A")
    store.pin(rel)
    new = store.rename(rel, "B")
    assert new == "B.txt"
    assert store.is_pinned("B.txt")
    with pytest.raises(StorageError):
        store.rename(new, "")


def test_pinned_sheets_leave_the_folder_list(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    store.create_sheet(name="A")
    store.create_sheet(name="B")
    store.pin("B.txt")
    assert names(store.tree().children) == ["A"]
    assert names(store.pinned()) == ["B"]
    store.unpin("B.txt")
    assert names(store.tree().children) == ["A", "B"]


def test_reorder_and_move(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    for n in "ABC":
        store.create_sheet(name=n)
    store.move("C.txt", "", 0)
    assert names(store.tree().children) == ["C", "A", "B"]
    folder = store.create_folder(name="F")
    moved = store.move("A.txt", folder)
    assert moved == "F/A.txt"
    assert names(store.tree().children) == ["C", "B", "F"]
    with pytest.raises(StorageError):
        store.move(folder, folder)


def test_order_survives_reload(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    for n in "ABC":
        store.create_sheet(name=n)
    store.move("C.txt", "", 0)
    assert names(SheetStore(tmp_path).tree().children) == ["C", "A", "B"]


def test_trash_restore_delete(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    folder = store.create_folder(name="F")
    rel = store.create_sheet(folder, "A", "5")
    store.pin(rel)
    name = store.trash(rel)
    assert not store.is_pinned(rel)
    assert store.trashed() == [(name, "F/A.txt")]
    assert store.read_trashed(name) == "5"
    assert store.restore(name) == "F/A.txt"
    name = store.trash("F/A.txt")
    store.delete_forever(name)
    assert store.trashed() == []


def test_search(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    store.create_sheet(name="Holiday", text="flights $400")
    store.create_sheet(name="Rent", text="$900")
    assert store.search("holi") == ["Holiday.txt"]
    assert store.search("FLIGHTS") == ["Holiday.txt"]
    assert store.search("") == []


def test_paths_cannot_escape(tmp_path: Path) -> None:
    store = SheetStore(tmp_path / "s")
    with pytest.raises(StorageError):
        store.read("../outside.txt")


def test_scans_skip_junctions_and_unreadable_entries(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    store = SheetStore(tmp_path)
    store.create_sheet(name="Notes", text="groceries")
    junction = Mock()
    junction.name = "My Music"
    junction.is_symlink.return_value = False
    junction.is_junction.return_value = True
    junction.is_dir.return_value = True
    unreadable = Mock()
    unreadable.name = "Unreadable"
    unreadable.is_symlink.return_value = False
    unreadable.is_junction.return_value = False
    unreadable.is_dir.side_effect = PermissionError("access denied")
    scandir = os.scandir

    @contextmanager
    def scan(path):
        with scandir(path) as entries:
            items = list(entries)
        if Path(path) == tmp_path:
            items.extend([junction, unreadable])
        yield iter(items)

    monkeypatch.setattr(os, "scandir", scan)
    assert names(store.tree().children) == ["Notes"]
    assert store.all_sheets() == ["Notes.txt"]
    assert store.search("groceries") == ["Notes.txt"]
    junction.is_dir.assert_not_called()
    unreadable.is_dir.assert_called()


@pytest.mark.skipif(os.name != "nt", reason="Windows directory junctions")
@pytest.mark.parametrize("target_kind", ["outside", "inside", "cycle", "broken"])
def test_windows_junctions(tmp_path: Path, target_kind: str) -> None:
    store = SheetStore(tmp_path / "Documents")
    store.create_sheet(name="Notes", text="groceries")
    store.create_folder(name="Work")
    store.create_sheet("Work", "Budget", "groceries")
    target = tmp_path / "Music"
    target.mkdir()
    if target_kind == "inside":
        target = store.root / "Work"
    elif target_kind == "cycle":
        target = store.root
    junction = store.root / "My Music"
    subprocess.run(
        ["cmd", "/c", "mklink", "/J", str(junction), str(target)],
        check=True,
        capture_output=True,
    )
    assert junction.is_junction()
    if target_kind == "broken":
        target.rmdir()
    assert names(store.tree().children) == ["Work", "Notes"]
    assert store.all_sheets() == ["Notes.txt", "Work/Budget.txt"]
    assert store.search("groceries") == ["Notes.txt", "Work/Budget.txt"]
    if target_kind == "outside":
        with pytest.raises(StorageError):
            store.path("My Music")


def test_scans_skip_symbolic_links(tmp_path: Path) -> None:
    store = SheetStore(tmp_path / "sheets")
    store.create_sheet(name="Notes", text="groceries")
    store.create_folder(name="Work")
    store.create_sheet("Work", "Budget", "groceries")
    (store.root / "folder.txt").mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("groceries", encoding="utf-8")
    try:
        (store.root / "linked.txt").symlink_to(outside)
        (store.root / "cycle").symlink_to(store.root, target_is_directory=True)
        (store.root / "broken.txt").symlink_to(tmp_path / "missing.txt")
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {exc}")
    assert names(store.tree().children) == ["folder.txt", "Work", "Notes"]
    assert store.all_sheets() == ["Notes.txt", "Work/Budget.txt"]
    assert store.search("groceries") == ["Notes.txt", "Work/Budget.txt"]


def test_search_includes_pins_and_skips_hidden_folders(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    store.create_sheet(name="Notes", text="groceries")
    store.pin("Notes.txt")
    store.create_sheet("Work", "Budget", "groceries")
    store.create_sheet(".hidden", "Hidden", "groceries")
    store.create_sheet(".trash", "Trashed", "groceries")
    assert store.all_sheets() == ["Notes.txt", "Work/Budget.txt"]
    assert store.search("groceries") == ["Notes.txt", "Work/Budget.txt"]


def test_broken_meta_file_is_ignored(tmp_path: Path) -> None:
    (tmp_path / ".calculon.json").write_text("{not json")
    store = SheetStore(tmp_path)
    store.create_sheet(name="A")
    assert names(store.tree().children) == ["A"]
