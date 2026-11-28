"""Windows' spell checker: the COM calls against fake COM objects, and the real one on Windows.

The fakes are Python functions laid out in memory the way COM lays out an object, so
windows_spelling.py runs exactly as it does on Windows, on any system.
"""

import ctypes
import logging
import sys
from collections import Counter
from collections.abc import Callable, Iterator
from concurrent.futures import ThreadPoolExecutor
from ctypes import CFUNCTYPE, POINTER, c_int, c_long, c_void_p, c_wchar_p
from threading import get_ident
from time import monotonic, sleep

import pytest

from calculon import spelling, windows_spelling
from calculon.spelling import SpellChecker, Status
from calculon.storage import SheetStore
from calculon.ui.settings_dialog import SettingsDialog
from calculon.windows_spelling import (
    CHECKER_CHECK,
    CHECKER_SUGGEST,
    CLSID_SPELL_CHECKER_FACTORY,
    ENUM_NEXT,
    FACTORY_CREATE,
    FACTORY_IS_SUPPORTED,
    GUID,
    IID_SPELL_CHECKER_FACTORY,
    OUT,
    RELEASE,
    RPC_E_CHANGED_MODE,
    S_FALSE,
    S_OK,
    ULONG,
)

E_INVALIDARG = -2147024809
REGDB_E_CLASSNOTREG = -2147221164

Method = tuple[tuple[type, ...], Callable[..., int]]


