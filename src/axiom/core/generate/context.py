"""Per-run values shared by the argument fragments.

The original generators keep input/output paths, filter accumulators and several
cached fragments in ``MainWindow`` / ``Generate.*`` statics.  A build context gives the
Python port the same lifetime without leaking state between conversions.
"""

from __future__ import annotations

import ntpath
from dataclasses import dataclass, field
from typing import Any, Dict, List

from ..state import AxiomState
from ..text import wrap_with_quotes


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


def _windows_dir(path: str) -> str:
    directory = ntpath.dirname(path)
    return directory.rstrip("\\") + "\\" if directory else ".\\"


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
    v_filters: List[str] = field(default_factory=list)
    v_params: List[str] = field(default_factory=list)
    v_filter: str = ""

    @property
    def shell(self) -> str:
        return self.state.get("Configure.Shell_SelectedItem") or "CMD"

    @property
    def process_priority(self) -> str:
        return self.state.get("Configure.ProcessPriority_SelectedItem") or "Default"

    def quote(self, value: str) -> str:
        return wrap_with_quotes(value, self.shell, self.process_priority)

    def probe_value(self, key: str) -> str:
        value = self.probe.get(key)
        return "" if value is None else str(value)


def build_context(state: AxiomState) -> BuildContext:
    input_text = str(state.get("Main.Input_Text") or "")
    batch = bool(state.get("Main.Batch_IsChecked"))
    if batch:
        input_dir = input_text.rstrip("\\") + "\\"
        input_ext = ntpath.splitext(state.get("Main.BatchExtension_Text") or "")[1]
        input_filename = (
            "%f"
            if (state.get("Configure.Shell_SelectedItem") or "CMD") == "CMD"
            else "$inputName"
        )
        input_path = input_dir + input_filename
    else:
        input_dir = _windows_dir(input_text) if input_text else ""
        input_filename = ntpath.splitext(ntpath.basename(input_text))[0]
        input_ext = ntpath.splitext(input_text)[1]
        input_path = input_text

    output_text = str(state.get("Main.Output_Text") or "")
    output_ext = "." + str(state.get("Format.Format_Container_SelectedItem") or "")
    if output_text:
        output_dir = _windows_dir(output_text)
        output_filename = ntpath.splitext(ntpath.basename(output_text))[0]
    else:
        output_dir = input_dir
        output_filename = input_filename
    if state.get("Format.Format_MediaType_SelectedItem") == "Sequence":
        output_filename = "image-%03d"
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
    )


def join_args(*fragments: str | None) -> str:
    """Join fragments the way Axiom's RemoveLineBreaks ultimately leaves them."""
    return " ".join(part for part in fragments if part)
