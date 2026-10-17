# -*- mode: python ; coding: utf-8 -*-

import os
import shutil
from pathlib import Path


project = Path(SPECPATH).resolve().parent
ffmpeg_env = os.environ.get("AXIOM_FFMPEG_BIN")
ffmpeg_bin = Path(ffmpeg_env).resolve() if ffmpeg_env else None
if ffmpeg_bin is None:
    ffmpeg_exe = shutil.which("ffmpeg")
    ffmpeg_bin = Path(ffmpeg_exe).resolve().parent if ffmpeg_exe else None
theme = project / "src" / "axiom" / "ui" / "theme" / "axiom_dark.qss"
console = os.environ.get("AXIOM_BUILD_CONSOLE") == "1"
app_name = "AxiomPyDebug" if console else "AxiomPy"

if ffmpeg_bin is None:
    raise SystemExit("FFmpeg not found. Set AXIOM_FFMPEG_BIN or add ffmpeg to PATH.")
missing = [name for name in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe") if not (ffmpeg_bin / name).is_file()]
if missing:
    raise SystemExit(f"Missing bundled tools in {ffmpeg_bin}: {', '.join(missing)}")
shims = [
    name
    for name in ("ffmpeg.exe", "ffprobe.exe", "ffplay.exe")
    if (ffmpeg_bin / (name + ".shim")).exists()
    or (ffmpeg_bin / name).stat().st_size < 1024 * 1024
]
if shims:
    raise SystemExit(
        "Refusing to bundle package-manager shims: "
        + ", ".join(shims)
        + f". Set AXIOM_FFMPEG_BIN to the real binaries in {ffmpeg_bin}."
    )

a = Analysis(
    [str(project / "packaging" / "entrypoint.py")],
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
    name=app_name,
    debug=False,
    bootloader_ignore_signals=False,
    strip=False,
    upx=False,
    console=console,
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
    name=app_name,
)
