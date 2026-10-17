"""Ports of ``Generators/Streams.cs``."""

from __future__ import annotations

from ..state import AxiomState
from .context import AUDIO_FORMATS, BuildContext


def _is_audio_input(ctx: BuildContext) -> bool:
    # Faithful to Axiom: ``AudioFormats`` holds names without a dot, while
    # ``MainWindow.inputExt`` includes one, so this comparison is normally false.
    extension = ctx.input_ext.lower()
    return extension in {value.lstrip(".") for value in AUDIO_FORMATS}


def format_maps(state: AxiomState, ctx: BuildContext) -> str:
    container = state.get("Format.Format_Container_SelectedItem")
    audio_stream = state.get("Audio.Audio_Stream_SelectedItem")
    subtitle_stream = state.get("Subtitle.Subtitle_Stream_SelectedItem")

    if container in ("webm", "m2v", "jpg", "png", "webp"):
        return ""
    if container == "mp3":
        return "-map_metadata 0 -id3v2_version 3"
    if container in ("m4a", "ogg", "flac", "wav"):
        return "-map_metadata 0"

    if audio_stream != "mux" and subtitle_stream not in ("mux", "external"):
        return "-map_metadata 0"
    if audio_stream == "mux" and subtitle_stream != "mux":
        return "-map_metadata:s:v 0 -map_metadata:s:s 0"
    if subtitle_stream == "mux" and audio_stream != "mux":
        return "-map_metadata:s:v 0 -map_metadata:s:a 0"
    if subtitle_stream == "mux" and audio_stream == "mux":
        return "-map_metadata:s:v 0"
    return ""


def video_stream_maps(state: AxiomState, ctx: BuildContext) -> str:
    container = state.get("Format.Format_Container_SelectedItem")
    mapping = {
        "webm": "-map 0:v:0?",
        "mp4": "-map 0:v:0?",
        "mkv": "-map 0:v?",
        "m2v": "-map 0:v?",
        "mpg": "-map 0:v?",
        "avi": "-map 0:v:0?",
        "ogv": "-map 0:v?",
    }.get(container, "")
    if state.get("Video.Video_Codec_SelectedItem") == "None":
        mapping = "-vn"
    if _is_audio_input(ctx):
        mapping = ""
    return mapping


def audio_stream_maps(state: AxiomState, ctx: BuildContext) -> str:
    stream = state.get("Audio.Audio_Stream_SelectedItem")
    container = state.get("Format.Format_Container_SelectedItem")
    if stream == "none":
        mapping = "-an"
    elif stream == "mux":
        mapping = ""
    elif stream == "all":
        mapping = {
            "webm": "-map 0:a:0?",
            "mp4": "-map 0:a?",
            "mkv": "-map 0:a?",
            "m2v": "-an",
            "mpg": "-map 0:a?",
            "avi": "-map 0:a?",
            "ogv": "-map 0:a?",
            "jpg": "-an",
            "png": "-an",
            "webp": "-an",
        }.get(container, "")
        if state.get("Format.Format_MediaType_SelectedItem") == "Audio":
            mapping = "-map 0:a:0?"
    else:
        try:
            number = int(str(stream)) - 1
        except (TypeError, ValueError):
            number = 0
        mapping = f"-map 0:a:{number}?"

    if _is_audio_input(ctx):
        mapping = ""
    if state.get("Audio.Audio_Quality_SelectedItem") == "Mute":
        mapping = "-an"
    return mapping


def subtitle_maps(state: AxiomState, ctx: BuildContext) -> str:
    if state.get("Subtitle.Subtitle_Codec_SelectedItem") == "Burn":
        return ""
    stream = state.get("Subtitle.Subtitle_Stream_SelectedItem")
    container = state.get("Format.Format_Container_SelectedItem")
    if stream == "none":
        mapping = "-sn"
    elif stream == "mux":
        mapping = ""
    elif stream == "all":
        mapping = {
            "webm": "-sn",
            "mp4": "-map 0:s?",
            "mkv": "-map 0:s?",
            "m2v": "-sn",
            "mpg": "-map 0:s?",
            "avi": "-map 0:s?",
            "ogv": "-map 0:s?",
            "jpg": "-sn",
            "png": "-sn",
            "webp": "-sn",
        }.get(container, "-sn")
    else:
        try:
            number = int(str(stream)) - 1
        except (TypeError, ValueError):
            number = 0
        mapping = f"-map 1:s:{number}?"
        if container in ("jpg", "png", "webp"):
            mapping = "-sn"

    if _is_audio_input(ctx):
        mapping = ""
    return mapping


def chapters_maps(state: AxiomState, ctx: BuildContext) -> str:
    container = state.get("Format.Format_Container_SelectedItem")
    mapping = {
        "webm": "-map_chapters -1",
        "mp4": "-map_chapters 0",
        "mkv": "-map_chapters 0",
        "m2v": "-map_chapters -1",
        "mpg": "-map_chapters 0",
        "avi": "-map_chapters 0",
        "ogv": "-map_chapters 0",
        "mp3": "-map_chapters 0",
        "m4a": "-map_chapters 0",
        "ogg": "-map_chapters 0",
        "flac": "-map_chapters 0",
        "wav": "-map_chapters 0",
    }.get(container, "")
    if _is_audio_input(ctx):
        mapping = ""
    return mapping
