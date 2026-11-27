# -*- mode: python ; coding: utf-8 -*-
# Build with: uv run pyinstaller calculon.spec --clean --noconfirm
# Linux and Windows get dist/calculon/ with its dependencies already unpacked.
# macOS gets dist/Calculon.app. CALCULON_TARGET_ARCH picks x86_64 or arm64 there
# (default: the interpreter's).
import os
import re
import sys
from pathlib import Path

MACOS = sys.platform == "darwin"

icon_file = "assets/icon.icns" if MACOS else "assets/icon.ico"
datas = [
    ("assets/icon.ico", "assets"),
    ("assets/icon.png", "assets"),
    ("assets/ICON-LICENSE.txt", "assets"),
    ("assets/rates-fallback.json", "assets"),
    ("assets/fonts/*.ttf", "assets/fonts"),
    ("assets/fonts/OFL.txt", "assets/fonts"),
    ("assets/icons/*.svg", "assets/icons"),
    ("assets/icons/LICENSE.txt", "assets/icons"),
    ("assets/arrows/*.svg", "assets/arrows"),
    ("calculon/help/*.txt", "calculon/help"),
]

a = Analysis(
    ["calculon/__main__.py"],
    pathex=["."],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter"],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe_options = dict(
    name="calculon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=not MACOS,  # UPX breaks the code signature macOS needs
    upx_exclude=[],
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=os.environ.get("CALCULON_TARGET_ARCH") or None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)

exe = EXE(pyz, a.scripts, [], exclude_binaries=True, **exe_options)
coll = COLLECT(exe, a.binaries, a.datas, strip=False, upx=not MACOS, name="calculon")

if MACOS:
    # macOS wants plain numbers here, so a test build's 0.0.0.dev0+... becomes 0.0.0
    version_file = Path("calculon/_version.py").read_text()
    version = re.search(r'"(\d+(?:\.\d+)*)', version_file).group(1)
    app = BUNDLE(
        coll,
        name="Calculon.app",
        icon=icon_file,
        bundle_identifier="dev.sprytnyk.calculon",
        version=version,
        info_plist={
            "CFBundleVersion": version,
            "LSApplicationCategoryType": "public.app-category.productivity",
        },
    )
