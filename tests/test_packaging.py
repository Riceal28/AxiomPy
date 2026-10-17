"""Guards for the frozen portable runtime layout."""

from __future__ import annotations

import os
import sys

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
