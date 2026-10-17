"""Control-layer resolution.

The original GUI resolves a lot of state as the user picks a container, media type and
codecs: it copies the codec's item tables into the ViewModel, applies the codec's
``controls_Enabled`` / ``controls_Selected`` overrides, defaults the pass mode and keeps
the previous codec's choice where sensible.  The generators then read that resolved
state.

This module reproduces the same steps from :mod:`axiom.core.controls_data` (extracted
from the C# control files) and :mod:`axiom.core.codecs_data`, so the CLI and the UI share
one implementation and the parity tests can compare it against the oracle's state dump.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from . import codecs
from .controls_data import CONTROLS
from .containers_data import CONTAINERS, FORMAT_CONTROLS
from .state import AxiomState

KIND_GROUP = {"video": "Video", "audio": "Audio", "subtitle": "Subtitle"}
KIND_CODEC_FLAG = {"video": "-c:v", "audio": "-c:a", "subtitle": "-c:s"}

def item_names(items: Sequence[Any]) -> list[str]:
    """Names of an item source (rows become their ``Name``, strings stay as they are)."""
    names: list[str] = []
    for item in items or []:
        if isinstance(item, Mapping):
            names.append(str(item.get("Name", "")))
        else:
            names.append(str(item))
    return names


def save_previous_item_cond(selected_item: str | None) -> bool:
    """Port of MainWindow.SavePreviousItemCond.

    The original's "default/auto/none" guard joins the three comparisons with
    ``&&``, so only the whitespace check can actually return false.
    """
    return bool(selected_item and selected_item.strip())


def selected_item(items: Sequence[Any], previous_item: str | None) -> str | None:
    """Port of MainWindow.SelectedItem: reuse the previous choice when it still exists."""
    names = item_names(items)
    if previous_item and previous_item.strip() and previous_item in names:
        return previous_item
    return names[0] if names else None


def _previous_flags(state: AxiomState) -> Dict[str, Any]:
    return state.flags.setdefault("previousItems", {})


def _enabled_row(kind: str, name: str) -> Dict[str, Any]:
    rows = codecs.table(kind, name, "controls_Enabled")
    return dict(rows[0]) if rows else {}


def _selected_row(kind: str, name: str) -> Dict[str, Any]:
    rows = codecs.table(kind, name, "controls_Selected")
    return dict(rows[0]) if rows else {}


def codec_controls(state: AxiomState, kind: str, name: str) -> Dict[str, Any]:
    """Replay ``Controls.<Kind>.Controls.CodecControls`` for one codec."""
    if not name or not name.strip():
        return {}
    if not codecs.has(kind, name):
        raise KeyError(f"unknown {kind} codec: {name}")

    group = KIND_GROUP[kind]
    rules = CONTROLS.get(kind, {"enabled": [], "selected": []})
    applied: Dict[str, Any] = {}

    # 1. Codec + parameters, exactly as the original joins them (empty parts dropped).
    codec_rows = codecs.table(kind, name, "codec")
    codec_name = str(codec_rows[0].get("Codec", "")) if codec_rows else ""
    parameters = str(codec_rows[0].get("Parameters", "")) if codec_rows else ""
    state.set(
        f"{group}.{group}_Codec",
        " ".join(part for part in (KIND_CODEC_FLAG[kind], codec_name, parameters) if part),
    )

    # 2. Remember the current choices before the item sources change.
    previous = _previous_flags(state)
    for rule in rules["selected"]:
        field = f"{group}.{rule['field']}"
        current = state.get(field)
        if rule["previousItem"] and save_previous_item_cond(current):
            previous[rule["previousItem"]] = current

    # 3. Item sources, in the original order (the pass state machine runs in between).
    for section, field in (
        ("encodeSpeed", f"{group}_EncodeSpeed_Items"),
        ("pixelFormat", f"{group}_PixelFormat_Items"),
    ):
        if codecs.table(kind, name, section):
            state.set(f"{group}.{field}", codecs.table(kind, name, section))

    codecs.apply_quality_pass(state, kind, name)

    for section, field in (
        ("quality", f"{group}_Quality_Items"),
        ("optimize", f"{group}_Optimize_Items"),
        ("tune", f"{group}_Optimize_Tune_Items"),
        ("profile", f"{group}_Optimize_Profile_Items"),
        ("level", f"{group}_Optimize_Level_Items"),
    ):
        if codecs.table(kind, name, section):
            state.set(f"{group}.{field}", codecs.table(kind, name, section))

    # 4. controls_Enabled overrides - note the guard variable is the one the original
    #    actually tested (verbatim from the source, including its copy/paste slip).
    enabled_row = _enabled_row(kind, name)
    for rule in rules["enabled"]:
        guard_prop = VIDEO_GUARD_PROP.get(rule["guard"], rule["guard"])
        guard_value = enabled_row.get(guard_prop)
        value = True if guard_value is None else bool(guard_value)
        state.set(f"{rule['view']}.{rule['field']}", value)
        applied[rule["field"]] = value

    if kind == "video":
        if name in ("Copy", "None"):
            _video_filters_disable_all(state)
            _video_filters_select_defaults(state)
        else:
            _video_filters_enable_all(state)

    # 5. controls_Selected overrides.
    selected_row = _selected_row(kind, name)
    for rule in rules["selected"]:
        field = f"{group}.{rule['field']}"
        value = selected_row.get(rule["prop"])
        if value not in (None, ""):
            state.set(field, value)
            applied[rule["field"]] = value
        elif rule["previousItem"]:
            items = state.get(f"{group}.{rule['previousItems']}") or []
            previous_value = previous.pop(rule["previousItem"], None)
            chosen = selected_item(items, previous_value)
            if chosen is not None:
                state.set(field, chosen)
                applied[rule["field"]] = chosen

    if kind == "video":
        quality = state.get("Video.Video_Quality_SelectedItem")
        key = "PixelFormat_Lossless" if quality == "Lossless" else "PixelFormat"
        value = selected_row.get(key)
        if value:
            state.set("Video.Video_PixelFormat_SelectedItem", value)
            applied["PixelFormat_SelectedItem"] = value

    # 6. controls_Checked / controls_Expanded, gated on the enable flag set above.
    for rule in rules.get("flags", []):
        rows = codecs.table(kind, name, "controls_" + rule["group"])
        row = dict(rows[0]) if rows else {}
        field = f"{rule['view']}.{rule['field']}"
        if state.get(f"{rule['view']}.{rule['gate']}") is True:
            value = row.get(rule["prop"])
            state.set(field, True if value is None else bool(value))
        else:
            state.set(field, False)
        applied[rule["field"]] = state.get(field)
    return applied


def resolve(state: AxiomState) -> AxiomState:
    """Resolve every control group the way the GUI does before a conversion.

    The call order follows ``tools/parity_harness/Program.ResolveControls`` and the
    WPF event chain: container -> media type -> cut/streams -> codec -> quality.
    """
    format_controls(state, state.get("Format.Format_Container_SelectedItem") or "")

    # Test fixtures may simulate the user changing a combo box after the container
    # was picked (FormatControls would otherwise overwrite the codec with its default).
    for key, value in (state.values.get("_after_format") or {}).items():
        state.set(key, value)

    media_type_controls(state)
    media_type_controls_selected_items(state)
    cut_controls(state)
    audio_stream_controls(state)

    video_codec = state.get("Video.Video_Codec_SelectedItem")
    if video_codec:
        codec_controls(state, "video", str(video_codec))
        encoding_pass_controls(state)
        pixel_format_controls(state)
        video_optimize_controls(state)
        video_quality_controls(state)
        video_bitrate_display(state)

    audio_codec = state.get("Audio.Audio_Codec_SelectedItem")
    if audio_codec:
        audio_codec_controls(state, str(audio_codec))
        audio_quality_controls(state)
        audio_bitrate_display(state)

    subtitle_codec = state.get("Subtitle.Subtitle_Codec_SelectedItem")
    if subtitle_codec:
        subtitle_codec_controls(state, str(subtitle_codec))
    for key, value in (state.values.get("_after_controls") or {}).items():
        state.set(key, value)
    state.flags["controlsResolved"] = True
    return state


def format_controls(state: AxiomState, container: str) -> Dict[str, Any]:
    """Port of Controls.Format.Controls.FormatControls (container -> item lists + defaults)."""
    if not container:
        return {}
    spec = FORMAT_CONTROLS.get(container) or {}
    applied: Dict[str, Any] = {}
    for field, action in spec.items():
        if action[0] == "list":
            values = list(CONTAINERS.get(action[1], {}).get(action[2], []))
            state.set(field, values)
            applied[field] = values
        else:
            state.set(field, action[1])
            applied[field] = action[1]
    return applied


# --------------------------------------------------------------------------------------
# Format: media type, cut and audio stream
# --------------------------------------------------------------------------------------

VIDEO_ENABLE_FIELDS = (
    "Video_Codec_IsEnabled",
    "Video_HWAccel_IsEnabled",
    "Video_PixelFormat_IsEnabled",
    "Video_Scale_IsEnabled",
    "Video_ScreenFormat_IsEnabled",
    "Video_AspectRatio_IsEnabled",
    "Video_Crop_IsEnabled",
    "Video_Color_Range_IsEnabled",
    "Video_Color_Space_IsEnabled",
    "Video_Color_Primaries_IsEnabled",
    "Video_Color_TransferCharacteristics_IsEnabled",
    "Video_Color_Matrix_IsEnabled",
)

VIDEO_DISABLE_FIELDS = VIDEO_ENABLE_FIELDS + (
    "Video_EncodeSpeed_IsEnabled",
    "Video_Quality_IsEnabled",
    "Video_VBR_IsEnabled",
    "Video_FPS_IsEnabled",
    "Video_Speed_IsEnabled",
    "Video_Vsync_IsEnabled",
    "Video_Optimize_IsEnabled",
    "Video_ScalingAlgorithm_IsEnabled",
)

AUDIO_ENABLE_FIELDS = (
    "Audio_Codec_IsEnabled",
    "Audio_Stream_IsEnabled",
    "Audio_Channel_IsEnabled",
    "Audio_Volume_IsEnabled",
    "Audio_HardLimiter_IsEnabled",
)

AUDIO_DISABLE_FIELDS = (
    "Audio_Codec_IsEnabled",
    "Audio_Stream_IsEnabled",
    "Audio_Channel_IsEnabled",
    "Audio_Quality_IsEnabled",
    "Audio_CompressionLevel_IsEnabled",
    "Audio_SampleRate_IsEnabled",
    "Audio_BitDepth_IsEnabled",
    "Audio_Volume_IsEnabled",
    "Audio_HardLimiter_IsEnabled",
)


def _set_fields(state: AxiomState, group: str, fields: Sequence[str], value: Any) -> None:
    for field in fields:
        state.set(f"{group}.{field}", value)


def _enable_video(state: AxiomState, *, encode_speed: bool, fps: bool) -> None:
    _set_fields(state, "Video", VIDEO_ENABLE_FIELDS, True)
    state.set("Video.Video_EncodeSpeed_IsEnabled", encode_speed)
    state.set("Video.Video_FPS_IsEnabled", fps)
    state.set("Video.Video_Speed_IsEnabled", fps)
    state.set("Video.Video_Vsync_IsEnabled", fps)


def _disable_video(state: AxiomState) -> None:
    _set_fields(state, "Video", VIDEO_DISABLE_FIELDS, False)


def _enable_audio(state: AxiomState) -> None:
    _set_fields(state, "Audio", AUDIO_ENABLE_FIELDS, True)


def _disable_audio(state: AxiomState, *, reset_limiter: bool = False) -> None:
    _set_fields(state, "Audio", AUDIO_DISABLE_FIELDS, False)
    if reset_limiter:
        state.set("Audio.Audio_HardLimiter_Value", 0.0)


def media_type_controls(state: AxiomState) -> None:
    """Port of ``Controls.Format.Controls.MediaTypeControls``."""
    media_type = state.get("Format.Format_MediaType_SelectedItem") or ""
    video = state.get("Video.Video_Codec_SelectedItem") or ""
    audio = state.get("Audio.Audio_Codec_SelectedItem") or ""
    subtitle = state.get("Subtitle.Subtitle_Codec_SelectedItem") or ""

    if media_type == "Video":
        if video and video not in ("Copy", "None"):
            _enable_video(state, encode_speed=True, fps=True)
        if audio and audio not in ("Copy", "None"):
            _enable_audio(state)
        if subtitle and subtitle not in ("Copy", "None"):
            state.set("Subtitle.Subtitle_Codec_IsEnabled", True)

    elif media_type == "Audio":
        state.set("Format.Format_FrameEnd_IsEnabled", False)
        if video and video != "Copy":
            _disable_video(state)
        if audio and audio not in ("Copy", "None"):
            _enable_audio(state)
        if subtitle and subtitle != "Copy":
            state.set("Subtitle.Subtitle_Codec_IsEnabled", False)
            state.set("Subtitle.Subtitle_Stream_IsEnabled", False)

    elif media_type == "Image":
        state.set("Format.Format_CutStart_IsEnabled", True)
        state.set("Format.Format_CutEnd_IsEnabled", False)
        state.set("Format.Format_CutEnd_Hours_Text", "")
        state.set("Format.Format_CutEnd_Minutes_Text", "")
        state.set("Format.Format_CutEnd_Seconds_Text", "")
        state.set("Format.Format_CutEnd_Milliseconds_Text", "")
        state.set("Format.Format_FrameEnd_IsEnabled", False)

        if video and video not in ("Copy", "None"):
            _enable_video(state, encode_speed=False, fps=False)
        if audio and audio != "Copy":
            _disable_audio(state, reset_limiter=True)
        if subtitle and subtitle not in ("Copy", "None"):
            state.set("Subtitle.Subtitle_Codec_IsEnabled", True)

    elif media_type == "Sequence":
        if video and video not in ("Copy", "None"):
            _enable_video(state, encode_speed=False, fps=True)
        if audio and audio != "Copy":
            _disable_audio(state, reset_limiter=True)
        if subtitle and subtitle != "Copy":
            state.set("Subtitle.Subtitle_Codec_IsEnabled", True)


def media_type_controls_selected_items(state: AxiomState) -> None:
    """Port of ``Controls.Format.Controls.MediaTypeControls_SelectedItems``."""
    media_type = state.get("Format.Format_MediaType_SelectedItem") or ""
    cut_start = state.get("Format.Format_CutStart_IsEnabled")
    cut_end = state.get("Format.Format_CutEnd_IsEnabled")

    if media_type == "Video":
        if cut_start is True and cut_end is False:
            state.set("Format.Format_Cut_SelectedItem", "No")
        state.set("Format.Format_YouTube_SelectedItem", "Video + Audio")

    elif media_type == "Audio":
        if cut_start is True and cut_end is False:
            state.set("Format.Format_Cut_SelectedItem", "No")
        state.set("Format.Format_YouTube_SelectedItem", "Audio Only")
        state.set("Format.Format_FrameEnd_Text", "")
        state.set("Video.Video_HWAccel_SelectedItem", "off")
        state.set("Video.Video_FPS_SelectedItem", "auto")
        state.set("Video.Video_Scale_SelectedItem", "Source")
        state.set("Video.Video_ScalingAlgorithm_SelectedItem", "auto")

    elif media_type == "Image":
        state.set("Format.Format_Cut_SelectedItem", "Yes")
        state.set("Format.Format_FrameEnd_Text", "")
        state.set("Format.Format_YouTube_SelectedItem", "Video + Audio")
        state.set("Video.Video_FPS_SelectedItem", "auto")
        state.set("Video.Video_ScalingAlgorithm_SelectedItem", "auto")
        state.set("Audio.Audio_Channel_SelectedItem", "none")
        state.set("Audio.Audio_Quality_SelectedItem", "None")
        state.set("Audio.Audio_CompressionLevel_SelectedItem", "none")
        state.set("Audio.Audio_SampleRate_SelectedItem", "auto")
        state.set("Audio.Audio_BitDepth_SelectedItem", "auto")

    elif media_type == "Sequence":
        if cut_start is True and cut_end is False:
            state.set("Format.Format_Cut_SelectedItem", "No")
        state.set("Format.Format_YouTube_SelectedItem", "Video + Audio")
        state.set("Video.Video_ScalingAlgorithm_SelectedItem", "auto")
        state.set("Audio.Audio_Channel_SelectedItem", "none")
        state.set("Audio.Audio_Quality_SelectedItem", "None")
        state.set("Audio.Audio_CompressionLevel_SelectedItem", "none")
        state.set("Audio.Audio_SampleRate_SelectedItem", "auto")
        state.set("Audio.Audio_BitDepth_SelectedItem", "auto")

    if state.get("Format.Format_CutStart_IsEnabled") is False and state.get(
        "Format.Format_CutEnd_IsEnabled"
    ) is False:
        for prefix in ("Format_CutStart", "Format_CutEnd"):
            state.set(f"Format.{prefix}_Hours_Text", "00")
            state.set(f"Format.{prefix}_Minutes_Text", "00")
            state.set(f"Format.{prefix}_Seconds_Text", "00")
            state.set(f"Format.{prefix}_Milliseconds_Text", "000")


def cut_controls(state: AxiomState) -> None:
    """Port of ``Controls.Format.Controls.CutControls``."""
    selected = state.get("Format.Format_Cut_SelectedItem")
    media_type = state.get("Format.Format_MediaType_SelectedItem")
    times = ("Hours", "Minutes", "Seconds", "Milliseconds")

    if selected == "No":
        state.set("Format.Format_CutStart_IsEnabled", False)
        state.set("Format.Format_CutEnd_IsEnabled", False)
        if media_type in ("Video", "Sequence"):
            for prefix in ("Format_CutStart", "Format_CutEnd"):
                state.set(f"Format.{prefix}_Hours_Text", "00")
                state.set(f"Format.{prefix}_Minutes_Text", "00")
                state.set(f"Format.{prefix}_Seconds_Text", "00")
                state.set(f"Format.{prefix}_Milliseconds_Text", "000")
        elif media_type == "Image":
            state.set("Format.Format_CutStart_Hours_Text", "00")
            state.set("Format.Format_CutStart_Minutes_Text", "00")
            state.set("Format.Format_CutStart_Seconds_Text", "00")
            state.set("Format.Format_CutStart_Milliseconds_Text", "000")
            for moment in times:
                state.set(f"Format.Format_CutEnd_{moment}_Text", "")

        state.set("Format.Format_FrameStart_IsEnabled", False)
        state.set("Format.Format_FrameEnd_IsEnabled", False)
        state.set("Format.Format_FrameStart_Text", "")
        state.set("Format.Format_FrameEnd_Text", "")

    elif selected == "Yes":
        if media_type == "Video":
            state.set("Format.Format_CutStart_IsEnabled", True)
            state.set("Format.Format_CutEnd_IsEnabled", True)
            state.set("Format.Format_FrameStart_IsEnabled", True)
            state.set("Format.Format_FrameEnd_IsEnabled", True)
        elif media_type == "Audio":
            state.set("Format.Format_CutStart_IsEnabled", True)
            state.set("Format.Format_CutEnd_IsEnabled", True)
            state.set("Format.Format_FrameStart_IsEnabled", False)
            state.set("Format.Format_FrameEnd_IsEnabled", False)
            state.set("Format.Format_FrameStart_Text", "")
            state.set("Format.Format_FrameEnd_Text", "")
        elif media_type == "Image":
            state.set("Format.Format_CutStart_IsEnabled", True)
            state.set("Format.Format_CutEnd_IsEnabled", False)
            for moment in times:
                state.set(f"Format.Format_CutEnd_{moment}_Text", "")
            state.set("Format.Format_FrameStart_IsEnabled", True)
            state.set("Format.Format_FrameEnd_IsEnabled", False)
            state.set("Format.Format_FrameEnd_Text", "")
        elif media_type == "Sequence":
            state.set("Format.Format_CutStart_IsEnabled", True)
            state.set("Format.Format_CutEnd_IsEnabled", True)
            state.set("Format.Format_FrameStart_IsEnabled", True)
            state.set("Format.Format_FrameEnd_IsEnabled", True)


def audio_stream_controls(state: AxiomState) -> None:
    """Port of ``Controls.Format.Controls.AudioStreamControls``."""
    container = state.get("Format.Format_Container_SelectedItem")
    video_codec = state.get("Video.Video_Codec_SelectedItem")
    audio_codec = state.get("Audio.Audio_Codec_SelectedItem")
    previous_container = state.flags.get("formatContainerPreviousItem") or ""
    previous_stream = _previous_flags(state).get("Audio_Stream_PreviousItem")

    if container == "webm":
        if video_codec == "VP8":
            state.set("Audio.Audio_Stream_SelectedItem", "1")
        if audio_codec == "None":
            state.set("Audio.Audio_Stream_SelectedItem", "none")

    elif container in ("mp4", "mkv", "mpg", "avi", "ogv"):
        if audio_codec == "None":
            state.set("Audio.Audio_Stream_SelectedItem", "none")
        else:
            if previous_container in (
                "webm",
                "mp3",
                "m4a",
                "ogg",
                "flac",
                "wav",
                "jpg",
                "png",
                "webp",
            ):
                state.set("Audio.Audio_Stream_SelectedItem", "all")
            if previous_stream == "none":
                state.set("Audio.Audio_Stream_SelectedItem", "all")
            state.flags["formatContainerPreviousItem"] = ""

    elif container in ("jpg", "png", "webp"):
        state.set("Audio.Audio_Stream_SelectedItem", "none")

    elif container in ("mp3", "m4a", "ogg", "flac", "wav"):
        if audio_codec == "None":
            state.set("Audio.Audio_Stream_SelectedItem", "none")
        else:
            if previous_container in (
                "webm",
                "mp4",
                "mkv",
                "mpg",
                "avi",
                "ogv",
                "jpg",
                "png",
                "webp",
            ):
                state.set("Audio.Audio_Stream_SelectedItem", "1")
            if previous_stream in ("none", "all"):
                state.set("Audio.Audio_Stream_SelectedItem", "1")
            state.flags["formatContainerPreviousItem"] = ""


# --------------------------------------------------------------------------------------
# Video: hardware acceleration
# --------------------------------------------------------------------------------------

HW_CODEC_FAMILIES = {
    "H264": {
        "software": {"x264", "H264 AMF", "H264 NVENC", "H264 QSV"},
        "AMD AMF": "H264 AMF",
        "NVIDIA NVENC": "H264 NVENC",
        "Intel QSV": "H264 QSV",
    },
    "HEVC": {
        "software": {"x265", "HEVC AMF", "HEVC NVENC", "HEVC QSV"},
        "AMD AMF": "HEVC AMF",
        "NVIDIA NVENC": "HEVC NVENC",
        "Intel QSV": "HEVC QSV",
    },
}

HW_CODEC_TRANSCODE = {
    "H264 AMF": "AMD AMF",
    "H264 NVENC": "NVIDIA NVENC",
    "H264 QSV": "Intel QSV",
    "HEVC AMF": "AMD AMF",
    "HEVC NVENC": "NVIDIA NVENC",
    "HEVC QSV": "Intel QSV",
}


def set_hwaccel_video_codecs(state: AxiomState) -> None:
    """Port of ``MainWindow.SetHWAccelVideoCodecs`` for the MP4/MKV lists."""
    container = str(state.get("Format.Format_Container_SelectedItem") or "")
    container_name = {"mp4": "MP4", "mkv": "MKV"}.get(container)
    if not container_name:
        return

    spec = CONTAINERS.get(container_name) or {}
    mode = str(state.get("Video.Video_HWAccel_SelectedItem") or "Off").casefold()
    if mode == "on":
        items = spec.get("video_HWAccel") or spec.get("video") or []
    elif mode in ("off", "auto"):
        items = spec.get("video") or []
    else:
        return
    if not items:
        return

    names = item_names(items)
    previous = str(state.get("Video.Video_Codec_SelectedItem") or "")
    software = {
        "H264 AMF": "x264",
        "H264 NVENC": "x264",
        "H264 QSV": "x264",
        "HEVC AMF": "x265",
        "HEVC NVENC": "x265",
        "HEVC QSV": "x265",
    }.get(previous, previous)

    if previous in names:
        selected = previous
    elif software in names:
        selected = software
    else:
        selected = names[0]

    state.set("Video.Video_Codec_Items", list(items))
    state.set("Video.Video_Codec_SelectedItem", selected)


def hwaccel_mode_controls(state: AxiomState) -> None:
    """Port of the ``cboHWAccel_SelectionChanged`` event chain."""
    mode = str(state.get("Video.Video_HWAccel_SelectedItem") or "Off").casefold()
    if mode == "auto":
        state.set("Video.Video_HWAccel_Decode_IsEnabled", False)
        state.set("Video.Video_HWAccel_Decode_SelectedItem", "auto")
        state.set("Video.Video_HWAccel_Transcode_IsEnabled", False)
        state.set("Video.Video_HWAccel_Transcode_SelectedItem", "auto")
    elif mode == "on":
        state.set("Video.Video_HWAccel_Decode_IsEnabled", True)
        state.set("Video.Video_HWAccel_Decode_SelectedItem", "auto")
        state.set("Video.Video_HWAccel_Transcode_IsEnabled", True)
        state.set("Video.Video_HWAccel_Transcode_SelectedItem", "auto")
    elif mode == "off":
        state.set("Video.Video_HWAccel_Decode_IsEnabled", False)
        state.set("Video.Video_HWAccel_Decode_SelectedItem", "off")
        state.set("Video.Video_HWAccel_Transcode_IsEnabled", False)
        state.set("Video.Video_HWAccel_Transcode_SelectedItem", "off")
    else:
        state.set("Video.Video_HWAccel_Decode_IsEnabled", True)
        state.set("Video.Video_HWAccel_Decode_SelectedItem", "off")
        state.set("Video.Video_HWAccel_Transcode_IsEnabled", True)
        state.set("Video.Video_HWAccel_Transcode_SelectedItem", "off")

    set_hwaccel_video_codecs(state)


def select_hwaccel_video_codec(state: AxiomState) -> None:
    """Port of ``MainWindow.SelectHWAccelVideoCodec``."""
    codec = str(state.get("Video.Video_Codec_SelectedItem") or "")
    transcode = str(
        state.get("Video.Video_HWAccel_Transcode_SelectedItem") or "auto"
    )
    for family_name, family in HW_CODEC_FAMILIES.items():
        if codec not in family["software"]:
            continue
        if transcode in family:
            state.set("Video.Video_Codec_SelectedItem", family[transcode])
        else:
            default = "x264" if family_name == "H264" else "x265"
            state.set("Video.Video_Codec_SelectedItem", default)
        return


def change_hwaccel_transcode(state: AxiomState) -> None:
    """Port of ``MainWindow.ChangeHWAccelTranscode``."""
    mode = str(state.get("Video.Video_HWAccel_SelectedItem") or "Off").casefold()
    if mode != "on":
        return
    codec = str(state.get("Video.Video_Codec_SelectedItem") or "")
    transcode = HW_CODEC_TRANSCODE.get(codec)
    if transcode:
        state.set("Video.Video_HWAccel_Transcode_SelectedItem", transcode)


# --------------------------------------------------------------------------------------
# Video: quality / bitrate / optimize
# --------------------------------------------------------------------------------------

# The original tests these codec names before deciding whether VBR is available.
VBR_DISABLED_CODECS = {
    "VP8",
    "x264",
    "H264_AMF",
    "H264_NVENC",
    "H264_QSV",
    "JPEG",
    "AV1",
    "FFV1",
    "MagicYUV",
    "HuffYUV",
    "Copy",
    "None",
}

OPTIMIZE_CODECS = {
    "x264",
    "x265",
    "H264 AMF",
    "HEVC AMF",
    "H264 NVENC",
    "HEVC NVENC",
    "H264 QSV",
    "HEVC QSV",
}

# The C# code stores the guard in a lower-camel local (``bool? codec_IsEnabled``)
# while the codec row uses the property name (``Codec``).  ``size`` is the guard for
# the ``Scale`` row, which is another place the two names differ.
VIDEO_GUARD_PROP = {
    "encodeSpeed": "EncodeSpeed",
    "codec": "Codec",
    "hwAccel": "HWAccel",
    "vbr": "VBR",
    "pixelFormat": "PixelFormat",
    "fps": "FPS",
    "speed": "Speed",
    "vsync": "Vsync",
    "optimize": "Optimize",
    "size": "Scale",
    "scalingAlgorithm": "Scaling",
    "crop": "Crop",
    "colorRange": "ColorRange",
    "colorSpace": "ColorSpace",
    "colorPrimaries": "ColorPrimaries",
    "colorTransferCharacteristics": "ColorTransferChar",
    "colorMatrix": "ColorMatrix",
    "subtitleCodec": "SubtitleCodec",
    "subtitleStream": "SubtitleStream",
}


def _set(state: AxiomState, field: str, value: Any) -> None:
    state.set(f"Video.{field}", value)


VIDEO_FILTER_COMMON = (
    "FilterVideo_DropFrames_IsEnabled",
    "FilterVideo_Deinterlace_IsEnabled",
    "FilterVideo_Deblock_IsEnabled",
    "FilterVideo_Deflicker_IsEnabled",
    "FilterVideo_Denoise_IsEnabled",
    "FilterVideo_Deband_IsEnabled",
    "FilterVideo_Deshake_IsEnabled",
    "FilterVideo_Dejudder_IsEnabled",
    "FilterVideo_Flip_IsEnabled",
    "FilterVideo_Rotate_IsEnabled",
    "FilterVideo_EQ_Brightness_IsEnabled",
    "FilterVideo_EQ_Contrast_IsEnabled",
    "FilterVideo_EQ_Saturation_IsEnabled",
    "FilterVideo_EQ_Gamma_IsEnabled",
    "FilterVideo_SelectiveColor_IsEnabled",
    "FilterVideo_SelectiveColor_Correction_Method_IsEnabled",
)

SELECTIVE_COLORS = (
    "Reds",
    "Yellows",
    "Greens",
    "Cyans",
    "Blues",
    "Magentas",
    "Whites",
    "Neutrals",
    "Blacks",
)


def _video_filters_enable_all(state: AxiomState) -> None:
    for field in VIDEO_FILTER_COMMON:
        state.set(f"FilterVideo.{field}", True)
    for color in SELECTIVE_COLORS:
        for channel in ("Cyan", "Magenta", "Yellow"):
            state.set(
                f"FilterVideo.FilterVideo_SelectiveColor_{color}_{channel}_IsEnabled",
                True,
            )


def _video_filters_disable_all(state: AxiomState) -> None:
    for field in VIDEO_FILTER_COMMON:
        state.set(f"FilterVideo.{field}", False)
    # The original only clears the Reds block; the other colours are unreachable
    # while Reds is disabled, so their flags keep their previous values.
    for channel in ("Cyan", "Magenta", "Yellow"):
        state.set(
            f"FilterVideo.FilterVideo_SelectiveColor_Reds_{channel}_IsEnabled", False
        )


def _video_filters_select_defaults(state: AxiomState) -> None:
    state.set("FilterVideo.FilterVideo_DropFrames_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Deinterlace_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Deblock_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Deflicker_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Denoise_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Deband_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Deshake_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Dejudder_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Flip_SelectedItem", "disabled")
    state.set("FilterVideo.FilterVideo_Rotate_SelectedItem", "disabled")
    for field in (
        "FilterVideo_EQ_Brightness_Value",
        "FilterVideo_EQ_Contrast_Value",
        "FilterVideo_EQ_Saturation_Value",
        "FilterVideo_EQ_Gamma_Value",
    ):
        state.set(f"FilterVideo.{field}", 0)
    state.set("FilterVideo.FilterVideo_SelectiveColor_SelectedItem", "Reds")
    state.set(
        "FilterVideo.FilterVideo_SelectiveColor_Correction_Method_SelectedItem",
        "relative",
    )
    for color in SELECTIVE_COLORS:
        for channel in ("Cyan", "Magenta", "Yellow"):
            state.set(
                f"FilterVideo.FilterVideo_SelectiveColor_{color}_{channel}_Value", 0
            )


def video_quality_controls(state: AxiomState) -> None:
    """Port of Controls.Video.Controls.QualityControls."""
    quality = state.get("Video.Video_Quality_SelectedItem")
    codec = state.get("Video.Video_Codec_SelectedItem")

    if quality == "Auto":
        _set(state, "Video_Pass_IsEnabled", False)
        _set(state, "Video_CRF_IsEnabled", False)
        _set(state, "Video_CRF_Text", "")
        _set(state, "Video_BitRate_IsEnabled", False)
        _set(state, "Video_BitRate_Text", "")
        _set(state, "Video_VBR_IsEnabled", False)
        _set(state, "Video_VBR_IsChecked", False)
        _set(state, "Video_MinRate_IsEnabled", False)
        _set(state, "Video_MinRate_Text", "")
        _set(state, "Video_MaxRate_IsEnabled", False)
        _set(state, "Video_MaxRate_Text", "")
        _set(state, "Video_BufSize_IsEnabled", False)
        _set(state, "Video_BufSize_Text", "")
        _set(state, "Video_Scale_IsEnabled", True)
        return

    if quality == "Lossless":
        if codec in ("H264 NVENC", "HEVC NVENC"):
            _set(state, "Video_EncodeSpeed_SelectedItem", "Lossless")
        _set(state, "Video_Pass_IsEnabled", False)
        _set(state, "Video_CRF_IsEnabled", False)
        _set(state, "Video_BitRate_IsEnabled", False)
        _set(state, "Video_VBR_IsEnabled", False)
        _set(state, "Video_MinRate_IsEnabled", False)
        _set(state, "Video_MaxRate_IsEnabled", False)
        _set(state, "Video_BufSize_IsEnabled", False)
        _set(state, "Video_Scale_IsEnabled", True)
        return

    if quality == "Custom":
        _set(state, "Video_Pass_IsEnabled", True)
        _set(state, "Video_CRF_IsEnabled", True)
        _set(state, "Video_BitRate_IsEnabled", True)
        _set(state, "Video_VBR_IsEnabled", True)
        _set(state, "Video_MinRate_IsEnabled", True)
        _set(state, "Video_MaxRate_IsEnabled", True)
        _set(state, "Video_BufSize_IsEnabled", True)
        _set(state, "Video_Scale_IsEnabled", True)
        return

    if quality == "None":
        _set(state, "Video_Pass_IsEnabled", False)
        _set(state, "Video_CRF_IsEnabled", False)
        _set(state, "Video_BitRate_IsEnabled", False)
        _set(state, "Video_VBR_IsEnabled", False)
        _set(state, "Video_MinRate_IsEnabled", False)
        _set(state, "Video_MaxRate_IsEnabled", False)
        _set(state, "Video_BufSize_IsEnabled", False)
        _set(state, "Video_Scale_IsEnabled", False)
        return

    # Every other quality (the named presets)
    _set(state, "Video_Pass_IsEnabled", True)
    _set(state, "Video_CRF_IsEnabled", False)
    _set(state, "Video_BitRate_IsEnabled", False)
    _set(state, "Video_VBR_IsEnabled", codec not in VBR_DISABLED_CODECS)
    _set(state, "Video_MinRate_IsEnabled", False)
    _set(state, "Video_MaxRate_IsEnabled", False)
    _set(state, "Video_BufSize_IsEnabled", False)
    _set(state, "Video_Scale_IsEnabled", True)


def _quality_row(state: AxiomState) -> Dict[str, Any]:
    items = state.get("Video.Video_Quality_Items") or []
    selected = state.get("Video.Video_Quality_SelectedItem")
    for item in items:
        if isinstance(item, Mapping) and item.get("Name") == selected:
            return dict(item)
    return {}


def video_bitrate_display(state: AxiomState) -> None:
    """Port of Controls.Video.Controls.VideoBitRateDisplay."""
    quality = state.get("Video.Video_Quality_SelectedItem")
    if not quality or quality in ("Auto", "Lossless", "Custom", "None"):
        return

    selected_pass = state.get("Video.Video_Pass_SelectedItem")
    row = _quality_row(state)

    if selected_pass == "auto":
        for field in (
            "Video_CRF_Text",
            "Video_BitRate_Text",
            "Video_MinRate_Text",
            "Video_MaxRate_Text",
            "Video_BufSize_Text",
        ):
            _set(state, field, "")
        return

    if selected_pass == "CRF":
        _set(state, "Video_BitRate_Text", row.get("Video_CRF_BitRate"))
        _set(state, "Video_CRF_Text", row.get("CRF"))
        _set(state, "Video_MinRate_Text", row.get("MinRate"))
        _set(state, "Video_MaxRate_Text", row.get("MaxRate"))
        _set(state, "Video_BufSize_Text", row.get("BufSize"))
        return

    if selected_pass in ("1 Pass", "2 Pass"):
        _set(state, "Video_CRF_Text", "")
        if state.get("Video.Video_VBR_IsChecked") is True:
            _set(state, "Video_BitRate_Text", row.get("VBR"))
        else:
            _set(state, "Video_BitRate_Text", row.get("CBR"))
        _set(state, "Video_MinRate_Text", row.get("MinRate"))
        _set(state, "Video_MaxRate_Text", row.get("MaxRate"))
        _set(state, "Video_BufSize_Text", row.get("BufSize"))


def video_optimize_controls(state: AxiomState) -> None:
    """Port of Controls.Video.Controls.OptimizeControls."""
    codec = state.get("Video.Video_Codec_SelectedItem")
    optimize = state.get("Video.Video_Optimize_SelectedItem")

    if codec in OPTIMIZE_CODECS:
        if optimize == "Custom":
            _set(state, "Video_Optimize_Tune_IsEnabled", True)
            _set(state, "Video_Optimize_Profile_IsEnabled", True)
            _set(state, "Video_Optimize_Level_IsEnabled", True)
        else:
            _set(state, "Video_Optimize_Tune_IsEnabled", False)
            _set(state, "Video_Optimize_Profile_IsEnabled", False)
            _set(state, "Video_Optimize_Level_IsEnabled", False)
    else:
        _set(state, "Video_Optimize_Tune_IsEnabled", False)
        _set(state, "Video_Optimize_Profile_IsEnabled", False)
        _set(state, "Video_Optimize_Level_IsEnabled", False)

    if optimize != "Custom":
        items = state.get("Video.Video_Optimize_Items") or []
        row: Dict[str, Any] = {}
        for item in items:
            if isinstance(item, Mapping) and item.get("Name") == optimize:
                row = dict(item)
                break
        _set(state, "Video_Optimize_Tune_SelectedItem", row.get("Tune"))
        _set(state, "Video_Optimize_Profile_SelectedItem", row.get("Profile"))
        _set(state, "Video_Optimize_Level_SelectedItem", row.get("Level"))

    # Special rule: coming from the webm container the original resets Optimize to None.
    if state.flags.get("formatContainerPreviousItem") == "webm":
        _set(state, "Video_Optimize_SelectedItem", "None")


def pixel_format_controls(state: AxiomState) -> None:
    """Port of ``Controls.Video.Controls.PixelFormatControls``."""
    media_type = state.get("Format.Format_MediaType_SelectedItem")
    codec = state.get("Video.Video_Codec_SelectedItem")
    if media_type not in ("Video", "Image", "Sequence") or not codec:
        return
    if not codecs.has("video", str(codec)):
        return

    rows = codecs.table("video", str(codec), "controls_Selected")
    row = dict(rows[0]) if rows else {}
    quality = state.get("Video.Video_Quality_SelectedItem")
    value = row.get("PixelFormat_Lossless" if quality == "Lossless" else "PixelFormat")
    if value:
        state.set("Video.Video_PixelFormat_SelectedItem", value)


def encoding_pass_controls(state: AxiomState) -> None:
    """Port of ``Controls.Video.Controls.EncodingPassControls``."""
    codec = state.get("Video.Video_Codec_SelectedItem")
    if not codec:
        return
    codecs.apply_quality_pass(state, "video", str(codec))
    if state.get("Video.Video_Quality_SelectedItem") == "Custom":
        selected_pass = state.get("Video.Video_Pass_SelectedItem")
        if selected_pass == "CRF":
            state.set("Video.Video_CRF_IsEnabled", True)
        elif selected_pass in ("1 Pass", "2 Pass", "none", "auto"):
            state.set("Video.Video_CRF_IsEnabled", False)


# --------------------------------------------------------------------------------------
# Audio
# --------------------------------------------------------------------------------------

AUDIO_ENABLED_FIELDS = {
    "Codec": "Audio_Codec_IsEnabled",
    "Stream": "Audio_Stream_IsEnabled",
    "Channel": "Audio_Channel_IsEnabled",
    "Quality": "Audio_Quality_IsEnabled",
    "CompressionLevel": "Audio_CompressionLevel_IsEnabled",
    "VBR": "Audio_VBR_IsEnabled",
    "SampleRate": "Audio_SampleRate_IsEnabled",
    "BitDepth": "Audio_BitDepth_IsEnabled",
    "Volume": "Audio_Volume_IsEnabled",
    "HardLimiter": "Audio_HardLimiter_IsEnabled",
}

AUDIO_ITEMS = (
    ("channel", "Audio_Channel_Items"),
    ("quality", "Audio_Quality_Items"),
    ("compressionLevel", "Audio_CompressionLevel_Items"),
    ("sampleRate", "Audio_SampleRate_Items"),
    ("bitDepth", "Audio_BitDepth_Items"),
)

AUDIO_PREVIOUS = (
    ("Stream", "Audio_Stream_SelectedItem", "Audio_Stream_PreviousItem", "Audio_Stream_Items"),
    ("Channel", "Audio_Channel_SelectedItem", "Audio_Channel_PreviousItem", "Audio_Channel_Items"),
    ("Quality", "Audio_Quality_SelectedItem", "Audio_Quality_PreviousItem", "Audio_Quality_Items"),
    (
        "CompressionLevel",
        "Audio_CompressionLevel_SelectedItem",
        "Audio_CompressionLevel_PreviousItem",
        "Audio_CompressionLevel_Items",
    ),
    ("SampleRate", "Audio_SampleRate_SelectedItem", "Audio_SampleRate_PreviousItem", "Audio_SampleRate_Items"),
    ("BitDepth", "Audio_BitDepth_SelectedItem", "Audio_BitDepth_PreviousItem", "Audio_BitDepth_Items"),
)


def _audio_filters_enable_all(state: AxiomState) -> None:
    for field in (
        "FilterAudio_Lowpass_IsEnabled",
        "FilterAudio_Highpass_IsEnabled",
        "FilterAudio_Contrast_IsEnabled",
        "FilterAudio_ExtraStereo_IsEnabled",
        "FilterAudio_Headphones_IsEnabled",
        "FilterAudio_Tempo_IsEnabled",
    ):
        state.set(f"FilterAudio.{field}", True)


def _audio_filters_disable_all(state: AxiomState) -> None:
    for field in (
        "FilterAudio_Lowpass_IsEnabled",
        "FilterAudio_Highpass_IsEnabled",
        "FilterAudio_Contrast_IsEnabled",
        "FilterAudio_ExtraStereo_IsEnabled",
        "FilterAudio_Headphones_IsEnabled",
        "FilterAudio_Tempo_IsEnabled",
    ):
        state.set(f"FilterAudio.{field}", False)


def _audio_filters_select_defaults(state: AxiomState) -> None:
    state.set("FilterAudio.FilterAudio_Lowpass_SelectedItem", "disabled")
    state.set("FilterAudio.FilterAudio_Highpass_SelectedItem", "disabled")
    state.set("FilterAudio.FilterAudio_Contrast_Value", 0)
    state.set("FilterAudio.FilterAudio_ExtraStereo_Value", 0)
    state.set("FilterAudio.FilterAudio_Headphones_SelectedItem", "disabled")
    state.set("FilterAudio.FilterAudio_Tempo_Value", 100)


def audio_codec_controls(state: AxiomState, name: str) -> None:
    """Port of ``Controls.Audio.Controls.CodecControls``."""
    if not name or not name.strip():
        return
    if not codecs.has("audio", name):
        raise KeyError(f"unknown audio codec: {name}")

    rows = codecs.table("audio", name, "codec")
    codec = str(rows[0].get("Codec", "")) if rows else ""
    parameters = str(rows[0].get("Parameters", "")) if rows else ""
    state.set(
        "Audio.Audio_Codec",
        " ".join(part for part in ("-c:a", codec, parameters) if part),
    )

    previous = _previous_flags(state)
    for _, field, previous_key, _ in AUDIO_PREVIOUS:
        current = state.get(f"Audio.{field}")
        if save_previous_item_cond(current):
            previous[previous_key] = current
    state.flags["audioVBPreviousChecked"] = state.get("Audio.Audio_VBR_IsChecked")

    for section, field in AUDIO_ITEMS:
        if codecs.table("audio", name, section):
            state.set(f"Audio.{field}", codecs.table("audio", name, section))

    enabled_rows = codecs.table("audio", name, "controls_Enabled")
    enabled = dict(enabled_rows[0]) if enabled_rows else {}
    for prop, field in AUDIO_ENABLED_FIELDS.items():
        value = enabled.get(prop)
        state.set(f"Audio.{field}", True if value is None else bool(value))

    if name in ("Copy", "None"):
        _audio_filters_disable_all(state)
    else:
        _audio_filters_enable_all(state)

    selected_rows = codecs.table("audio", name, "controls_Selected")
    selected = dict(selected_rows[0]) if selected_rows else {}
    for prop, field, previous_key, items_field in AUDIO_PREVIOUS:
        value = selected.get(prop)
        if value:
            state.set(f"Audio.{field}", value)
        else:
            previous_value = previous.pop(previous_key, None)
            chosen = selected_item(state.get(f"Audio.{items_field}") or [], previous_value)
            if chosen is not None:
                state.set(f"Audio.{field}", chosen)

    if name in ("Copy", "None"):
        _audio_filters_select_defaults(state)

    # Faithful to the original: the VBR checkbox reads the *Stream* flag from the
    # enabled row (a copy/paste slip in Axiom), so keep that guard exactly.
    if state.get("Audio.Audio_VBR_IsEnabled") is True:
        vbr = enabled.get("Stream")
        state.set("Audio.Audio_VBR_IsChecked", True if vbr is None else bool(vbr))
    else:
        state.set("Audio.Audio_VBR_IsChecked", False)


def _audio_quality_row(state: AxiomState) -> Dict[str, Any]:
    items = state.get("Audio.Audio_Quality_Items") or []
    selected = state.get("Audio.Audio_Quality_SelectedItem")
    for item in items:
        if isinstance(item, Mapping) and item.get("Name") == selected:
            return dict(item)
    return {}


def audio_quality_controls(state: AxiomState) -> None:
    """Port of ``Controls.Audio.Controls.QualityControls``."""
    quality = state.get("Audio.Audio_Quality_SelectedItem")
    if quality == "Custom":
        state.set("Audio.Audio_BitRate_IsEnabled", True)
        state.set("Audio.Audio_BitRate_Text", "")
    elif quality == "Auto":
        state.set("Audio.Audio_BitRate_IsEnabled", False)
        state.set("Audio.Audio_BitRate_Text", "")
    else:
        state.set("Audio.Audio_BitRate_IsEnabled", False)


def audio_bitrate_display(state: AxiomState) -> None:
    """Port of ``Controls.Audio.Controls.AudioBitRateDisplay``."""
    quality = state.get("Audio.Audio_Quality_SelectedItem")
    active = quality not in (None, "", "None", "Auto", "Lossless", "Custom", "Mute")
    if active:
        row = _audio_quality_row(state)
        if state.get("Audio.Audio_VBR_IsChecked") is True:
            state.set("Audio.Audio_BitRate_Text", row.get("VBR"))
        else:
            state.set("Audio.Audio_BitRate_Text", row.get("CBR"))
    elif quality in (None, "", "None", "Auto", "Lossless", "Mute"):
        state.set("Audio.Audio_BitRate_Text", "")


# --------------------------------------------------------------------------------------
# Subtitles
# --------------------------------------------------------------------------------------


def subtitle_codec_controls(state: AxiomState, name: str) -> None:
    """Port of ``Controls.Subtitles.Controls.CodecControls``."""
    if not name or not name.strip():
        return
    if not codecs.has("subtitle", name):
        raise KeyError(f"unknown subtitle codec: {name}")

    rows = codecs.table("subtitle", name, "codec")
    codec = str(rows[0].get("Codec", "")) if rows else ""
    parameters = str(rows[0].get("Parameters", "")) if rows else ""
    parts = [codec, parameters]
    if name != "Burn":
        parts.insert(0, "-c:s")
    state.set(
        "Subtitle.Subtitle_Codec",
        " ".join(part for part in parts if part),
    )

    state.set("Subtitle.Subtitle_Stream_Items", codecs.table("subtitle", name, "stream"))
    state.set("Subtitle.Subtitle_Codec_IsEnabled", True)
    state.set("Subtitle.Subtitle_Stream_IsEnabled", True)

    selected_rows = codecs.table("subtitle", name, "controls_Selected")
    selected = dict(selected_rows[0]) if selected_rows else {}
    stream = selected.get("Stream")
    if stream:
        state.set("Subtitle.Subtitle_Stream_SelectedItem", stream)

    if name == "None":
        state.set("Subtitle.Subtitle_Stream_SelectedItem", "none")
        state.set("Subtitle.Subtitle_Stream_IsEnabled", False)
    elif name == "Burn":
        state.set("Subtitle.Subtitle_Stream_SelectedItem", "external")
        state.set("Subtitle.Subtitle_Stream_IsEnabled", True)
    else:
        state.set("Subtitle.Subtitle_Stream_IsEnabled", True)

