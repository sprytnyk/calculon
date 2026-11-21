"""Where settings and data files go: config_dir() on new installs, the old places for
users who already have settings there."""

from pathlib import Path
from types import SimpleNamespace

import pytest
from PySide6.QtCore import QSettings, QStandardPaths

from calculon import paths, rates
from calculon.settings import Settings, open_settings, own_words_file


@pytest.fixture
def clean(app):
    paths.old_settings().clear()
    ini = paths.config_dir() / "settings.ini"
    ini.unlink(missing_ok=True)
    yield
    paths.old_settings().clear()
    ini.unlink(missing_ok=True)


def test_new_install_keeps_everything_in_config_dir(clean, home: Path) -> None:
    Settings(sheets_dir=str(home / "sheets")).save()
    folder = paths.config_dir()
    assert Path(open_settings().fileName()) == folder / "settings.ini"
    assert (folder / "settings.ini").is_file()
    assert own_words_file() == folder / "words.txt"
    assert rates.cache_file() == folder / "rates-cache.json"
    assert not paths.uses_old_paths()
    assert Settings.load().sheets_dir == str(home / "sheets")


def test_old_users_keep_their_settings_and_data(clean, home: Path) -> None:
    old = paths.old_settings()
    old.setValue("sheets_dir", str(home / "old sheets"))
    old.sync()
    assert paths.uses_old_paths()
    assert open_settings().format() == QSettings.Format.NativeFormat
    assert Settings.load().sheets_dir == str(home / "old sheets")
    app_data = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
    assert own_words_file() == Path(app_data) / "words.txt"
    assert rates.cache_file() == Path(app_data) / "rates-cache.json"
    assert not (paths.config_dir() / "settings.ini").exists()


@pytest.mark.parametrize(
    ("platform", "env", "base"),
    [
        ("linux", {"XDG_CONFIG_HOME": "xdg"}, "xdg"),
        ("linux", {}, "~/.config"),
        ("darwin", {}, "~/Library/Application Support"),
        ("win32", {"APPDATA": "roaming"}, "roaming"),
        ("win32", {}, "~/AppData/Roaming"),
    ],
)
def test_config_dir_matches_loka(app, monkeypatch, tmp_path, platform, env, base) -> None:
    """Environment values are directories in tmp_path, so they are absolute on every OS."""
    monkeypatch.setattr(paths, "sys", SimpleNamespace(platform=platform))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    monkeypatch.delenv("APPDATA", raising=False)
    for key, value in env.items():
        monkeypatch.setenv(key, str(tmp_path / value))
    expected = Path(base).expanduser() if base.startswith("~") else tmp_path / base
    assert paths.config_dir() == expected / "calculon-tests" / "Calculon"


def test_relative_xdg_config_home_is_ignored(app, monkeypatch) -> None:
    """The XDG spec says to ignore a relative XDG_CONFIG_HOME, so Calculon uses ~/.config."""
    monkeypatch.setattr(paths, "sys", SimpleNamespace(platform="linux"))
    monkeypatch.setenv("XDG_CONFIG_HOME", "relative")
    assert paths.config_dir() == Path.home() / ".config" / "calculon-tests" / "Calculon"
