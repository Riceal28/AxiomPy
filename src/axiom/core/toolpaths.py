"""Resolve the FFmpeg-family executables used by the UI and runner."""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path


def resolve_tool_path(value: str | None, tool: str) -> Path | None:
    """Resolve an explicit path or the ``<auto>`` convention.

    ``<auto>`` checks the configured development directory, the PyInstaller
    runtime directory, and finally ``PATH``.  The returned path is what the
    Settings page displays below an automatic tool field.
    """

    text = str(value or "").strip()
    if text and text != "<auto>":
        return Path(text).expanduser()

    names = [tool + ".exe", tool]
    roots: list[Path] = []
    configured = os.environ.get("AXIOM_FFMPEG_BIN")
    if configured:
        roots.append(Path(configured))

    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            roots.append(Path(meipass))
        executable_dir = Path(sys.executable).resolve().parent
        roots.extend((executable_dir, executable_dir / "_internal"))

    for root in roots:
        for name in names:
            candidate = root / name
            if candidate.is_file():
                return candidate.resolve()

    for name in names:
        found = shutil.which(name)
        if found:
            return Path(found).resolve()
    return None