class FakeWindows:
    """Windows' spell checker for a few words, counting what it hands out and gets back."""

    LANGUAGES = ("en-GB", "uk-UA")
    KNOWN = {"rent", "оренда"}
    TYPOS = {"rnet": ["rent", "net"], "оредна": ["оренда"]}

    def __init__(self):
        self.installed = True
        self.alive: dict[int, str] = {}  # objects handed out and not released yet
        self.strings: set[int] = set()  # strings handed out and not freed yet
        self.opened: list[str] = []  # the language of each spell checker made
        # wrong calls, written down because an exception can't leave a callback
        self.mistakes: list[str] = []
        self.com_modes: list[int] = []
        self.com_result = S_FALSE  # default to a thread where Qt has initialized COM
        self.com_counts: Counter[int] = Counter()
        self.com_ended = 0
        self.lifetime_events: list[str] = []
        self._keep: list[object] = []  # the memory behind every fake, kept alive
        # the functions windows_spelling.ole32() would have
        self.CoInitializeEx = self._function(self._start_com, c_long, c_void_p, ULONG)
        self.CoUninitialize = self._function(self._stop_com, None)
        self.CoCreateInstance = self._function(
            self._create, c_long, POINTER(GUID), c_void_p, ULONG, POINTER(GUID), OUT
        )
        self.CoTaskMemFree = self._function(self._free, None, c_void_p)

    def _start_com(self, _reserved, mode: int) -> int:
        self.com_modes.append(mode)
        if self.com_result in (S_OK, S_FALSE):
            self.com_counts[get_ident()] += 1
        return self.com_result

    def _stop_com(self) -> None:
        thread = get_ident()
        if self.com_counts[thread] == 0:
            self.mistakes.append("uninitialized COM without a matching call on this thread")
        self.com_counts[thread] -= 1
        self.com_ended += 1
        self.lifetime_events.append("uninitialize")
        if "factory" in self.alive.values():
            self.mistakes.append("uninitialized COM before releasing the factory")

    def _create(self, clsid, _outer, _context, iid, out) -> int:
        if not self.installed:
            return REGDB_E_CLASSNOTREG
        if bytes(clsid.contents) != bytes(GUID.parse(CLSID_SPELL_CHECKER_FACTORY)):
            self.mistakes.append("wrong CLSID")
        if bytes(iid.contents) != bytes(GUID.parse(IID_SPELL_CHECKER_FACTORY)):
            self.mistakes.append("wrong IID")
        out[0] = self._factory()
        return S_OK

    def _free(self, address: int) -> None:
        if address not in self.strings:
            self.mistakes.append(f"freed {address:#x} twice or never handed it out")
        self.strings.discard(address)

    def _function(self, fn: Callable[..., object], restype, *argtypes):
        f = CFUNCTYPE(restype, *argtypes)(fn)
        self._keep.append(f)
        return f

    def _object(self, name: str, methods: dict[int, Method]) -> int:
        """A COM object: a pointer to a table of functions, the first taking the object."""
        table = (c_void_p * (max(methods, default=RELEASE) + 1))()
        release = self._function(self._release, ULONG, c_void_p)
        table[RELEASE] = ctypes.cast(release, c_void_p).value
        for index, (argtypes, fn) in methods.items():
            f = self._function(fn, c_long, c_void_p, *argtypes)
            table[index] = ctypes.cast(f, c_void_p).value
        box = c_void_p(ctypes.addressof(table))
        self._keep += [table, box]
        self.alive[ctypes.addressof(box)] = name
        return ctypes.addressof(box)

    def _release(self, this: int) -> int:
        name = self.alive.pop(this, None)
        if name is None:
            self.mistakes.append(f"released {this:#x} twice")
        elif name in ("factory", "checker"):
            self.lifetime_events.append(f"release {name}")
        return 0

    def _factory(self) -> int:
        def is_supported(_this, tag: str, yes) -> int:
            yes[0] = tag in self.LANGUAGES
            return S_OK

        def create(_this, tag: str, out) -> int:
            if tag not in self.LANGUAGES:
                return E_INVALIDARG
            self.opened.append(tag)
            out[0] = self._checker()
            return S_OK

        return self._object(
            "factory",
            {
                FACTORY_IS_SUPPORTED: ((c_wchar_p, POINTER(c_int)), is_supported),
                FACTORY_CREATE: ((c_wchar_p, OUT), create),
            },
        )

    def _checker(self) -> int:
        def check(_this, word: str, out) -> int:
            # Windows hands back a list of errors, empty for a word spelled right
            out[0] = self._errors(0 if word in self.KNOWN else 1)
            return S_OK

        def suggest(_this, word: str, out) -> int:
            if word in self.KNOWN:
                out[0] = self._strings([])
                return S_FALSE
            out[0] = self._strings(self.TYPOS.get(word, []))
            return S_OK

        return self._object(
            "checker",
            {
                CHECKER_CHECK: ((c_wchar_p, OUT), check),
                CHECKER_SUGGEST: ((c_wchar_p, OUT), suggest),
            },
        )

    def _errors(self, count: int) -> int:
        left = [count]

        def next_error(_this, out) -> int:
            if not left[0]:
                return S_FALSE
            left[0] -= 1
            out[0] = self._object("error", {})
            return S_OK

        return self._object("errors", {ENUM_NEXT: ((OUT,), next_error)})

    def _strings(self, words: list[str]) -> int:
        left = list(words)

        def next_string(_this, wanted: int, out, fetched) -> int:
            if wanted != 1:
                self.mistakes.append(f"asked for {wanted} strings at once")
            if not left:
                fetched[0] = 0
                return S_FALSE
            text = ctypes.create_unicode_buffer(left.pop(0))
            self._keep.append(text)
            self.strings.add(ctypes.addressof(text))
            out[0] = ctypes.addressof(text)
            fetched[0] = 1
            return S_OK

        return self._object("strings", {ENUM_NEXT: ((ULONG, OUT, POINTER(ULONG)), next_string)})

    def tidy(self) -> bool:
        """Everything handed out came back, and nothing was called wrong."""
        return not (self.alive or self.strings or self.mistakes or any(self.com_counts.values()))


@pytest.fixture
def fake(monkeypatch: pytest.MonkeyPatch) -> FakeWindows:
    fake = FakeWindows()
    monkeypatch.setattr(windows_spelling, "ole32", lambda: fake)
    monkeypatch.setattr(spelling, "platform_key", lambda: "win32")
    return fake


