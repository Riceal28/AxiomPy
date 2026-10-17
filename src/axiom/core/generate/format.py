"""Ports of ``Generators/Format.cs``."""

from __future__ import annotations

from ..state import AxiomState
from .context import BuildContext


def force_format(container: str | None) -> str:
    return {
        "webm": "-f webm",
        "mp4": "-f mp4",
        "mkv": "-f matroska",
        "m2v": "-f mpeg2video",
        "mpg": "-f mpeg",
        "avi": "-f avi",
        "ogv": "-f ogv",
        "webp": "-f webp",
        "mp3": "-f mp3",
        "m4a": "",
        "ogg": "-f ogg",
        "flac": "-f flac",
        "wav": "-f wav",
    }.get(container or "", "")


def _pad(value: object, width: int, fill: str = "0") -> str:
    return str("" if value is None else value).rjust(width, fill)


def _frames_to_decimal(ctx: BuildContext, frame: str) -> str:
    frame_rate = ctx.probe_value("inputFrameRate")
    try:
        if "/" not in frame_rate:
            # Axiom indexes Split('/')[1] without checking; a plain "24" throws and
            # the catch block returns the original frame value.
            return frame
        numerator, denominator = frame_rate.split("/", 1)
        rate = float(numerator) / float(denominator)
        rate = int(rate * 1000) / 1000
        return str(float(frame) / rate)
    except (ValueError, ZeroDivisionError):
        return frame


def cut_start(state: AxiomState, ctx: BuildContext) -> str:
    if state.get("Format.Format_Cut_SelectedItem") != "Yes":
        return ""
    frame = state.get("Format.Format_FrameStart_Text")
    if frame is None or str(frame).strip() == "":
        value = (
            _pad(state.get("Format.Format_CutStart_Hours_Text"), 2)
            + ":"
            + _pad(state.get("Format.Format_CutStart_Minutes_Text"), 2)
            + ":"
            + _pad(state.get("Format.Format_CutStart_Seconds_Text"), 2)
            + "."
            + _pad(state.get("Format.Format_CutStart_Milliseconds_Text"), 3)
        )
    else:
        value = _frames_to_decimal(ctx, str(frame))
    return "-ss " + value


def cut_end(state: AxiomState, ctx: BuildContext) -> str:
    if state.get("Format.Format_Cut_SelectedItem") != "Yes":
        return ""
    if state.get("Format.Format_MediaType_SelectedItem") == "Image":
        return ""
    frame = state.get("Format.Format_FrameEnd_Text")
    if frame is None or str(frame).strip() == "":
        value = (
            _pad(state.get("Format.Format_CutEnd_Hours_Text"), 2)
            + ":"
            + _pad(state.get("Format.Format_CutEnd_Minutes_Text"), 2)
            + ":"
            + _pad(state.get("Format.Format_CutEnd_Seconds_Text"), 2)
            + "."
            + _pad(state.get("Format.Format_CutEnd_Milliseconds_Text"), 3)
        )
        if (value == "00:00:00.000" or not value.strip()) and state.get(
            "Main.Input_Text"
        ):
            value = ctx.probe_value("inputDuration") or value
    else:
        value = _frames_to_decimal(ctx, str(frame))
    return "-to " + value
