# -*- mode: python ; coding: utf-8 -*-
import glob
import os
from PyInstaller.utils.hooks import collect_data_files

# Windows .exe icon (shown in Explorer). Uses the icon at the path below if it
# exists; otherwise the build still succeeds with the default icon.
_ICON = os.path.join("src", "gridlens", "ui", "assets", "app.ico")
icon = _ICON if os.path.exists(_ICON) else None

datas = []
datas += collect_data_files(
    "gridlens", includes=["**/*.qss", "**/*.png", "**/*.svg", "**/*.jpg", "**/*.md"]
)
# Ship every bundled example feeder + the format spec so the app opens with a demo
# network and the user can open any of the provided examples from the frozen exe.
datas += [(f, "data/examples") for f in glob.glob("data/examples/*.json")]
datas += [("data/FORMAT.md", "data")]

a = Analysis(
    ["src/gridlens/__main__.py"],
    pathex=["src"],
    binaries=[],
    datas=datas,
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=["tkinter", "PySide6", "PyQt5"],
    noarchive=False,
)

pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    a.binaries,
    a.datas,
    [],
    name="GridLens",
    icon=icon,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    upx_exclude=[],
    runtime_tmpdir=None,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)
