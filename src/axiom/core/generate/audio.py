"""Ports of the ``Generate.Audio.*`` fragments used by the single-file pipeline."""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .. import codecs
from ..state import AxiomState
from ..text import normalize_value
from .context import BuildContext
from .metadata import stream_metadata


def _row(codec: str, section: str, name: str) -> Dict[str, Any]:
    for item in codecs.table("audio", codec, section):
        if isinstance(item, Mapping) and item.get("Name") == name:
            return dict(item)
    return {}


def audio_codec(state: AxiomState) -> str:
    codec = state.get("Audio.Audio_Codec_SelectedItem")
    if codec == "None":
        return ""
    if codec == "PCM":
        depth = state.get("Audio.Audio_BitDepth_SelectedItem")
        return "-c:a " + {
            "auto": "pcm_s24le",
            "8": "pcm_u8",
            "16": "pcm_s16le",
            "24": "pcm_s24le",
            "32": "pcm_f32le",
            "64": "pcm_f64le",
        }.get(str(depth), "pcm_s24le")
    return str(state.get("Audio.Audio_Codec") or "")


def _limit(codec: str, quality: str, value: int) -> int:
    if codec == "Copy" or quality != "Auto":
        return value
    limits = {
        "Vorbis": 500000,
        "Opus": 510000,
        "AAC": 400000,
        "AC3": 640000,
        "MP2": 384000,
        "LAME": 320000,
        "FLAC": 1411000,
        "PCM": 1536000,
    }
    if codec == "DTS":
        if value > 1509075:
            return 1509075
        if value < 320000:
            return 320000
        return value
    if codec in limits:
        return min(value, limits[codec])
    return 320000


def audio_bitrate_calculator(ctx: BuildContext, codec: str, quality: str, value: str) -> str:
    if not ctx.probe_value("inputAudioBitRate"):
        return value
    text = str(value)
    if len(text) >= 3 and text[:3] == "N/A":
        text = "N/A"
    if text == "N/A":
        return text
    try:
        number = float(text)
    except ValueError:
        return text
    kb = number * 0.001
    _limit(codec, quality, int(number))
    # Axiom formats this from the original double, after applying the limiter to
    # a different variable - the limiter is therefore not visible here.
    if kb == int(kb):
        return str(int(kb))
    return f"{kb:0.1f}"


def audio_vbr_calculator(ctx: BuildContext, codec: str, quality: str, value: str) -> str:
    try:
        number = float(value or "320000")
    except ValueError:
        number = 320000.0
    if quality == "Auto":
        number /= 1000.0
    if codec == "Vorbis":
        result = round(normalize_value(number, 0, 320, 0, 10, 5), 5)
    elif codec == "Opus":
        if number > 510:
            result = float(_row(codec, "quality", "Auto").get("VBR") or 0)
        else:
            result = round(number)
    elif codec == "AAC":
        if number > 400:
            result = float(_row(codec, "quality", "Auto").get("VBR") or 0)
        else:
            result = min(2, max(number * 0.00625, 0.1))
    elif codec == "MP2":
        result = (
            float(_row(codec, "quality", "Auto").get("VBR") or 0)
            if number > 384
            else (((number * -0.01) / 2.60) + 1) * 10
        )
    elif codec == "LAME":
        result = (
            float(_row(codec, "quality", "Auto").get("VBR") or 0)
            if number > 320
            else (((number * -0.01) / 2.60) + 1) * 10
        )
    else:
        result = 0.0
    text = f"{result:.5f}".rstrip("0").rstrip(".")
    return text or "0"


def bit_rate_mode(state: AxiomState, quality: str, bitrate_text: str, vbr: bool) -> str:
    if quality != "Auto" and not (bitrate_text or "").strip():
        return ""
    row = _row(str(state.get("Audio.Audio_Codec_SelectedItem")), "quality", quality)
    return str(row.get("VBR_BitMode" if vbr else "CBR_BitMode") or "")


