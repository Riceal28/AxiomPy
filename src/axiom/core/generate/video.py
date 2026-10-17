"""Ports of the ``Generate.Video.*`` fragments used by the single-file pipeline."""

from __future__ import annotations

import re
from typing import Any, Dict, Mapping

from .. import codecs
from ..state import AxiomState
from . import filters_video
from .context import BuildContext


SCALE_FIX_CODECS = {
    "x264",
    "x265",
    "H264 AMF",
    "HEVC AMF",
    "H264 NVENC",
    "HEVC NVENC",
    "H264 QSV",
    "HEVC QSV",
    "MPEG-2",
    "MPEG-4",
}

SIZE_AUTO_CODECS = {
    "VP8",
    "VP9",
    "AV1",
    "FFV1",
    "HuffYUV",
    "Theora",
    "JPEG",
    "PNG",
    "WebP",
}


def _row(kind: str, codec: str, section: str, name: str) -> Dict[str, Any]:
    for item in codecs.table(kind, codec, section):
        if isinstance(item, Mapping) and item.get("Name") == name:
            return dict(item)
    return {}


def video_codec(state: AxiomState) -> str:
    if state.get("Video.Video_Codec_SelectedItem") == "None":
        return ""
    return str(state.get("Video.Video_Codec") or "")


def hw_accel_decode(state: AxiomState) -> str:
    selected = state.get("Video.Video_HWAccel_Decode_SelectedItem")
    if selected == "off" or state.get("Format.Format_MediaType_SelectedItem") == "Audio":
        return ""
    return {
        "auto": "-hwaccel auto",
        "CUDA": "-hwaccel cuda",
        "CUVID": "-hwaccel cuvid",
        "D3D11VA": "-hwaccel d3d11va",
        "DXVA2": "-hwaccel dxva2",
        "Intel QSV": "-hwaccel qsv -hwaccel_output_format qsv",
    }.get(str(selected), "")


def hw_accel_transcode(state: AxiomState) -> str:
    return ""


def encode_speed(state: AxiomState, pass_name: str | None = None) -> str:
    codec = state.get("Video.Video_Codec_SelectedItem")
    if not codec:
        return ""
    selected = state.get("Video.Video_EncodeSpeed_SelectedItem")
    row = _row("video", str(codec), "encodeSpeed", str(selected))
    if codec == "Copy":
        return ""
    if codec in ("Auto", "VP8") and pass_name == "2 Pass":
        return str(row.get("Command_2Pass") or row.get("Command") or "")
    return str(row.get("Command") or "")


def bit_rate_mode(state: AxiomState, quality: str, bitrate_text: str, vbr: bool) -> str:
    if quality != "Auto" and not (bitrate_text or "").strip():
        return ""
    row = _row("video", str(state.get("Video.Video_Codec_SelectedItem")), "quality", quality)
    return str(row.get("VBR_BitMode" if vbr else "CBR_BitMode") or "")


def video_bitrate_calculator(ctx: BuildContext) -> str:
    state = ctx.state
    if not (state.get("Main.Input_Text") or "").strip():
        return ctx.probe_value("inputVideoBitRate")
    bitrate = ctx.probe_value("inputVideoBitRate").strip()
    if not bitrate:
        return bitrate
    bitrate = re.sub("[kKmM]", "", bitrate)
    if len(bitrate) >= 3 and bitrate[:3] == "N/A":
        bitrate = "N/A"
    if bitrate == "N/A":
        try:
            size = float(ctx.probe_value("inputSize").strip())
            duration = float(ctx.probe_value("inputDuration").strip())
            bitrate = "0" if size == 0 or duration == 0 else str(int(size * 8 / 1000 / duration))
        except ValueError:
            bitrate = "0"
    else:
        try:
            bitrate = str(round(float(bitrate.strip()) * 0.001))
        except ValueError:
            pass
        if state.get("Format.Format_Container_SelectedItem") == "webm":
            try:
                if float(bitrate) >= 1500:
                    bitrate = "1500"
            except ValueError:
                pass
    if state.get("Format.Format_MediaType_SelectedItem") not in ("Image", "Sequence"):
        bitrate += "K"
    return bitrate


