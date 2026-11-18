import errno
import os
import subprocess
from contextlib import contextmanager
from pathlib import Path
from unittest.mock import Mock

import pytest

from calculon import storage
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


@pytest.mark.parametrize("winerror", [5, 32, 33])
def test_write_retries_windows_replace_errors(tmp_path, monkeypatch, winerror) -> None:
    store = SheetStore(tmp_path)
    rel = store.create_sheet(text="1 + 1")
    error = PermissionError(errno.EACCES, "file is busy")
    error.winerror = winerror
    original_replace = os.replace

    def replace(src, dst):
        if replacement.call_count <= 2:
            raise error
        original_replace(src, dst)

    replacement = Mock(side_effect=replace)
    sleep = Mock()
    monkeypatch.setattr(storage.os, "replace", replacement)
    monkeypatch.setattr(storage.time, "sleep", sleep)

    store.write(rel, "2 + 2")

    assert store.read(rel) == "2 + 2"
    assert replacement.call_count == 3
    assert sleep.call_count == 2
    assert not list(tmp_path.glob(".tmp-*"))


@pytest.mark.parametrize("winerror", [None, 5, 32, 33, 123])
def test_failed_write_preserves_file_and_cleans_up(tmp_path, monkeypatch, winerror) -> None:
    store = SheetStore(tmp_path)
    rel = store.create_sheet(text="1 + 1")
    error = PermissionError(errno.EACCES, "access denied")
    if winerror is not None:
        error.winerror = winerror
    replacement = Mock(side_effect=error)
    sleep = Mock()
    monkeypatch.setattr(storage.os, "replace", replacement)
    monkeypatch.setattr(storage.time, "sleep", sleep)

    with pytest.raises(PermissionError) as caught:
        store.write(rel, "2 + 2")

    assert caught.value is error
    assert store.read(rel) == "1 + 1"
    assert not list(tmp_path.glob(".tmp-*"))
    if winerror in (5, 32, 33):
        assert replacement.call_count == 6
        assert sleep.call_count == 5
        assert sum(call.args[0] for call in sleep.call_args_list) <= 0.5
    else:
        replacement.assert_called_once()
        sleep.assert_not_called()


@pytest.mark.skipif(os.name != "nt", reason="Windows file sharing")
def test_write_retries_real_windows_replace_errors(tmp_path, monkeypatch) -> None:
    store = SheetStore(tmp_path)
    rel = store.create_sheet(text="1 + 1")
    original_replace = os.replace

    with store.path(rel).open(encoding="utf-8") as reader:

        def replace(src, dst):
            try:
                original_replace(src, dst)
            except PermissionError:
                reader.close()
                raise

        replacement = Mock(side_effect=replace)
        monkeypatch.setattr(storage.os, "replace", replacement)
        store.write(rel, "2 + 2")

    assert replacement.call_count == 2
    assert store.read(rel) == "2 + 2"
    assert not list(tmp_path.glob(".tmp-*"))


def test_directories_and_tree(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    directory = store.create_directory(name="Work")
    store.create_sheet(directory, "Budget")
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


def test_pinned_sheets_leave_the_directory_list(tmp_path: Path) -> None:
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
    directory = store.create_directory(name="F")
    moved = store.move("A.txt", directory)
    assert moved == "F/A.txt"
    assert names(store.tree().children) == ["F", "C", "B"]
    with pytest.raises(StorageError):
        store.move(directory, directory)


def test_order_survives_reload(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    for n in "ABC":
        store.create_sheet(name=n)
    store.move("C.txt", "", 0)
    assert names(SheetStore(tmp_path).tree().children) == ["C", "A", "B"]


def test_directories_stay_above_sheets(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    store.create_sheet(name="B")
    store.create_sheet(name="A")
    store.move("B.txt", "", 0)
    store.create_directory(name="Work")
    assert names(store.tree().children) == ["Work", "B", "A"]
    store.create_directory(name="Archive")
    store.move("Archive", "", 0)
    assert names(SheetStore(tmp_path).tree().children) == ["Archive", "Work", "B", "A"]


def test_trash_restore_delete(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    directory = store.create_directory(name="F")
    rel = store.create_sheet(directory, "A", "5")
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
    store.create_directory(name="Work")
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
    store.create_directory(name="Work")
    store.create_sheet("Work", "Budget", "groceries")
    (store.root / "directory.txt").mkdir()
    outside = tmp_path / "outside.txt"
    outside.write_text("groceries", encoding="utf-8")
    try:
        (store.root / "linked.txt").symlink_to(outside)
        (store.root / "cycle").symlink_to(store.root, target_is_directory=True)
        (store.root / "broken.txt").symlink_to(tmp_path / "missing.txt")
    except OSError as exc:
        pytest.skip(f"symbolic links unavailable: {exc}")
    assert names(store.tree().children) == ["directory.txt", "Work", "Notes"]
    assert store.all_sheets() == ["Notes.txt", "Work/Budget.txt"]
    assert store.search("groceries") == ["Notes.txt", "Work/Budget.txt"]


def test_search_includes_pins_and_skips_hidden_directories(tmp_path: Path) -> None:
    store = SheetStore(tmp_path)
    store.create_sheet(name="Notes", text="groceries")
    store.pin("Notes.txt")
    store.create_sheet("Work", "Budget", "groceries")
    store.create_sheet(".hidden", "Hidden", "groceries")
    store.create_sheet(".trash", "Trashed", "groceries")
    assert store.all_sheets() == ["Notes.txt", "Work/Budget.txt"]
    assert store.search("groceries") == ["Notes.txt", "Work/Budget.txt"]


@pytest.mark.skipif(os.name == "nt" or os.geteuid() == 0, reason="needs POSIX permissions")
def test_directory_that_cannot_be_written_is_refused(tmp_path: Path) -> None:
    locked = tmp_path / "locked"
    locked.mkdir()
    locked.chmod(0o500)
    try:
        with pytest.raises(PermissionError):
            SheetStore(locked)
    finally:
        locked.chmod(0o700)


def test_write_check_leaves_nothing_behind(tmp_path: Path) -> None:
    SheetStore(tmp_path / "sheets")
    assert list((tmp_path / "sheets").iterdir()) == []


def test_broken_meta_file_is_ignored(tmp_path: Path) -> None:
    (tmp_path / ".calculon.json").write_text("{not json")
    store = SheetStore(tmp_path)
    store.create_sheet(name="A")
    assert names(store.tree().children) == ["A"]
