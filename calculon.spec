# -*- mode: python ; coding: utf-8 -*-
# Build with: uv run pyinstaller calculon.spec --clean --noconfirm
# On macOS, CALCULON_TARGET_ARCH picks x86_64 or arm64 (default: the interpreter's).
import os

icon_file = "assets/icon.ico"
datas = [
    ("assets/icon.ico", "assets"),
    ("assets/icon.png", "assets"),
    ("assets/ICON-LICENSE.txt", "assets"),
    ("assets/rates-fallback.json", "assets"),
    ("assets/fonts/*.ttf", "assets/fonts"),
    ("assets/fonts/OFL.txt", "assets/fonts"),
    ("assets/icons/*.svg", "assets/icons"),
    ("assets/icons/LICENSE.txt", "assets/icons"),
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

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="calculon",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=True,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=True,
    argv_emulation=False,
    target_arch=os.environ.get("CALCULON_TARGET_ARCH") or None,
    codesign_identity=None,
    entitlements_file=None,
    icon=icon_file,
)