def quality_params(ctx: BuildContext) -> str:
    state = ctx.state
    codec = state.get("Video.Video_Codec_SelectedItem")
    if codec not in (
        "x264",
        "H264 AMF",
        "H264 NVENC",
        "H264 QSV",
        "x265",
        "HEVC AMF",
        "HEVC NVENC",
        "HEVC QSV",
    ):
        return ""
    if state.get("Video.Video_Quality_SelectedItem") == "None":
        return ""
    if state.get("Format.Format_MediaType_SelectedItem") == "Audio":
        return ""
    params = [part for part in ctx.v_params if part]
    if not params:
        return ""
    prefix = "-x264-params " if codec in ("x264", "H264 AMF", "H264 NVENC", "H264 QSV") else "-x265-params "
    return prefix + ctx.quote(":".join(params))


def pix_fmt(state: AxiomState) -> str:
    codec = state.get("Video.Video_Codec_SelectedItem")
    value = state.get("Video.Video_PixelFormat_SelectedItem")
    if codec == "Copy" or value in ("auto", "none"):
        return ""
    return "-pix_fmt " + str(value)


def optimize(state: AxiomState) -> str:
    if state.get("Video.Video_Codec_SelectedItem") == "Copy":
        return ""
    tune = state.get("Video.Video_Optimize_Tune_SelectedItem")
    profile = state.get("Video.Video_Optimize_Profile_SelectedItem")
    level = state.get("Video.Video_Optimize_Level_SelectedItem")
    row = _row(
        "video",
        str(state.get("Video.Video_Codec_SelectedItem")),
        "optimize",
        str(state.get("Video.Video_Optimize_SelectedItem")),
    )
    parts = []
    if tune and tune != "none":
        parts.append("-tune " + str(tune))
    if profile and profile != "none":
        parts.append("-profile:v " + str(profile))
    if level and level != "none":
        parts.append("-level " + str(level))
    if row.get("Command"):
        parts.append(str(row["Command"]))
    return " ".join(parts)


def fps(state: AxiomState) -> str:
    codec = state.get("Video.Video_Codec_SelectedItem")
    text = state.get("Video.Video_FPS_Text")
    selected = state.get("Video.Video_FPS_SelectedItem")
    if codec == "Copy" or not (text or "").strip():
        return ""
    if selected == "auto":
        return ""
    mapping = {
        "film": "film",
        "pal": "pal",
        "ntsc": "ntsc",
        "23.976": "24000/1001",
        "24": "24",
        "25": "25",
        "29.97": "30000/1001",
        "30": "30",
        "48": "48",
        "50": "50",
        "59.94": "60000/1001",
        "60": "60",
    }
    return "-r " + mapping.get(str(selected), str(text))


def vsync(state: AxiomState) -> str:
    codec = state.get("Video.Video_Codec_SelectedItem")
    selected = state.get("Video.Video_Vsync_SelectedItem")
    if codec == "Copy" or selected == "off":
        return ""
    return {
        "auto": "-vsync auto",
        "passthrough": "-vsync passthrough",
        "cfr": "-vsync cfr",
        "vfr": "-vsync vfr",
        "drop": "-vsync drop",
    }.get(str(selected), "")


def images(state: AxiomState) -> str:
    if state.get("Video.Video_Codec_SelectedItem") == "Copy":
        return ""
    if state.get("Format.Format_MediaType_SelectedItem") == "Image":
        return "-vframes 1"
    return ""


def aspect_ratio(state: AxiomState) -> str:
    selected = str(state.get("Video.Video_AspectRatio_SelectedItem") or "auto")
    if selected == "auto":
        return ""
    if selected == "2.4:1":
        return "-aspect 240:100"
    return "-aspect " + selected


