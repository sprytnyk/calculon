"""Windows' own spell checker, through ctypes. Windows has had it since Windows 8.

The spell checker is a COM object, which is a pointer to a table of functions. Each call
below names a function by its place in that table, in the order the Windows SDK's
spellcheck.h declares them. The Windows dictionary for a language comes with the
language, added in Settings > Time & language > Language & region.
"""

import ctypes
import functools
import logging
import sys
import uuid
from collections.abc import Iterable, Iterator
from contextlib import ExitStack, contextmanager
from ctypes import POINTER, byref, c_int, c_long, c_void_p, c_wchar_p

log = logging.getLogger(__name__)

S_OK, S_FALSE = 0, 1
RPC_E_CHANGED_MODE = -2147417850  # 0x80010106, COM is already on as multi-threaded
COINIT_APARTMENTTHREADED = 0x2  # the mode Qt's UI thread uses
CLSCTX_INPROC_SERVER = 0x1

CLSID_SPELL_CHECKER_FACTORY = "7AB36653-1796-484B-BDFA-E74F1DB7C1DC"
IID_SPELL_CHECKER_FACTORY = "8E018A9D-2415-4677-BF08-794EA61F94BB"

# places in the function tables; every table starts with QueryInterface, AddRef, Release
RELEASE = 2
FACTORY_IS_SUPPORTED, FACTORY_CREATE = 4, 5  # ISpellCheckerFactory
CHECKER_CHECK, CHECKER_SUGGEST = 4, 5  # ISpellChecker
ENUM_NEXT = 3  # IEnumSpellingError and IEnumString

# 64-bit Windows has one calling convention, so CFUNCTYPE is the same thing there. It
# lets the tests run this code against fake COM objects on Linux and macOS.
FUNCTYPE = getattr(ctypes, "WINFUNCTYPE", ctypes.CFUNCTYPE)
OUT = POINTER(c_void_p)
ULONG = ctypes.c_uint32  # also DWORD; it's 32 bits, while c_ulong is 64 off Windows


class GUID(ctypes.Structure):
    _fields_ = [
        ("data1", ULONG),
        ("data2", ctypes.c_uint16),
        ("data3", ctypes.c_uint16),
        ("data4", ctypes.c_ubyte * 8),
    ]

    @classmethod
    def parse(cls, text: str) -> GUID:
        return cls.from_buffer_copy(uuid.UUID(text).bytes_le)


@functools.cache
def ole32():
    """Windows' COM library."""
    if sys.platform != "win32":
        raise OSError("Windows only")
    lib = ctypes.WinDLL("ole32")
    lib.CoInitializeEx.argtypes = [c_void_p, ULONG]
    lib.CoInitializeEx.restype = c_long
    lib.CoUninitialize.argtypes = []
    lib.CoUninitialize.restype = None
    lib.CoCreateInstance.argtypes = [POINTER(GUID), c_void_p, ULONG, POINTER(GUID), OUT]
    lib.CoCreateInstance.restype = c_long
    lib.CoTaskMemFree.argtypes = [c_void_p]
    lib.CoTaskMemFree.restype = None
    return lib


class Com:
    """A COM object we hold a reference to."""

    def __init__(self, address: int):
        self.address = address

    def call(self, index: int, argtypes: tuple[type, ...], *args: object) -> int:
        """Call function `index` of the object's table; returns its HRESULT."""
        table = ctypes.cast(self.address, POINTER(POINTER(c_void_p))).contents
        function = FUNCTYPE(c_long, c_void_p, *argtypes)(table[index])
        return function(self.address, *args)

    def release(self) -> None:
        if self.address:
            self.call(RELEASE, ())
            self.address = 0


def _initialize_com(cleanup: ExitStack):
    lib = ole32()
    hr = lib.CoInitializeEx(None, COINIT_APARTMENTTHREADED)
    if hr not in (S_OK, S_FALSE, RPC_E_CHANGED_MODE):
        raise OSError(f"COM didn't start: {hr & 0xFFFFFFFF:#010x}")
    if hr != RPC_E_CHANGED_MODE:
        cleanup.callback(lib.CoUninitialize)
    return lib


