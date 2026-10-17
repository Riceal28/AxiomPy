# -*- mode: python ; coding: utf-8 -*-

import os
from pathlib import Path


project = Path(SPECPATH).resolve().parent
ffmpeg_bin = Path(os.environ.get("AXIOM_FFMPEG_BIN", r"F:\ffmpeg-8.0.1\bin"))
theme = project / "src" / "axiom" / "ui" / "theme" / "axiom_dark.qss"

missing = [name for name in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe") if not (ffmpeg_bin / name).is_file()]
if missing:
    raise SystemExit(f"Missing bundled tools in {ffmpeg_bin}: {', '.join(missing)}")

a = Analysis(
    [str(project / "src" / "axiom" / "ui" / "app.py")],
    pathex=[str(project / "src")],
    binaries=[
        (str(ffmpeg_bin / "ffmpeg.exe"), "."),
        (str(ffmpeg_bin / "ffprobe.exe"), "."),
        (str(ffmpeg_bin / "ffplay.exe"), "."),
    ],
    datas=[(str(theme), "axiom/ui/theme")],
    hiddenimports=[],
    hookspath=[],
    hooksconfig={},
    runtime_hooks=[],
    excludes=[],
    noarchive=False,
)
pyz = PYZ(a.pure)

exe = EXE(
    pyz,
    a.scripts,
    [],
    exclude_binaries=True,
    name="AxiomPy",
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=False,
    disable_windowed_traceback=False,
    argv_emulation=False,
    target_arch=None,
    codesign_identity=None,
    entitlements_file=None,
)

coll = COLLECT(
    exe,
    a.binaries,
    a.datas,
    strip=False,
    upx=False,
    upx_exclude=[],
    name="AxiomPy",
)