def _scaling_algorithm(state: AxiomState) -> str:
    selected = state.get("Video.Video_ScalingAlgorithm_SelectedItem")
    return "" if selected == "auto" else ":flags=" + str(selected)


def _size_auto(codec: str) -> str:
    if codec in SIZE_AUTO_CODECS:
        return "-1"
    if codec in SCALE_FIX_CODECS:
        return "-2"
    return "-1"


def add_scale_filter(ctx: BuildContext) -> None:
    state = ctx.state
    codec = state.get("Video.Video_Codec_SelectedItem")
    codec = str(codec or "")
    size = str(state.get("Video.Video_Scale_SelectedItem") or "")
    width_text = str(state.get("Video.Video_Width_Text") or "")
    height_text = str(state.get("Video.Video_Height_Text") or "")
    screen = str(state.get("Video.Video_ScreenFormat_SelectedItem") or "auto")
    crop_clear = str(state.get("Video.Video_CropClear_Text") or "")

    # ``Generate.Video.Size.Scale`` handles four situations.  The Auto branches of
    # Custom sizing deliberately add no scale filter in the original application.
    if size == "Source":
        if codec in SCALE_FIX_CODECS:
            ctx.v_filters.append(
                "scale=trunc(iw/2)*2:trunc(ih/2)*2" + _scaling_algorithm(state)
            )
        return

    if size != "Custom":
        if screen in ("auto", "Widescreen", "Ultrawide"):
            width = width_text
            height = _size_auto(codec)
        elif screen == "Full Screen":
            width = _size_auto(codec)
            height = height_text
        else:
            width = width_text
            height = _size_auto(codec)
        ctx.v_filters.append(f"scale={width}:{height}" + _scaling_algorithm(state))
        return

    width_auto = width_text.lower() == "auto"
    height_auto = height_text.lower() == "auto"

    if codec in ("VP8", "VP9", "Theora", "JPEG", "PNG", "WebP"):
        width = "-1" if width_auto else width_text
        height = "-1" if height_auto else height_text
        ctx.v_filters.append(f"scale={width}:{height}" + _scaling_algorithm(state))
        return

    if codec not in SCALE_FIX_CODECS:
        return

    if width_auto and height_auto:
        return
    if width_auto or height_auto:
        # Preserved from the original: one Auto dimension gets normalized locally but
        # no scale fragment is emitted.
        return

    try:
        width_number = int(width_text)
    except ValueError:
        width_number = 0
    try:
        height_number = int(height_text)
    except ValueError:
        height_number = 0

    scale = f"scale={width_text}:{height_text}" + _scaling_algorithm(state)
    if crop_clear == "Clear":
        ctx.v_filters.append(scale)
    elif crop_clear == "Clear*":
        manual = str(state.values.get("_crop") or "")
        if manual:
            ctx.v_filters.append(manual)
        ctx.v_filters.append(scale)

    if crop_clear in ("Clear", "Clear*") and (
        width_number % 2 or height_number % 2
    ):
        ctx.v_filters.append(
            f"crop={width_number - width_number % 2}:"
            f"{height_number - height_number % 2}:0:0"
        )


def add_speed_filter(ctx: BuildContext) -> None:
    state = ctx.state
    selected = state.get("Video.Video_Speed_SelectedItem")
    text = state.get("Video.Video_Speed_Text")
    if state.get("Video.Video_Codec_SelectedItem") == "Copy" or selected == "auto" or not (
        text or ""
    ).strip():
        return
    try:
        value = float(str(text).replace("%", "").strip())
        factor = (100 / (value * 0.01)) * 0.01
        ctx.v_filters.append("setpts=" + ("%.5f" % factor).rstrip("0").rstrip(".") + "*PTS")
    except (ValueError, ZeroDivisionError):
        pass