def test_probe_asks_windows_for_each_language(fake: FakeWindows) -> None:
    # the fake has no en-US, so probe() takes the next English it knows
    assert spelling.probe() == Status(
        library=True, dictionaries={"en-GB": "en-GB", "uk-UA": "uk-UA"}
    )
    assert fake.opened == []  # asking which languages exist opens no checker
    assert fake.com_modes and set(fake.com_modes) == {windows_spelling.COINIT_APARTMENTTHREADED}
    assert fake.com_ended == 1
    assert fake.tidy(), (fake.alive, fake.mistakes)


def test_probe_without_windows_spell_checker(fake: FakeWindows) -> None:
    fake.installed = False
    status = spelling.probe()
    assert status == Status(library=False) and not status.available
    assert fake.com_ended == 1


def test_windows_selects_a_supported_english_variant(fake: FakeWindows) -> None:
    fake.LANGUAGES = ("en-AU", "en-GB", "en-US", "en", "uk-UA")
    status = spelling.probe()
    assert status.english == ("en-US", "en-GB", "en-AU", "en")
    assert status.selected() == {"en": "en-US", "uk": "uk-UA"}
    checker = SpellChecker.load(status.selected("en-GB"))
    try:
        assert checker.check("rent") and checker.check("оренда")
        assert fake.opened == ["en-GB", "uk-UA"]
    finally:
        checker.close()
    assert fake.tidy()


def test_windows_checks_and_suggests(fake: FakeWindows) -> None:
    checker = SpellChecker.load(spelling.probe().selected())
    assert checker.languages == ["en", "uk"]
    assert fake.opened == []  # each checker opens on first use, on the thread that checks
    assert checker.check("rent") and checker.check("оренда")
    assert not checker.check("rnet") and not checker.check("оредна")
    assert checker.check("Kyiv")  # Calculon's own words still come first
    assert fake.opened == ["en-GB", "uk-UA"]  # each opened once
    assert checker.suggest("rnet") == ["rent", "net"]
    assert checker.suggest("оредна") == ["оренда"]
    assert checker.suggest("rent") == []  # the fake's S_FALSE means no suggestions
    assert checker.suggest("zzzz") == []
    assert set(fake.alive.values()) == {"checker"}  # every list and error released
    checker.close()
    assert fake.tidy(), (fake.alive, fake.strings, fake.mistakes)


@pytest.mark.parametrize("result", [S_OK, S_FALSE, RPC_E_CHANGED_MODE])
def test_windows_checker_keeps_com_until_close(fake: FakeWindows, result: int) -> None:
    fake.com_result = result
    dictionary = windows_spelling.WindowsDictionary("en-GB")
    dictionary.close()  # construction is lazy
    assert fake.com_modes == []
    assert not dictionary.check("rnet")
    assert dictionary.suggest("rnet") == ["rent", "net"]
    assert fake.lifetime_events == ["release factory"]
    assert fake.com_counts[get_ident()] == int(result != RPC_E_CHANGED_MODE)
    dictionary.close()
    dictionary.close()
    expected = ["release factory", "release checker"]
    if result != RPC_E_CHANGED_MODE:
        expected.append("uninitialize")
    assert fake.lifetime_events == expected
    assert fake.tidy()


@pytest.mark.parametrize("installed", [True, False])
def test_windows_language_that_wont_open_passes_everything(
    fake: FakeWindows, caplog: pytest.LogCaptureFixture, installed: bool
) -> None:
    fake.installed = installed
    dictionary = windows_spelling.WindowsDictionary("de-DE")
    with caplog.at_level(logging.WARNING):
        assert dictionary.check("rnet")
        assert dictionary.suggest("rnet") == []
        assert dictionary.check("Strasse")
    assert len(caplog.records) == 1  # one warning, not one for every word
    assert "de-DE" in caplog.text
    assert fake.lifetime_events == (["release factory"] if installed else []) + ["uninitialize"]
    dictionary.close()
    assert fake.tidy()


