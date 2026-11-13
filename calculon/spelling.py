"""Spell check with the system's Hunspell, for English and Ukrainian words.

Nothing is bundled: Calculon uses the Hunspell library and dictionaries already on the
system, through ctypes.

- Linux: `libhunspell-1.7-0`, `hunspell-en-us` and `hunspell-uk` (Debian/Ubuntu names).
- macOS: `brew install hunspell`, plus .aff/.dic dictionaries in ~/Library/Spelling.
- Windows: not yet.

A word with Cyrillic letters goes to the Ukrainian dictionary, any other word to the
English one. No Qt here: the editor decides which words to check and when.
"""

import codecs
import ctypes
import ctypes.util
import logging
import os
import re
import sys
from collections.abc import Callable, Iterable, Iterator
from dataclasses import dataclass, field
from pathlib import Path

log = logging.getLogger(__name__)

LANGUAGES = ("en", "uk")
# dictionary file names to look for, best first
DICTIONARY_NAMES = {
    "en": ("en_US", "en_GB", "en_CA", "en_AU", "en"),
    "uk": ("uk_UA", "uk"),
}
LIBRARIES = {
    "linux": ("libhunspell-1.7.so.0", "libhunspell-1.7.so", "libhunspell.so"),
    "darwin": (
        "/opt/homebrew/lib/libhunspell-1.7.0.dylib",
        "/opt/homebrew/lib/libhunspell-1.7.dylib",
        "/usr/local/lib/libhunspell-1.7.0.dylib",
        "/usr/local/lib/libhunspell-1.7.dylib",
    ),
}
# Debian/Ubuntu packages, for the install hint
APT_PACKAGES = {"library": "libhunspell-1.7-0", "en": "hunspell-en-us", "uk": "hunspell-uk"}
# words Calculon users write often that the system dictionaries lack
EXTRA_WORDS = frozenset({"Kyiv", "Calculon", "Soulver"})

CYRILLIC = re.compile(r"[Ѐ-ӿ]")
# letters, with apostrophes or hyphens inside: п'ять, пʼять, e-mail
WORD = re.compile(r"[^\W\d_]+(?:['’ʼ\-][^\W\d_]+)*")
# words glued to digits or underscores are names or codes, not prose: x2, total_2
GLUED = re.compile(r"[\d_]")
# URLs, emails and paths are not prose either
NOT_PROSE = re.compile(r"\S+://\S+|\bwww\.\S+|\S+@\S+\.\S+|(?:~|\.{1,2})?/\S+")


def platform_key() -> str:
    return "darwin" if sys.platform == "darwin" else sys.platform


def dictionary_dirs() -> list[Path]:
    dirs = [Path(p) for p in os.environ.get("DICPATH", "").split(os.pathsep) if p]
    home = Path.home()
    if platform_key() == "darwin":
        dirs += [
            home / "Library" / "Spelling",
            Path("/Library/Spelling"),
            Path("/opt/homebrew/share/hunspell"),
            Path("/usr/local/share/hunspell"),
        ]
    else:
        dirs += [
            home / ".local" / "share" / "hunspell",
            Path("/usr/share/hunspell"),
            Path("/usr/share/myspell"),
            Path("/usr/share/myspell/dicts"),
            Path("/usr/local/share/hunspell"),
        ]
    return dirs


def find_dictionary(lang: str, dirs: Iterable[Path] | None = None) -> Path | None:
    """The .aff/.dic pair for `lang`, as a path without the extension."""
    for folder in dictionary_dirs() if dirs is None else dirs:
        for name in DICTIONARY_NAMES[lang]:
            base = folder / name
            if base.with_suffix(".aff").is_file() and base.with_suffix(".dic").is_file():
                return base
    return None


_lib: ctypes.CDLL | None = None
_lib_tried = False


def load_library() -> ctypes.CDLL | None:
    """The Hunspell library, or None if this system doesn't have it."""
    global _lib, _lib_tried
    if _lib_tried:
        return _lib
    _lib_tried = True
    names = list(LIBRARIES.get(platform_key(), ()))
    for short in ("hunspell-1.7", "hunspell"):
        if found := ctypes.util.find_library(short):
            names.append(found)
    for name in names:
        try:
            lib = ctypes.CDLL(name)
        except OSError:
            continue
        _declare(lib)
        _lib = lib
        log.info("spell check: using %s", name)
        return lib
    return None