def video_filter(ctx: BuildContext) -> str:
    state = ctx.state
    if (
        state.get("Video.Video_Quality_SelectedItem") == "None"
        or state.get("Video.Video_Codec_SelectedItem") in ("None", "Copy")
        or state.get("Format.Format_MediaType_SelectedItem") == "Audio"
    ):
        return ""
    add_speed_filter(ctx)
    add_scale_filter(ctx)
    if (
        state.get("Video.Video_Codec_SelectedItem") == "JPEG"
        and ctx.input_ext.lower() == ".png"
    ):
        ctx.v_filters.append(
            "format=yuva444p,geq='if(lte(alpha(X,Y),16),255,p(X,Y))':"
            "'if(lte(alpha(X,Y),16),128,p(X,Y))':"
            "'if(lte(alpha(X,Y),16),128,p(X,Y))'"
        )
    filters_video.add_video_filters(ctx)
    filters = [part for part in ctx.v_filters if part]
    if not filters:
        return ""
    if len(filters) == 1:
        return "-vf " + ctx.quote(filters[0])
    return "-vf " + ctx.quote(", ".join(filters))


def video_quality(ctx: BuildContext, pass_name: str) -> str:
    state = ctx.state
    codec = state.get("Video.Video_Codec_SelectedItem")
    quality = str(state.get("Video.Video_Quality_SelectedItem") or "")
    if codec == "Copy":
        return ""
    vbr = bool(state.get("Video.Video_VBR_IsChecked"))
    crf_text = str(state.get("Video.Video_CRF_Text") or "")
    bitrate_text = str(state.get("Video.Video_BitRate_Text") or "")
    minrate_text = str(state.get("Video.Video_MinRate_Text") or "")
    maxrate_text = str(state.get("Video.Video_MaxRate_Text") or "")
    bufsize_text = str(state.get("Video.Video_BufSize_Text") or "")

    v_lossless = ""
    v_bitmode = ""
    v_bitrate = ""
    v_minrate = ""
    v_maxrate = ""
    v_bufsize = ""
    v_crf = ""
    v_options = ""

    if quality == "Auto" and codec not in ("FFV1", "HuffYUV"):
        row = _row("video", str(codec), "quality", quality)
        if ctx.batch:
            v_bitmode = "-b:v"
            if state.get("Format.Format_MediaType_SelectedItem") == "Image":
                v_bitrate = str(row.get("VBR") or "")
            else:
                v_bitrate = "%V" if ctx.shell == "CMD" else "$vBitrate"
        else:
            v_bitrate = video_bitrate_calculator(ctx)
            v_bitmode = bit_rate_mode(state, quality, bitrate_text, vbr)
            if not ctx.probe_value("inputVideoBitRate").strip() and codec:
                na = str(row.get("NA") or "")
                if na:
                    v_bitmode = bit_rate_mode(state, quality, bitrate_text, vbr)
                    v_bitrate = na
        v_crf = ""
    elif quality == "Lossless":
        if codec == "x265":
            ctx.v_params.append("lossless")
        else:
            v_lossless = str(_row("video", str(codec), "quality", "Lossless").get("Lossless") or "")
    elif quality == "Custom":
        v_crf = "-crf " + crf_text if crf_text.strip() else ""
        v_bitmode = bit_rate_mode(state, quality, bitrate_text, vbr)
        v_bitrate = bitrate_text
        if minrate_text.strip():
            v_minrate = "-minrate " + minrate_text.upper()
        if maxrate_text.strip():
            v_maxrate = "-maxrate " + maxrate_text.upper()
        if bufsize_text.strip():
            v_bufsize = "-bufsize " + bufsize_text.upper()
    else:
        v_bitmode = bit_rate_mode(state, quality, bitrate_text, vbr)
        if minrate_text.strip():
            v_minrate = "-minrate " + minrate_text.upper()
        if maxrate_text.strip():
            v_maxrate = "-maxrate " + maxrate_text.upper()
        if bufsize_text.strip():
            v_bufsize = "-bufsize " + bufsize_text.upper()
        if pass_name == "auto":
            v_crf = v_bitrate = v_minrate = v_maxrate = v_bufsize = ""
        elif pass_name == "CRF":
            if codec == "x265":
                if crf_text.strip():
                    v_crf = "-crf " + crf_text
                ctx.v_params.append(
                    "crf=" + str(_row("video", str(codec), "quality", quality).get("CRF") or "")
                )
            else:
                v_bitrate = bitrate_text
                if crf_text.strip():
                    v_crf = "-crf " + crf_text
        else:
            v_bitrate = bitrate_text

    args = [v_lossless, v_bitmode, v_bitrate, v_minrate, v_maxrate, v_bufsize]
    if pass_name == "CRF":
        args += [v_crf, v_options]
    else:
        args.append(v_options)
    return " ".join(part for part in args if part)


