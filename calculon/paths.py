"""Where things live, both from a checkout and inside a PyInstaller build."""

import os
import sys
from pathlib import Path

from PySide6.QtCore import QCoreApplication, QSettings, QStandardPaths


def bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


ASSETS = bundle_dir() / "assets"
HELP_DIR = bundle_dir() / "calculon" / "help"
APP_ICON = ASSETS / "icon.png"
FONTS = ASSETS / "fonts"
ICONS = ASSETS / "icons"
ARROWS = ASSETS / "arrows"  # made by scripts/make_arrows.py
FALLBACK_RATES = ASSETS / "rates-fallback.json"


def config_dir() -> Path:
    """Calculon's own directory on new installs, the same place Loka uses:
    ~/.config/sprytnyk.dev/Calculon on Linux, ~/Library/Application Support/sprytnyk.dev/Calculon
    on macOS and %AppData%\\sprytnyk.dev\\Calculon on Windows."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA") or Path.home() / "AppData" / "Roaming")
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME", "")
        base = Path(xdg) if os.path.isabs(xdg) else Path.home() / ".config"
    return base / QCoreApplication.organizationName() / QCoreApplication.applicationName()


def old_settings() -> QSettings:
    """Where versions before config_dir() kept settings: ~/.config/sprytnyk.dev/Calculon.conf
    on Linux, a plist on macOS and the registry on Windows. The same call they made, so
    macOS still finds the plist by the organization domain."""
    return QSettings()


def uses_old_paths() -> bool:
    """True for users who already have settings from an older version, so they keep them."""
    qs = old_settings()
    qs.setFallbacksEnabled(False)  # macOS would list global keys too
    return bool(qs.allKeys())


def data_dir() -> Path:
    """Where words.txt and the rates cache go."""
    if uses_old_paths():
        old = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.AppDataLocation)
        return Path(old)
    return config_dir()