def audio_quality(ctx: BuildContext) -> str:
    state = ctx.state
    codec = str(state.get("Audio.Audio_Codec_SelectedItem") or "")
    if codec == "Copy":
        return ""
    quality = str(state.get("Audio.Audio_Quality_SelectedItem") or "")
    bitrate_text = str(state.get("Audio.Audio_BitRate_Text") or "")
    vbr = bool(state.get("Audio.Audio_VBR_IsChecked"))
    bitmode = bit_rate_mode(state, quality, bitrate_text, vbr)
    if not bitmode:
        return ""

    bitrate = ""
    if quality == "Auto":
        if ctx.batch:
            if bitmode == "-q:a":
                bitrate = str(_row(codec, "quality", quality).get("VBR") or "")
            else:
                bitrate = "%A" if ctx.shell == "CMD" else "$aBitrate"
            return " ".join(part for part in (bitmode, bitrate) if part)
        input_rate = ctx.probe_value("inputAudioBitRate")
        if input_rate:
            if vbr:
                bitrate = audio_vbr_calculator(ctx, codec, quality, input_rate)
            else:
                bitrate = audio_bitrate_calculator(ctx, codec, quality, input_rate)
        else:
            bitmode = ""
        if not (state.get("Main.Input_Text") or "").strip():
            bitmode = "-b:a"
            bitrate = str(_row(codec, "quality", "Auto").get("NA") or "")
        if bitrate == "0" and not vbr:
            bitmode = bitrate = ""
        if not bitrate:
            bitmode = ""
    elif quality == "Lossless":
        bitrate = str(_row(codec, "quality", "Lossless").get("Lossless") or "")
    elif quality == "Custom":
        if vbr:
            bitrate = audio_vbr_calculator(ctx, codec, quality, bitrate_text)
        else:
            bitrate = bitrate_text
    else:
        bitrate = bitrate_text

    if bitrate and bitmode != "-q:a" and bitrate not in ("%A", "$aBitrate"):
        bitrate += "k"
    return " ".join(part for part in (bitmode, bitrate) if part)


def compression_level(state: AxiomState) -> str:
    if state.get("Audio.Audio_Codec_SelectedItem") == "Copy":
        return ""
    value = state.get("Audio.Audio_CompressionLevel_SelectedItem")
    if value in ("none", "auto", "", None):
        return ""
    return "-compression_level " + str(value)


def sample_rate(state: AxiomState) -> str:
    if state.get("Audio.Audio_Codec_SelectedItem") == "Copy":
        return ""
    value = state.get("Audio.Audio_SampleRate_SelectedItem")
    if value == "auto":
        return ""
    row = _row(
        str(state.get("Audio.Audio_Codec_SelectedItem")),
        "sampleRate",
        str(value),
    )
    return "-ar " + str(row.get("Frequency") or "")


def bit_depth(state: AxiomState) -> str:
    if state.get("Audio.Audio_Codec_SelectedItem") == "Copy":
        return ""
    value = state.get("Audio.Audio_BitDepth_SelectedItem")
    if value == "auto":
        return ""
    row = _row(
        str(state.get("Audio.Audio_Codec_SelectedItem")),
        "bitDepth",
        str(value),
    )
    return str(row.get("Depth") or "")


def channel(state: AxiomState) -> str:
    if state.get("Audio.Audio_Codec_SelectedItem") == "Copy":
        return ""
    value = str(state.get("Audio.Audio_Channel_SelectedItem") or "")
    mapping = {
        "": "",
        "Source": "",
        "Mono": "-ac 1",
        "Stereo": "-ac 2",
        "Joint Stereo": "-ac 2 -joint_stereo 1",
        "5.1": "-ac 6",
    }
    result = mapping.get(value, "")
    if value != "Source":
        result = "-rematrix_maxval 1.0 " + result
    return result


def audio_metadata(state: AxiomState) -> str:
    return stream_metadata(state, "audio")


def audio_mux(ctx: BuildContext) -> str:
    state = ctx.state
    if (
        state.get("Audio.Audio_Codec_SelectedItem") != "None"
        and state.get("Audio.Audio_Stream_SelectedItem") == "mux"
        and ctx.audio_paths
    ):
        return "-i " + " -i ".join(path for path in ctx.audio_paths if path.strip())
    return ""