def pass_params(ctx: BuildContext, codec: str, pass_name: str, number: str) -> str:
    if number == "2":
        ctx.v_params.clear()
    if pass_name == "2 Pass" and codec == "x265":
        ctx.v_params.append("pass=" + number)
    return ""


def pass1_modifier(codec: str, pass_name: str) -> str:
    if pass_name == "2 Pass":
        return "" if codec == "x265" else "-pass 1"
    return ""


def pass2_modifier(codec: str, pass_name: str) -> str:
    if pass_name == "2 Pass":
        return "" if codec == "x265" else "-pass 2"
    return ""


def color_args(state: AxiomState) -> list[str]:
    """Only the non-auto colour values (the default resolves to empty)."""
    values = []
    range_value = state.get("Video.Video_Color_Range_SelectedItem")
    if range_value not in (None, "", "auto"):
        values.append("-color_range " + {
            "TV": "tv",
            "PC": "pc",
            "MPEG": "mpeg",
            "JPEG": "jpeg",
        }.get(str(range_value), str(range_value)))
    space = state.get("Video.Video_Color_Space_SelectedItem")
    if space not in (None, "", "auto"):
        values.append("-colorspace " + {
            "BT.709": "bt709",
            "FCC": "fcc",
            "BT.470BG": "bt470bg",
            "BT.601-6 525": "smpte170m",
            "BT.601-6 625": "bt470bg",
            "SMPTE-170M": "smpte170m",
            "SMPTE-240M": "smpte240m",
            "YCgCo": "ycgco",
            "BT.2020 NCL": "bt2020nc",
        }.get(str(space), str(space)))
    primaries = state.get("Video.Video_Color_Primaries_SelectedItem")
    if primaries not in (None, "", "auto"):
        values.append("-color_primaries " + {
            "BT.709": "bt709",
            "BT.470M": "bt470m",
            "BT.470BG": "bt470bg",
            "BT.601-6 525": "smpte170m",
            "BT.601-6 625": "bt470bg",
            "SMPTE-170M": "smpte170m",
            "SMPTE-240M": "smpte240m",
            "film": "film",
            "SMPTE-431": "smpte431",
            "SMPTE-432": "smpte432",
            "BT.2020": "bt2020",
            "JEDEC P22 phosphors": "jedec-p22",
        }.get(str(primaries), str(primaries)))
    transfer = state.get("Video.Video_Color_TransferCharacteristics_SelectedItem")
    if transfer not in (None, "", "auto"):
        values.append("-color_trc " + {
            "BT.709": "bt709",
            "BT.470M": "bt470m",
            "BT.470BG": "bt470bg",
            "Gamma 2.2": "gamma22",
            "Gamma 2.8": "gamma28",
            "BT.601-6 525": "smpte170m",
            "BT.601-6 625": "bt470bg",
            "SMPTE-170M": "smpte170m",
            "SMPTE-240M": "smpte240m",
            "SRGB": "iec61966-2-1",
            "iec61966-2-1": "iec61966-2-1",
            "iec61966-2-4": "iec61966-2-4",
            "xvycc": "xvycc",
            "BT.2020 10-bit": "bt2020-10",
            "BT.2020 12-bit": "bt2020-12",
        }.get(str(transfer), str(transfer)))
    return values
