# -*- mode: python ; coding: utf-8 -*-
# PyInstaller spec for SnipText (Windows onedir)
# Build: py -3 -m PyInstaller --noconfirm SnipText.spec

import sys
from pathlib import Path

from PyInstaller.utils.hooks import collect_all, collect_data_files, collect_dynamic_libs

ROOT = Path(SPECPATH).resolve()

datas = [
    (str(ROOT / "assets" / "icon.ico"), "assets"),
    (str(ROOT / "assets" / "icon.png"), "assets"),
    (str(ROOT / "assets" / "shutter.wav"), "assets"),
    (str(ROOT / "config.example.json"), "."),
]
binaries = []
hiddenimports = [
    "sniptext",
    "sniptext.app",
    "pynput.keyboard._win32",
    "pynput.mouse._win32",
    "pystray._win32",
    "PIL._tkinter_finder",
    "keyring.backends",
    "keyring.backends.Windows",
    "pkg_resources.py2_warn",
]

# Bundle local OCR stack when present
for pkg in ("rapidocr_onnxruntime", "onnxruntime", "cv2", "numpy"):
    try:
        d, b, h = collect_all(pkg)
        datas += d
        binaries += b
        hiddenimports += h
    except Exception as exc:
        print(f"[SnipText.spec] skip collect_all({pkg}): {exc}")

try:
    datas += collect_data_files("rapidocr_onnxruntime")
except Exception:
    pass
try:
    binaries += collect_dynamic_libs("onnxruntime")
except Exception:
    pass

a = Analysis(
    [str(ROOT / "sniptext" / "__main__.py")],
    pathex=[str(ROOT)],
    binaries=binaries,
    datas=datas,
    hiddenimports=hiddenimports,
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[
        "matplotlib",
        "scipy",
        "pandas",
        "torch",
        "tensorflow",
        "paddle",
        "paddleocr",
        "easyocr",
    ],
    noarchive=False,
    optimize=0,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="SnipText",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    icon=str(ROOT / "assets" / "icon.ico") if (ROOT / "assets" / "icon.ico").is_file() else None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="SnipText",
)
