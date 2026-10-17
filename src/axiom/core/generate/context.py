"""Per-run values shared by the argument fragments.

The original generators keep input/output paths, filter accumulators and several
cached fragments in ``MainWindow`` / ``Generate.*`` statics.  A build context gives the
Python port the same lifetime without leaking state between conversions.
"""

from __future__ import annotations

import ntpath
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, List

from ..state import AxiomState
from ..text import wrap_with_quotes
from . import naming


AUDIO_FORMATS = {
    ".wv",
    ".wma",
    ".wav",
    ".vox",
    ".tta",
    ".sln",
    ".rm",
    ".raw",
    ".ra",
    ".opus",
    ".ogg",
    ".oga",
    ".msv",
    ".mpc",
    ".mp3",
    ".mmf",
    ".m4p",
    ".m4b",
    ".m4a",
    ".ivs",
    ".iklax",
    ".gsm",
    ".flac",
    ".dvf",
    ".dss",
    ".dct",
    ".awb",
    ".au",
    ".ape",
    ".amr",
    ".aiff",
    ".act",
    ".aax",
    ".aac",
    ".aa",
    ".8svx",
}

MEDIA_OUTPUT_SUFFIXES = {
    ".aac", ".avi", ".bmp", ".flac", ".gif", ".jpeg", ".jpg", ".m2ts",
    ".m4a", ".m4v", ".mkv", ".mov", ".mp3", ".mp4", ".mpeg", ".mpg",
    ".ogg", ".opus", ".png", ".tif", ".tiff", ".ts", ".wav", ".webm",
    ".webp", ".wmv",
}


def _windows_dir(path: str) -> str:
    directory = ntpath.normpath(ntpath.dirname(path))
    if not directory or directory == ".":
        return ".\\"
    return directory if directory.endswith("\\") else directory + "\\"


def _windows_directory(path: str) -> str:
    """Normalize a directory path and keep exactly one trailing separator."""
    if not path:
        return ""
    stripped = path.rstrip("\\/")
    if not stripped:
        return path
    directory = ntpath.normpath(stripped)
    return directory if directory.endswith("\\") else directory + "\\"


def _windows_output_dir(path: str) -> str:
    """Normalize a configured output directory without doubling separators.

    The UI browse button appends a trailing separator, while hand-edited
    settings often do not.  A path with a file extension is still accepted as
    an output filename for backward compatibility.
    """
    if not path:
        return ""
    stripped = path.rstrip("\\/")
    looks_like_file = (
        ntpath.splitext(stripped)[1].lower() in MEDIA_OUTPUT_SUFFIXES
    )
    if looks_like_file and not os.path.isdir(path):
        return _windows_dir(path)
    return _windows_directory(path)


def _threads(state: AxiomState) -> str:
    selected = state.get("Configure.Threads_SelectedItem")
    threads = state.controls.get("threads")
    maxthreads = state.controls.get("maxthreads") or ""
    if selected == "Default":
        return ""
    if threads:
        return str(threads)
    if selected == "Optimal":
        return "-threads 0"
    if selected == "All":
        return "-threads " + str(maxthreads)
    if selected not in (None, ""):
        return "-threads " + str(selected)
    return ""


def _ffmpeg_path(state: AxiomState) -> str:
    value = state.get("Configure.FFmpegPath_Text") or "<auto>"
    if value == "<auto>":
        return "ffmpeg"
    return wrap_with_quotes(
        value,
        state.get("Configure.Shell_SelectedItem") or "CMD",
        state.get("Configure.ProcessPriority_SelectedItem") or "Default",
    )


def _ffprobe_path(state: AxiomState) -> str:
    value = state.get("Configure.FFprobePath_Text") or "<auto>"
    if value == "<auto>":
        return "ffprobe"
    return wrap_with_quotes(
        value,
        state.get("Configure.Shell_SelectedItem") or "CMD",
        state.get("Configure.ProcessPriority_SelectedItem") or "Default",
    )


def _batch_extension(state: AxiomState) -> str:
    value = str(state.get("Main.BatchExtension_Text") or "")
    if not value.strip() or value == "extension":
        return ""
    return value if value.startswith(".") else "." + value


@dataclass
class BuildContext:
    state: AxiomState
    probe: Dict[str, Any]
    input_dir: str
    input_filename: str
    input_ext: str
    input_path: str
    output_dir: str
    output_filename: str
    output_ext: str
    output_path: str
    threads: str
    ffmpeg: str
    ffprobe: str
    batch_input_directory: str
    v_filters: List[str] = field(default_factory=list)
    v_params: List[str] = field(default_factory=list)
    v_filter: str = ""
    subtitle_paths: List[str] = field(default_factory=list)
    audio_paths: List[str] = field(default_factory=list)

    @property
    def shell(self) -> str:
        return self.state.get("Configure.Shell_SelectedItem") or "CMD"

    @property
    def process_priority(self) -> str:
        return self.state.get("Configure.ProcessPriority_SelectedItem") or "Default"

    @property
    def batch(self) -> bool:
        return bool(self.state.get("Main.Batch_IsChecked"))

    def quote(self, value: str) -> str:
        return wrap_with_quotes(value, self.shell, self.process_priority)

    def probe_value(self, key: str) -> str:
        value = self.probe.get(key)
        return "" if value is None else str(value)


