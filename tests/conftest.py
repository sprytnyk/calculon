"""UI fixtures with an offscreen window and user directories in a temporary directory."""

import os
from pathlib import Path

import pytest
from PySide6.QtCore import QCoreApplication, QEvent, QSettings
from PySide6.QtWidgets import QApplication

from calculon import rates
from calculon.settings import Settings
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
def window_settings(app, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> QSettings:
    monkeypatch.setattr(rates.RatesService, "refresh", lambda self: None)
    qs = QSettings()
    qs.clear()
    qs.setValue("sheets_dir", str(tmp_path / "sheets"))
    qs.setValue("number_date_notice_seen", True)
    return qs


@pytest.fixture
def open_window(window_settings):
    """Start real windows and clean them up after the test."""
    opened: list[MainWindow] = []

    def start(settings: Settings | None = None, *, show: bool = True) -> MainWindow:
        w = MainWindow(settings)
        opened.append(w)
        if show:
            w.show()
        return w

    yield start
    for w in reversed(opened):
        dispose(w)


@pytest.fixture
def window(open_window, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> MainWindow:
    sheets = tmp_path / "sheets"
    sheets.mkdir()
    (sheets / "Sheet.txt").touch()
    w = open_window()
    monkeypatch.setattr(w, "_ask_text", lambda title, default: (default, True))
    return w


def dispose(w: MainWindow) -> None:
    """Close the window and delete it now. Qt only frees it once the event loop runs,
    which tests never reach. Left alive, old windows pile up and slow every new one,
    because each theme change repaints them all."""
    w.close()
    w.deleteLater()
    QCoreApplication.sendPostedEvents(None, QEvent.Type.DeferredDelete)
