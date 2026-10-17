"""Opt-in end-to-end conversion using the generated command."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path

import pytest

from axiom.core.generate import generate
from axiom.core.runner import RunOptions, run
from axiom.core.state import AxiomState


FFMPEG_BIN = Path(os.environ.get("AXIOM_FFMPEG_BIN", r"F:\ffmpeg-8.0.1\bin"))
pytestmark = pytest.mark.skipif(
    os.environ.get("AXIOM_RUN_E2E") != "1" or not (FFMPEG_BIN / "ffmpeg.exe").is_file(),
    reason="set AXIOM_RUN_E2E=1 and AXIOM_FFMPEG_BIN to run conversion tests",
)


def test_generated_single_pass_produces_output(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PATH",
        str(FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", ""),
    )
    source = tmp_path / "clip.mp4"
    subprocess.run(
        [
            str(FFMPEG_BIN / "ffmpeg.exe"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc=size=160x120:rate=15",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=440",
            "-t",
            "1",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            str(source),
            "-y",
        ],
        check=True,
    )

    state = AxiomState(
        {
            "Main.Input_Text": str(source),
            "Format.Format_Container_SelectedItem": "mkv",
            "Format.Format_MediaType_SelectedItem": "Video",
            "Video.Video_Codec_SelectedItem": "x264",
            "Video.Video_Quality_SelectedItem": "Custom",
            "Video.Video_Pass_SelectedItem": "1 Pass",
            "Video.Video_BitRate_Text": "500",
            "Configure.Shell_SelectedItem": "CMD",
        }
    )
    script = generate(state)
    log: list[str] = []
    assert run(script, RunOptions(shell="CMD"), on_log=log.append) == 0, "\n".join(log[-20:])

    output = tmp_path / "clip.mkv"
    assert output.is_file()
    assert output.stat().st_size > 0
