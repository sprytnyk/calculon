"""UI fixtures with an offscreen window and user directories in a temporary directory."""

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
    qs.setValue("number_date_notice_seen", True)
    qs.sync()
    w = MainWindow()
    monkeypatch.setattr(w, "_ask_text", lambda title, default: (default, True))
    w.show()
    yield w
    dispose(w)


@pytest.fixture
def reopen(app):
    """Open the window again on the saved settings, as starting the app again does.
    Every window it opens is deleted after the test."""
    opened: list[MainWindow] = []

    def open_again() -> MainWindow:
        w = MainWindow()
        w.show()
        opened.append(w)
        return w

    yield open_again
    for w in opened:
        dispose(w)


def dispose(w: MainWindow) -> None:
    """Close the window and delete it now. Qt only frees it once the event loop runs,
    which tests never reach. Left alive, old windows pile up and slow every new one,
    because each theme change repaints them all."""
    w.close()
    w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
