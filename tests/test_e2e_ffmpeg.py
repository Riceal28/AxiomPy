"""Opt-in end-to-end conversion using the generated command."""

from __future__ import annotations

import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

from axiom.core import controls
from axiom.core.generate import generate_runnable, resolve_controls
from axiom.core.runner import RunOptions, run
from axiom.core.state import AxiomState


_ffmpeg_env = os.environ.get("AXIOM_FFMPEG_BIN")
if _ffmpeg_env:
    FFMPEG_BIN = Path(_ffmpeg_env)
else:
    _ffmpeg = shutil.which("ffmpeg")
    FFMPEG_BIN = Path(_ffmpeg).resolve().parent if _ffmpeg else Path("ffmpeg-not-found")
pytestmark = pytest.mark.skipif(
    os.environ.get("AXIOM_RUN_E2E") != "1" or not (FFMPEG_BIN / "ffmpeg.exe").is_file(),
    reason=(
        "set AXIOM_RUN_E2E=1 and install FFmpeg or set AXIOM_FFMPEG_BIN "
        "to run conversion tests"
    ),
)


def _make_source(path: Path) -> None:
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
            str(path),
            "-y",
        ],
        check=True,
    )


def test_generated_single_pass_produces_output(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PATH",
        str(FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", ""),
    )
    source = tmp_path / "clip.mp4"
    _make_source(source)

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
    script = generate_runnable(state)
    log: list[str] = []
    assert run(script, RunOptions(shell="CMD"), on_log=log.append) == 0, "\n".join(log[-20:])

    output = tmp_path / "clip.mkv"
    assert output.is_file()
    assert output.stat().st_size > 0


def test_external_audio_metadata_reaches_output(tmp_path, monkeypatch):
    monkeypatch.setenv(
        "PATH",
        str(FFMPEG_BIN) + os.pathsep + os.environ.get("PATH", ""),
    )
    source = tmp_path / "muxclip.mp4"
    _make_source(source)
    external = tmp_path / "commentary.m4a"
    subprocess.run(
        [
            str(FFMPEG_BIN / "ffmpeg.exe"),
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "sine=frequency=880",
            "-t",
            "1",
            "-c:a",
            "aac",
            str(external),
            "-y",
        ],
        check=True,
    )

    state = AxiomState(
        {
            "Main.Input_Text": str(source),
            "Format.Format_Container_SelectedItem": "mkv",
            "Format.Format_MediaType_SelectedItem": "Video",
            "Configure.Shell_SelectedItem": "CMD",
        }
    )
    resolve_controls(state)
    state.set("Video.Video_Quality_SelectedItem", "Custom")
    state.set("Video.Video_Pass_SelectedItem", "1 Pass")
    state.set("Video.Video_BitRate_Text", "500K")
    state.set("Audio.Audio_Codec_SelectedItem", "Copy")
    controls.audio_codec_controls(state, "Copy")
    state.set("Audio.Audio_Stream_SelectedItem", "mux")
    state.set("_audio_paths", [str(external)])
    state.set(
        "_audio_metadata",
        [{"title": "Commentary", "language": "English", "delay": ""}],
    )

    log: list[str] = []
    assert run(
        generate_runnable(state),
        RunOptions(shell="CMD"),
        on_log=log.append,
    ) == 0, "\n".join(log[-20:])
    output = tmp_path / "muxclip.mkv"
    probe = subprocess.run(
        [
            str(FFMPEG_BIN / "ffprobe.exe"),
            "-v",
            "error",
            "-select_streams",
            "a:0",
            "-show_entries",
            "stream_tags=title,language",
            "-of",
            "json",
            str(output),
        ],
        capture_output=True,
        text=True,
        check=True,
    )
    tags = json.loads(probe.stdout)["streams"][0]["tags"]
    assert tags["title"] == "Commentary"
    assert tags["language"] == "en"