def _declare(lib: ctypes.CDLL) -> None:
    handle, text = ctypes.c_void_p, ctypes.c_char_p
    words = ctypes.POINTER(ctypes.POINTER(ctypes.c_char_p))
    lib.Hunspell_create.argtypes = [text, text]
    lib.Hunspell_create.restype = handle
    lib.Hunspell_destroy.argtypes = [handle]
    lib.Hunspell_destroy.restype = None
    lib.Hunspell_get_dic_encoding.argtypes = [handle]
    lib.Hunspell_get_dic_encoding.restype = text
    lib.Hunspell_spell.argtypes = [handle, text]
    lib.Hunspell_spell.restype = ctypes.c_int
    lib.Hunspell_suggest.argtypes = [handle, words, text]
    lib.Hunspell_suggest.restype = ctypes.c_int
    lib.Hunspell_free_list.argtypes = [handle, words, ctypes.c_int]
    lib.Hunspell_free_list.restype = None


@dataclass
class Status:
    """What this system has, found without loading any dictionary."""

    supported: bool  # the OS: Linux or macOS
    library: bool
    dictionaries: dict[str, Path] = field(default_factory=dict)

    @property
    def available(self) -> bool:
        return self.supported and self.library and bool(self.dictionaries)

    @property
    def missing(self) -> list[str]:
        return [lang for lang in LANGUAGES if lang not in self.dictionaries]

    def install_command(self) -> str:
        """The apt command that adds what's missing; empty off Linux."""
        if platform_key() != "linux":
            return ""
        names = [] if self.library else [APT_PACKAGES["library"]]
        names += [APT_PACKAGES[lang] for lang in self.missing]
        return f"sudo apt install {' '.join(names)}" if names else ""


def probe() -> Status:
    supported = platform_key() in LIBRARIES
    if not supported:
        return Status(supported=False, library=False)
    dicts = {lang: path for lang in LANGUAGES if (path := find_dictionary(lang))}
    return Status(supported=True, library=load_library() is not None, dictionaries=dicts)


class Dictionary:
    """One Hunspell dictionary. Loading takes a moment (~0.2 s for Ukrainian)."""

    def __init__(self, lib: ctypes.CDLL, base: Path):
        self._lib = lib
        aff, dic = base.with_suffix(".aff"), base.with_suffix(".dic")
        self._handle = lib.Hunspell_create(os.fsencode(aff), os.fsencode(dic))
        if not self._handle:
            raise OSError(f"Hunspell could not load {base}")
        raw = lib.Hunspell_get_dic_encoding(self._handle) or b"UTF-8"
        try:
            self.encoding = codecs.lookup(raw.decode("ascii", "replace")).name
        except LookupError:
            self.encoding = "utf-8"

    def check(self, word: str) -> bool:
        try:
            raw = word.encode(self.encoding)
        except UnicodeEncodeError:
            return True  # letters this dictionary can't even spell: not its business
        return self._lib.Hunspell_spell(self._handle, raw) != 0

    def suggest(self, word: str) -> list[str]:
        try:
            raw = word.encode(self.encoding)
        except UnicodeEncodeError:
            return []
        out = ctypes.POINTER(ctypes.c_char_p)()
        n = self._lib.Hunspell_suggest(self._handle, ctypes.byref(out), raw)
        try:
            return [out[i].decode(self.encoding, "replace") for i in range(n)]
        finally:
            self._lib.Hunspell_free_list(self._handle, ctypes.byref(out), n)

    def close(self) -> None:
        if self._handle:
            self._lib.Hunspell_destroy(self._handle)
            self._handle = None


def language_of(word: str) -> str:
    return "uk" if CYRILLIC.search(word) else "en"