@contextmanager
def _factory(lib) -> Iterator[Com]:
    """Windows' spell checker factory, for this thread."""
    out = c_void_p()
    clsid, iid = GUID.parse(CLSID_SPELL_CHECKER_FACTORY), GUID.parse(IID_SPELL_CHECKER_FACTORY)
    hr = lib.CoCreateInstance(byref(clsid), None, CLSCTX_INPROC_SERVER, byref(iid), byref(out))
    if hr != S_OK or not out.value:
        raise OSError(f"no Windows spell checker: {hr & 0xFFFFFFFF:#010x}")
    factory = Com(out.value)
    try:
        yield factory
    finally:
        factory.release()


def supported_tags(tags: Iterable[str]) -> list[str]:
    """Return the language tags Windows can check, in the requested order.

    Raise OSError if Windows has no spell checker.
    """
    with ExitStack() as cleanup, _factory(_initialize_com(cleanup)) as factory:
        supported = []
        for tag in tags:
            yes = c_int()
            hr = factory.call(FACTORY_IS_SUPPORTED, (c_wchar_p, POINTER(c_int)), tag, byref(yes))
            if hr == S_OK and yes.value:
                supported.append(tag)
        return supported


def _create_checker(tag: str) -> tuple[Com, ExitStack]:
    with ExitStack() as cleanup:
        with _factory(_initialize_com(cleanup)) as factory:
            out = c_void_p()
            hr = factory.call(FACTORY_CREATE, (c_wchar_p, OUT), tag, byref(out))
            if hr != S_OK or not out.value:
                raise OSError(f"{hr & 0xFFFFFFFF:#010x}")
            checker = Com(out.value)
            cleanup.callback(checker.release)
        return checker, cleanup.pop_all()


class WindowsDictionary:
    """Windows' spell checker for one language tag, such as en-US.

    Calculon can construct this on a worker. The first check opens the COM object, and
    the same thread must close it. For the editor, that's the UI thread.
    """

    def __init__(self, tag: str):
        self.tag = tag
        self._checker: Com | None = None
        self._cleanup = ExitStack()
        self._failed = False

    def _open(self) -> Com | None:
        """The checker, or None if it won't open. Then every word passes, as for a
        language with no dictionary."""
        if self._checker is None and not self._failed:
            try:
                self._checker, self._cleanup = _create_checker(self.tag)
            except OSError as exc:
                self._failed = True
                log.warning("spell check: Windows can't check %s: %s", self.tag, exc)
        return self._checker

    def check(self, word: str) -> bool:
        checker = self._open()
        if checker is None:
            return True
        out = c_void_p()
        if checker.call(CHECKER_CHECK, (c_wchar_p, OUT), word, byref(out)) != S_OK:
            return True
        errors = Com(out.value or 0)
        if not errors.address:
            return True
        try:
            # the first error is enough to call the word misspelled
            error = c_void_p()
            wrong = errors.call(ENUM_NEXT, (OUT,), byref(error)) == S_OK
            Com(error.value or 0).release()
            return not wrong
        finally:
            errors.release()

    def suggest(self, word: str) -> list[str]:
        checker = self._open()
        if checker is None:
            return []
        out = c_void_p()
        hr = checker.call(CHECKER_SUGGEST, (c_wchar_p, OUT), word, byref(out))
        strings = Com(out.value or 0)
        try:
            # S_FALSE means the word is spelled right
            if hr != S_OK or not strings.address:
                return []
            suggestions: list[str] = []
            next_types = (ULONG, OUT, POINTER(ULONG))
            while True:
                text, fetched = c_void_p(), ULONG()
                if strings.call(ENUM_NEXT, next_types, 1, byref(text), byref(fetched)) != S_OK:
                    break
                if fetched.value and text.value:
                    suggestions.append(ctypes.wstring_at(text.value))
                    ole32().CoTaskMemFree(text.value)
            return suggestions
        finally:
            strings.release()

    def close(self) -> None:
        self._checker = None
        self._cleanup.close()
