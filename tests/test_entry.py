"""The command line: --version and --self-test answer without opening a window."""

import sys

import pytest

from calculon import __main__ as entry
from calculon import __version__


def test_version(monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]) -> None:
    monkeypatch.setattr(sys, "argv", ["calculon", "--version"])
    assert entry.main() == 0
    assert capsys.readouterr().out == f"calculon {__version__}\n"


def test_self_test_flag_runs_the_self_test(monkeypatch: pytest.MonkeyPatch) -> None:
    # the real self-test takes over a second; builds run it in CI
    monkeypatch.setattr(sys, "argv", ["calculon", "--self-test"])
    monkeypatch.setattr(entry, "self_test", lambda: 1)
    assert entry.main() == 1


def test_say_without_stdout(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sys, "stdout", None)  # windowed Windows builds
    entry.say("calculon")
