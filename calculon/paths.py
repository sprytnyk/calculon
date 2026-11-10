"""Where things live, both from a checkout and inside a PyInstaller build."""

from __future__ import annotations

import sys
from pathlib import Path


def bundle_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent))
    return Path(__file__).resolve().parent.parent


ASSETS = bundle_dir() / "assets"
HELP_DIR = bundle_dir() / "calculon" / "help"
APP_ICON = ASSETS / "icon.png"
FONTS = ASSETS / "fonts"
ICONS = ASSETS / "icons"
FALLBACK_RATES = ASSETS / "rates-fallback.json"