def test_windows_checker_cleanup_when_switching_dictionaries_and_closing(
    fake: FakeWindows, window_settings, open_window, app, tmp_path, monkeypatch
) -> None:
    fake.LANGUAGES = ("en-US", "en-GB", "uk-UA")
    window_settings.setValue("spell_check", True)
    SheetStore(tmp_path / "sheets").create_sheet("", "Spelling", "rnet оредна\n")
    window = open_window()

    def wait_for_checker(english: str) -> SpellChecker:
        deadline = monotonic() + 10
        while monotonic() < deadline:
            app.processEvents()
            checker = window.editor.spell
            if checker is not None and checker.sources.get("en") == english:
                return checker
            sleep(0.01)
        pytest.fail(f"spelling checker did not load {english}")

    checker = wait_for_checker("en-US")
    assert not checker.check("rnet") and not checker.check("оредна")
    assert fake.com_counts == Counter({get_ident(): 2})
    monkeypatch.setattr(SettingsDialog, "exec", lambda self: SettingsDialog.DialogCode.Rejected)
    for _ in range(3):
        window.open_settings()
    assert fake.com_counts == Counter({get_ident(): 2})

    def choose_british(dialog):
        menu = dialog.spell_english
        menu.setCurrentIndex(menu.findData("en-GB"))
        return SettingsDialog.DialogCode.Accepted

    monkeypatch.setattr(SettingsDialog, "exec", choose_british)
    window.open_settings()
    checker = wait_for_checker("en-GB")
    assert checker.suggest("rnet") == ["rent", "net"]
    assert not checker.check("оредна")
    assert fake.com_counts == Counter({get_ident(): 2})
    assert window.close()
    assert window.editor.spell is None
    assert fake.tidy()

    late_checker = SpellChecker.load(checker.sources)
    window.spelling_loaded.emit(late_checker)
    assert late_checker.dictionaries == {}
    assert fake.tidy()

    window.show()
    checker = wait_for_checker("en-GB")
    assert checker.suggest("rnet") == ["rent", "net"]
    assert window.close()
    assert fake.tidy()


SYSTEM = spelling.probe() if sys.platform == "win32" else Status(library=False)
on_windows = pytest.mark.skipif(
    "en" in SYSTEM.missing, reason="needs Windows' spell checker with English"
)


@pytest.fixture(scope="module")
def real() -> Iterator[SpellChecker]:
    checker = SpellChecker.load(SYSTEM.selected())
    yield checker
    checker.close()


@on_windows
def test_real_windows_english(real: SpellChecker) -> None:
    for good in ("hotel", "Hotel", "groceries", "receive"):
        assert real.check(good), good
    for bad in ("hotell", "recieve", "airprot"):
        assert not real.check(bad), bad
    assert "hotel" in real.suggest("hotell")
    assert "receive" in real.suggest("recieve")


@on_windows
def test_real_windows_checker_balances_com_on_a_fresh_thread() -> None:
    def check() -> tuple[bool, int]:
        lib = windows_spelling.ole32()
        checker = SpellChecker.load(spelling.probe().selected())
        try:
            misspelled = not checker.check("hotell")
        finally:
            checker.close()
        mode = windows_spelling.COINIT_APARTMENTTHREADED
        result = lib.CoInitializeEx(None, mode)
        if result in (S_OK, S_FALSE):
            lib.CoUninitialize()
        return misspelled, result

    with ThreadPoolExecutor(max_workers=1) as executor:
        assert executor.submit(check).result() == (True, S_OK)


@on_windows
@pytest.mark.skipif("uk" in SYSTEM.missing, reason="needs Ukrainian added in Windows")
def test_real_windows_ukrainian(real: SpellChecker) -> None:
    for good in ("оренда", "Оренда", "Львів", "ґанок", "п'ять", "пʼять", "п’ять"):
        assert real.check(good), good
    for bad in ("оредна", "мобілний"):
        assert not real.check(bad), bad
    assert "оренда" in real.suggest("оредна")


def test_guid_layout_matches_windows() -> None:
    guid = GUID.parse(CLSID_SPELL_CHECKER_FACTORY)  # {7AB36653-1796-484B-BDFA-E74F1DB7C1DC}
    assert ctypes.sizeof(GUID) == 16
    assert (guid.data1, guid.data2, guid.data3) == (0x7AB36653, 0x1796, 0x484B)
    assert bytes(guid.data4) == bytes.fromhex("BDFAE74F1DB7C1DC")
