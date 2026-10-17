"""Guards for the frozen portable runtime layout."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from axiom.ui.app import _prepare_runtime


def test_frozen_runtime_exposes_internal_ffmpeg_folder(tmp_path, monkeypatch):
    executable = tmp_path / "AxiomPy.exe"
    internal = tmp_path / "_internal"
    executable.write_bytes(b"exe")
    internal.mkdir()

    monkeypatch.setattr(sys, "frozen", True, raising=False)
    monkeypatch.setattr(sys, "executable", str(executable))
    monkeypatch.setattr(sys, "_MEIPASS", str(internal), raising=False)
    monkeypatch.setenv("PATH", "")
    monkeypatch.delenv("AXIOM_PORTABLE_ROOT", raising=False)

    _prepare_runtime()

    entries = os.environ["PATH"].split(os.pathsep)
    assert str(internal) in entries
    assert str(tmp_path) in entries
    assert os.environ["AXIOM_PORTABLE_ROOT"] == str(tmp_path)


def test_release_workflow_pins_nvenc_compatible_ffmpeg():
    workflow = (
        Path(__file__).parent.parent
        / ".github"
        / "workflows"
        / "release.yml"
    ).read_text(encoding="utf-8")

    assert '$version = "7.1.1"' in workflow
    assert "ffmpeg-$version-essentials_build.zip" in workflow
    assert "04861d3339c5ebe38b56c19a15cf2c0cc97f5de4fa8910e4d47e5e6404e4a2d4" in workflow
    assert "choco install ffmpeg" not in workflow