def build_context(state: AxiomState) -> BuildContext:
    input_text = str(state.get("Main.Input_Text") or "")
    batch = bool(state.get("Main.Batch_IsChecked"))
    if batch:
        batch_input_directory = input_text
        input_dir = _windows_directory(input_text) if input_text else ""
        input_ext = _batch_extension(state)
        input_filename = (
            "%f"
            if (state.get("Configure.Shell_SelectedItem") or "CMD") == "CMD"
            else "$inputName"
        )
        input_path = input_dir + input_filename
    else:
        batch_input_directory = ""
        input_dir = _windows_dir(input_text) if input_text else ""
        input_filename = ntpath.splitext(ntpath.basename(input_text))[0]
        input_ext = ntpath.splitext(input_text)[1]
        input_path = input_text

    output_text = str(state.get("Main.Output_Text") or "")
    output_ext = "." + str(state.get("Format.Format_Container_SelectedItem") or "")
    if batch:
        output_dir = (
            _windows_output_dir(output_text) if output_text else input_dir
        )
        output_filename = (
            "%~nf"
            if (state.get("Configure.Shell_SelectedItem") or "CMD") == "CMD"
            else "$outputName"
        )
    elif output_text:
        output_dir = _windows_output_dir(output_text)
        base_name = naming.token_remover(state, input_filename)
        output_filename = naming.file_renamer(
            state,
            input_dir,
            output_dir,
            input_filename,
            input_ext,
            base_name,
            output_ext,
        )
        if naming.selected_tokens(state):
            output_filename = naming.file_renamer(
                state,
                input_dir,
                output_dir,
                input_filename,
                input_ext,
                naming.token_appender(state, input_text, base_name),
                output_ext,
            )
    else:
        output_dir = input_dir
        base_name = naming.token_remover(state, input_filename)
        output_filename = naming.file_renamer(
            state,
            input_dir,
            output_dir,
            input_filename,
            input_ext,
            base_name,
            output_ext,
        )
        if naming.selected_tokens(state):
            output_filename = naming.file_renamer(
                state,
                input_dir,
                output_dir,
                input_filename,
                input_ext,
                naming.token_appender(state, input_text, base_name),
                output_ext,
            )
    if state.get("Format.Format_MediaType_SelectedItem") == "Sequence":
        output_filename = "image-%03d"
    output_filename = naming.output_filename_spacing(state, output_filename)
    output_path = (
        ntpath.join(output_dir, output_filename + output_ext)
        if output_dir
        else output_filename + output_ext
    )

    return BuildContext(
        state=state,
        probe=state.ffprobe,
        input_dir=input_dir,
        input_filename=input_filename,
        input_ext=input_ext,
        input_path=input_path,
        output_dir=output_dir,
        output_filename=output_filename,
        output_ext=output_ext,
        output_path=output_path,
        threads=_threads(state),
        ffmpeg=_ffmpeg_path(state),
        ffprobe=_ffprobe_path(state),
        batch_input_directory=batch_input_directory,
        subtitle_paths=[
            wrap_with_quotes(
                str(path),
                state.get("Configure.Shell_SelectedItem") or "CMD",
                state.get("Configure.ProcessPriority_SelectedItem") or "Default",
            )
            for path in (state.values.get("_subtitle_paths") or [])
        ],
        audio_paths=[
            wrap_with_quotes(
                str(path),
                state.get("Configure.Shell_SelectedItem") or "CMD",
                state.get("Configure.ProcessPriority_SelectedItem") or "Default",
            )
            for path in (state.values.get("_audio_paths") or [])
        ],
    )


def batch_output_path(state: AxiomState, input_path: str | Path) -> str:
    """Return the real output path for one file in the current batch."""
    ctx = build_context(state)
    if state.get("Format.Format_MediaType_SelectedItem") == "Sequence":
        filename = ctx.output_filename
    else:
        filename = ntpath.splitext(ntpath.basename(str(input_path)))[0]
    if ctx.output_dir:
        return ntpath.join(ctx.output_dir, filename + ctx.output_ext)
    return filename + ctx.output_ext


def join_args(*fragments: str | None) -> str:
    """Join fragments the way Axiom's RemoveLineBreaks ultimately leaves them."""
    return " ".join(part for part in fragments if part)