class SpellChecker:
    """English and Ukrainian together, plus the user's own words.

    `own_words` is a text file with one word per line; "Add to Dictionary" appends to it.
    A word in lower case there is fine in any case; one with capitals only as written.
    """

    MAX_CACHE = 50_000

    def __init__(self, own_words: Path | None = None, extra: Iterable[str] = ()):
        self.dictionaries: dict[str, Dictionary] = {}
        self.own_words_file = own_words
        self.own: set[str] = set(EXTRA_WORDS)
        self.known_lower: set[str] = {w.lower() for w in extra}
        self.ignored: set[str] = set()
        self._cache: dict[str, bool] = {}
        if own_words is not None:
            try:
                text = own_words.read_text(encoding="utf-8")
            except OSError:
                text = ""
            self.own |= {w.strip() for w in text.splitlines() if w.strip()}

    @classmethod
    def load(
        cls, status: Status, own_words: Path | None = None, extra: Iterable[str] = ()
    ) -> SpellChecker:
        """Load every dictionary `status` found. Safe to run off the main thread."""
        checker = cls(own_words, extra)
        lib = load_library()
        if lib is None:
            return checker
        for lang, base in status.dictionaries.items():
            try:
                checker.dictionaries[lang] = Dictionary(lib, base)
            except OSError as exc:
                log.warning("spell check: %s", exc)
        return checker

    @property
    def languages(self) -> list[str]:
        return [lang for lang in LANGUAGES if lang in self.dictionaries]

    def check(self, word: str) -> bool:
        """True if the word is fine, or there's no dictionary for its language."""
        hit = self._cache.get(word)
        if hit is not None:
            return hit
        ok = self._check(word)
        if len(self._cache) >= self.MAX_CACHE:
            self._cache.clear()
        self._cache[word] = ok
        return ok

    def _check(self, word: str) -> bool:
        lower = word.lower()
        if word in self.own or lower in self.own or word in self.ignored:
            return True
        if lower in self.known_lower:
            return True
        d = self.dictionaries.get(language_of(word))
        if d is None:
            return True
        if d.check(word):
            return True
        # Hunspell knows п'ять but some dictionaries lack the other apostrophes
        plain = word.replace("’", "'").replace("ʼ", "'")
        return plain != word and d.check(plain)

    def suggest(self, word: str, limit: int = 5) -> list[str]:
        d = self.dictionaries.get(language_of(word))
        return d.suggest(word)[:limit] if d else []

    def add(self, word: str) -> None:
        """Remember `word` for good, in the user's word list."""
        self.own.add(word)
        self._cache.pop(word, None)
        if self.own_words_file is None:
            return
        try:
            self.own_words_file.parent.mkdir(parents=True, exist_ok=True)
            with self.own_words_file.open("a", encoding="utf-8") as f:
                f.write(word + "\n")
        except OSError as exc:
            log.warning("spell check: can't save %r: %s", word, exc)

    def ignore(self, word: str) -> None:
        """Accept `word` until Calculon closes."""
        self.ignored.add(word)
        self._cache.pop(word, None)

    def close(self) -> None:
        for d in self.dictionaries.values():
            d.close()
        self.dictionaries.clear()


def words(text: str) -> Iterator[tuple[int, int, str]]:
    """The prose words in `text` worth checking: (start, end, word).

    Skips single letters, ALL-CAPS (VAT, USD), words glued to digits or underscores,
    and URLs, emails and paths.
    """
    skip = [(m.start(), m.end()) for m in NOT_PROSE.finditer(text)]
    for m in WORD.finditer(text):
        start, end, word = m.start(), m.end(), m.group()
        if len(word) < 2 or (word.isupper() and len(word) > 1):
            continue
        if (start and GLUED.match(text, start - 1)) or (end < len(text) and GLUED.match(text, end)):
            continue  # the regex stopped at a digit or underscore: abc123, x_total
        if any(a <= start < b for a, b in skip):
            continue
        yield start, end, word


def misspelled(
    text: str, check: Callable[[str], bool], skip: Iterable[tuple[int, int]] = ()
) -> list[tuple[int, int]]:
    """Where the misspelled words are in `text`, leaving out the `skip` ranges."""
    skip = list(skip)
    return [
        (start, end)
        for start, end, word in words(text)
        if not any(a <= start < b for a, b in skip) and not check(word)
    ]
