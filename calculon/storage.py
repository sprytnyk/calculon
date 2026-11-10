"""Sheets on disk: one .txt per sheet, folders are real folders.

Pins, custom order and where trashed sheets came from live in a small hidden
file, .calculon.json, in the sheets folder. Trashed sheets go to .trash/.
"""

from __future__ import annotations

import contextlib
import json
import os
import shutil
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

META_FILE = ".calculon.json"
TRASH_DIR = ".trash"
EXT = ".txt"


@dataclass
class Node:
    name: str  # display name (file name without .txt)
    rel: str  # path relative to the sheets folder, with "/" separators
    is_dir: bool
    children: list[Node] = field(default_factory=list)


class StorageError(OSError):
    pass


class SheetStore:
    def __init__(self, root: Path):
        self.root = Path(root)
        self.root.mkdir(parents=True, exist_ok=True)
        self.meta = self._load_meta()

    # --- metadata -------------------------------------------------------------------

    def _load_meta(self) -> dict:
        try:
            data = json.loads((self.root / META_FILE).read_text(encoding="utf-8"))
        except OSError, ValueError:
            data = {}
        if not isinstance(data, dict):
            data = {}
        data.setdefault("pinned", [])
        data.setdefault("order", {})
        data.setdefault("trash", {})
        return data

    def _save_meta(self) -> None:
        _atomic_write(self.root / META_FILE, json.dumps(self.meta, indent=1, ensure_ascii=False))

    # --- paths ----------------------------------------------------------------------

    def path(self, rel: str) -> Path:
        p = (self.root / rel).resolve()
        if p != self.root.resolve() and self.root.resolve() not in p.parents:
            raise StorageError(f"outside the sheets folder: {rel}")
        return p

    def rel(self, path: Path) -> str:
        return path.resolve().relative_to(self.root.resolve()).as_posix()

    @staticmethod
    def display_name(rel: str) -> str:
        name = rel.rsplit("/", 1)[-1]
        return name[: -len(EXT)] if name.endswith(EXT) else name

    # --- listing --------------------------------------------------------------------

    def tree(self) -> Node:
        root = Node("", "", True)
        root.children = self._children("")
        return root

    def _children(self, folder: str) -> list[Node]:
        base = self.path(folder) if folder else self.root
        pinned = set(self.meta["pinned"])
        nodes: dict[str, Node] = {}
        try:
            entries = list(os.scandir(base))
        except OSError:
            return []
        for entry in entries:
            if entry.name.startswith("."):
                continue
            rel = f"{folder}/{entry.name}" if folder else entry.name
            if entry.is_dir(follow_symlinks=False):
                node = Node(entry.name, rel, True)
                node.children = self._children(rel)
                nodes[entry.name] = node
            elif entry.name.endswith(EXT) and rel not in pinned:
                nodes[entry.name] = Node(self.display_name(rel), rel, False)
        order = [n for n in self.meta["order"].get(folder, []) if n in nodes]
        rest = sorted(
            (n for n in nodes if n not in order),
            key=lambda n: (not nodes[n].is_dir, n.lower()),
        )
        return [nodes[n] for n in order + rest]

    def pinned(self) -> list[Node]:
        out = []
        for rel in self.meta["pinned"]:
            if self.path(rel).is_file():
                out.append(Node(self.display_name(rel), rel, False))
        return out

    def all_sheets(self) -> list[str]:
        out = []
        for path in self.root.rglob("*" + EXT):
            rel = self.rel(path)
            if not any(part.startswith(".") for part in rel.split("/")):
                out.append(rel)
        return sorted(out, key=str.lower)

    def search(self, query: str) -> list[str]:
        """Sheets whose name or content contains the query (case-insensitive)."""
        q = query.lower().strip()
        if not q:
            return []
        hits = []
        for rel in self.all_sheets():
            if q in self.display_name(rel).lower():
                hits.append(rel)
                continue
            try:
                if q in self.read(rel).lower():
                    hits.append(rel)
            except OSError:
                continue
        return hits

    # --- sheets ---------------------------------------------------------------------

    def read(self, rel: str) -> str:
        return self.path(rel).read_text(encoding="utf-8")

    def write(self, rel: str, text: str) -> None:
        _atomic_write(self.path(rel), text)

    def mtime(self, rel: str) -> float:
        try:
            return self.path(rel).stat().st_mtime
        except OSError:
            return 0.0

    def create_sheet(self, folder: str = "", name: str = "Untitled", text: str = "") -> str:
        base = self.path(folder) if folder else self.root
        base.mkdir(parents=True, exist_ok=True)
        target = _unique(base, _safe(name), EXT)
        _atomic_write(target, text)
        return self.rel(target)

    def create_folder(self, parent: str = "", name: str = "New folder") -> str:
        base = self.path(parent) if parent else self.root
        target = _unique(base, _safe(name), "")
        target.mkdir(parents=True)
        return self.rel(target)

    def rename(self, rel: str, new_name: str) -> str:
        src = self.path(rel)
        new_name = _safe(new_name)
        if not new_name:
            raise StorageError("name can't be empty")
        dst_name = new_name + (EXT if not src.is_dir() else "")
        dst = src.with_name(dst_name)
        if dst == src:
            return rel
        if dst.exists() and dst.name.lower() != src.name.lower():
            raise StorageError(f"{new_name} already exists")
        src.rename(dst)
        new_rel = self.rel(dst)
        self._replace_refs(rel, new_rel)
        folder = _parent(rel)
        order = self.meta["order"].get(folder)
        if order and src.name in order:
            order[order.index(src.name)] = dst.name
        self._save_meta()
        return new_rel

    def move(self, rel: str, folder: str, index: int | None = None) -> str:
        """Move a sheet or folder into folder, at position index among its siblings."""
        src = self.path(rel)
        dest_dir = self.path(folder) if folder else self.root
        if src.is_dir() and (dest_dir == src or src in dest_dir.parents):
            raise StorageError("can't move a folder into itself")
        old_folder = _parent(rel)
        if dest_dir != src.parent:
            dst = _unique(dest_dir, src.stem if not src.is_dir() else src.name, src.suffix)
            src.rename(dst)
        else:
            dst = src
        new_rel = self.rel(dst)
        self._replace_refs(rel, new_rel)
        old_order = self.meta["order"].get(old_folder, [])
        if src.name in old_order:
            old_order.remove(src.name)
        siblings = [n.rel.rsplit("/", 1)[-1] for n in self._children(folder)]
        siblings = [s for s in siblings if s != dst.name]
        if index is None or index > len(siblings):
            index = len(siblings)
        siblings.insert(index, dst.name)
        self.meta["order"][folder] = siblings
        self._save_meta()
        return new_rel

    def _replace_refs(self, old: str, new: str) -> None:
        def fix(p: str) -> str:
            if p == old:
                return new
            if p.startswith(old + "/"):
                return new + p[len(old) :]
            return p

        self.meta["pinned"] = [fix(p) for p in self.meta["pinned"]]
        self.meta["order"] = {fix(k) if k else k: v for k, v in self.meta["order"].items()}

    # --- pins -----------------------------------------------------------------------

    def is_pinned(self, rel: str) -> bool:
        return rel in self.meta["pinned"]

    def pin(self, rel: str, index: int | None = None) -> None:
        pins = self.meta["pinned"]
        if rel in pins:
            pins.remove(rel)
        pins.insert(len(pins) if index is None else min(index, len(pins)), rel)
        self._save_meta()

    def unpin(self, rel: str) -> None:
        if rel in self.meta["pinned"]:
            self.meta["pinned"].remove(rel)
            self._save_meta()

    # --- trash ----------------------------------------------------------------------

    @property
    def trash_dir(self) -> Path:
        return self.root / TRASH_DIR

    def trash(self, rel: str) -> str:
        src = self.path(rel)
        self.trash_dir.mkdir(exist_ok=True)
        dst = _unique(self.trash_dir, src.stem if src.is_file() else src.name, src.suffix)
        src.rename(dst)
        self.meta["trash"][dst.name] = rel
        self.unpin(rel)
        self.meta["pinned"] = [p for p in self.meta["pinned"] if not p.startswith(rel + "/")]
        self._save_meta()
        return dst.name

    def trashed(self) -> list[tuple[str, str]]:
        """(name in trash, original path) pairs."""
        if not self.trash_dir.is_dir():
            return []
        out = []
        for entry in sorted(self.trash_dir.iterdir(), key=lambda p: p.name.lower()):
            out.append((entry.name, self.meta["trash"].get(entry.name, entry.name)))
        return out

    def read_trashed(self, name: str) -> str:
        return (self.trash_dir / _safe_component(name)).read_text(encoding="utf-8")

    def restore(self, name: str) -> str:
        src = self.trash_dir / _safe_component(name)
        original = self.meta["trash"].pop(name, name)
        folder = _parent(original)
        dest_dir = self.path(folder) if folder else self.root
        dest_dir.mkdir(parents=True, exist_ok=True)
        base = Path(original).name
        stem, suffix = (base[: -len(EXT)], EXT) if base.endswith(EXT) else (base, "")
        dst = _unique(dest_dir, stem, suffix)
        src.rename(dst)
        self._save_meta()
        return self.rel(dst)

    def delete_forever(self, name: str) -> None:
        target = self.trash_dir / _safe_component(name)
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        self.meta["trash"].pop(name, None)
        self._save_meta()

    def empty_trash(self) -> None:
        for name, _ in self.trashed():
            self.delete_forever(name)


def _parent(rel: str) -> str:
    return rel.rsplit("/", 1)[0] if "/" in rel else ""


def _safe(name: str) -> str:
    bad = '<>:"/\\|?*\0'
    cleaned = "".join("-" if c in bad or ord(c) < 32 else c for c in name).strip().strip(".")
    return cleaned[:120]


def _safe_component(name: str) -> str:
    if "/" in name or "\\" in name or name in ("", ".", ".."):
        raise StorageError(f"bad name: {name}")
    return name


def _unique(folder: Path, stem: str, suffix: str) -> Path:
    stem = stem or "Untitled"
    candidate = folder / f"{stem}{suffix}"
    n = 2
    while candidate.exists():
        candidate = folder / f"{stem} {n}{suffix}"
        n += 1
    return candidate


def _atomic_write(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=path.parent, prefix=".tmp-", suffix=path.suffix)
    try:
        with os.fdopen(fd, "w", encoding="utf-8", newline="") as f:
            f.write(text)
        os.replace(tmp, path)
    except BaseException:
        with contextlib.suppress(OSError):
            os.unlink(tmp)
        raise
