"""Fixtures for the UI tests: the real window, offscreen, with every user folder in a temp dir."""

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication

from calculon import rates
from calculon.ui.main_window import MainWindow


@pytest.fixture(scope="module")
def home(tmp_path_factory: pytest.TempPathFactory) -> Path:
    h = tmp_path_factory.mktemp("home")
    os.environ.update(
        HOME=str(h),
        XDG_CONFIG_HOME=str(h / ".config"),
        XDG_DATA_HOME=str(h / ".local" / "share"),
        XDG_CACHE_HOME=str(h / ".cache"),
        QT_QPA_PLATFORM="offscreen",
    )
    return h


@pytest.fixture(scope="module")
def app(home: Path):
    QCoreApplication.setOrganizationName("calculon-tests")
    QCoreApplication.setApplicationName("Calculon")
    return QApplication.instance() or QApplication([])


@pytest.fixture
def window(app, home: Path, monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    monkeypatch.setattr(rates.RatesService, "refresh", lambda self: None)
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(tmp_path / "sheets"))
    qs.sync()
    w = MainWindow()
    w.show()
    yield w
    w.close()
    w.deleteLater()
    # Qt only frees it once the event loop runs, which tests never reach. Left alive,
    # old windows pile up and slow every new one: the theme repaints them all.
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
