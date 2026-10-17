"""Controls that a built-in or user preset owns.

Axiom presets model a complete encoding profile.  Once one is selected, the
identity of that profile (container, codecs, quality, stream selection and
hardware path) is fixed until the user explicitly unlocks editing.  Keeping the
list here makes the Qt layer declarative and easy to test without duplicating
the reasons in every widget builder.
"""

from __future__ import annotations

from typing import Any


PRESET_LOCK_REASONS = {
    "Format.Format_Container_SelectedItem": (
        "The container is fixed by preset '{preset}'."
    ),
    "Video.Video_Codec_SelectedItem": (
        "The video codec is fixed by preset '{preset}'."
    ),
    "Video.Video_HWAccel_SelectedItem": (
        "The hardware-acceleration path is fixed by preset '{preset}'."
    ),
    "Video.Video_HWAccel_Decode_SelectedItem": (
        "HW decode follows the hardware mode fixed by preset '{preset}'."
    ),
    "Video.Video_HWAccel_Transcode_SelectedItem": (
        "HW transcode follows the hardware mode fixed by preset '{preset}'."
    ),
    "Video.Video_Quality_SelectedItem": (
        "The video quality level is fixed by preset '{preset}'."
    ),
    "Video.Video_Pass_SelectedItem": (
        "The rate-control pass is fixed by preset '{preset}'."
    ),
    "Video.Video_VBR_IsChecked": (
        "The rate-control mode is fixed by preset '{preset}'."
    ),
    "Video.Video_EncodeSpeed_SelectedItem": (
        "The encoder speed preset is fixed by preset '{preset}'."
    ),
    "Video.Video_PixelFormat_SelectedItem": (
        "The pixel format is fixed by preset '{preset}'."
    ),
    "Video.Video_Optimize_SelectedItem": (
        "The optimization mode is fixed by preset '{preset}'."
    ),
    "Video.Video_Optimize_Tune_SelectedItem": (
        "The encoder tune is fixed by preset '{preset}'."
    ),
    "Video.Video_Optimize_Profile_SelectedItem": (
        "The encoder profile is fixed by preset '{preset}'."
    ),
    "Video.Video_Optimize_Level_SelectedItem": (
        "The encoder level is fixed by preset '{preset}'."
    ),
    "Video.Video_Scale_SelectedItem": (
        "The output size is fixed by preset '{preset}'."
    ),
    "Video.Video_FPS_SelectedItem": (
        "The frame rate is fixed by preset '{preset}'."
    ),
    "Audio.Audio_Codec_SelectedItem": (
        "The audio codec is fixed by preset '{preset}'."
    ),
    "Audio.Audio_Quality_SelectedItem": (
        "The audio quality is fixed by preset '{preset}'."
    ),
    "Audio.Audio_VBR_IsChecked": (
        "The audio rate-control mode is fixed by preset '{preset}'."
    ),
    "Audio.Audio_Stream_SelectedItem": (
        "The audio stream selection is fixed by preset '{preset}'."
    ),
    "Audio.Audio_Channel_SelectedItem": (
        "The audio channel layout is fixed by preset '{preset}'."
    ),
    "Audio.Audio_SampleRate_SelectedItem": (
        "The audio sample rate is fixed by preset '{preset}'."
    ),
    "Audio.Audio_BitDepth_SelectedItem": (
        "The audio bit depth is fixed by preset '{preset}'."
    ),
    "Subtitle.Subtitle_Codec_SelectedItem": (
        "The subtitle codec is fixed by preset '{preset}'."
    ),
    "Subtitle.Subtitle_Stream_SelectedItem": (
        "The subtitle stream selection is fixed by preset '{preset}'."
    ),
}

PRESET_LOCKED_KEYS = frozenset(PRESET_LOCK_REASONS)

PARAMETER_PRESET_KEYS = (
    "Video.Video_Quality_SelectedItem",
    "Video.Video_Optimize_SelectedItem",
    "Video.Video_Scale_SelectedItem",
    "Audio.Audio_Quality_SelectedItem",
)


def preset_lock_reason(key: str, preset_name: str) -> str:
    """Return the hover explanation for a locked control."""

    reason = PRESET_LOCK_REASONS.get(key)
    if not reason:
        return ""
    return (
        reason.format(preset=preset_name)
        + " Use Unlock next to the preset list to edit it, or select 'Preset' "
        "to return to manual defaults."
    )


VIDEO_QUALITY_MANAGED = {
    "Video.Video_CRF_Text",
    "Video.Video_BitRate_Text",
    "Video.Video_MinRate_Text",
    "Video.Video_MaxRate_Text",
    "Video.Video_BufSize_Text",
    "Video.Video_VBR_IsChecked",
    "Video.Video_Pass_SelectedItem",
}

VIDEO_OPTIMIZE_MANAGED = {
    "Video.Video_Optimize_Tune_SelectedItem",
    "Video.Video_Optimize_Profile_SelectedItem",
    "Video.Video_Optimize_Level_SelectedItem",
}

VIDEO_SIZE_MANAGED = {
    "Video.Video_Width_Text",
    "Video.Video_Height_Text",
    "Video.Video_ScalingAlgorithm_SelectedItem",
}

AUDIO_QUALITY_MANAGED = {
    "Audio.Audio_BitRate_Text",
    "Audio.Audio_VBR_IsChecked",
}

HARDWARE_MANAGED = {
    "Video.Video_HWAccel_Decode_SelectedItem",
    "Video.Video_HWAccel_Transcode_SelectedItem",
}

CUT_MANAGED_PREFIXES = (
    "Format.Format_CutStart_",
    "Format.Format_CutEnd_",
    "Format.Format_FrameStart_",
    "Format.Format_FrameEnd_",
)


def parameter_preset_reason(state: Any, key: str) -> str | None:
    """Explain a control disabled by a parameter-level preset or mode."""

    if key in VIDEO_QUALITY_MANAGED:
        codec = state.get("Video.Video_Codec_SelectedItem")
        if codec in ("None", "Copy"):
            return f"Video encoding is disabled by codec '{codec}'."
        quality = state.get("Video.Video_Quality_SelectedItem")
        if quality:
            return f"Managed by video quality preset '{quality}'."
    if key in VIDEO_OPTIMIZE_MANAGED:
        optimize = state.get("Video.Video_Optimize_SelectedItem")
        if optimize not in (None, "None", "Custom"):
            return f"Managed by optimization preset '{optimize}'."
    if key in VIDEO_SIZE_MANAGED:
        scale = state.get("Video.Video_Scale_SelectedItem")
        if scale not in (None, "Source", "Custom"):
            return f"Set by size preset '{scale}'."
        if key == "Video.Video_ScalingAlgorithm_SelectedItem":
            return "Scaling algorithm is unavailable for the Source size preset."
        return "Size preset 'Source' keeps the input dimensions."
    if key in AUDIO_QUALITY_MANAGED:
        codec = state.get("Audio.Audio_Codec_SelectedItem")
        if codec in ("None", "Copy"):
            return f"Audio encoding is disabled by codec '{codec}'."
        quality = state.get("Audio.Audio_Quality_SelectedItem")
        if quality not in (None, "Custom", "None", "Mute"):
            return f"Managed by audio quality preset '{quality}'."
    if key in HARDWARE_MANAGED:
        mode = state.get("Video.Video_HWAccel_SelectedItem") or "Off"
        return f"Hardware acceleration is set to '{mode}'."
    if key.startswith(CUT_MANAGED_PREFIXES):
        cut = state.get("Format.Format_Cut_SelectedItem") or "No"
        return f"Disabled because Cut is set to '{cut}'."
    if key == "Subtitle.Subtitle_Stream_SelectedItem":
        codec = state.get("Subtitle.Subtitle_Codec_SelectedItem") or "None"
        return f"Managed by subtitle codec '{codec}'."
    if key == "Audio.Audio_Stream_SelectedItem":
        codec = state.get("Audio.Audio_Codec_SelectedItem") or "None"
        if codec in ("None", "Copy"):
            return f"Managed by audio codec '{codec}'."
    return None


def active_parameter_presets(state: Any) -> list[str]:
    """Named parameter presets that currently manage dependent controls."""

    names: list[str] = []
    quality = state.get("Video.Video_Quality_SelectedItem")
    if quality not in (None, "Auto", "Custom", "None"):
        names.append(f"video quality '{quality}'")
    optimize = state.get("Video.Video_Optimize_SelectedItem")
    if optimize not in (None, "None", "Custom"):
        names.append(f"optimization '{optimize}'")
    scale = state.get("Video.Video_Scale_SelectedItem")
    if scale not in (None, "Source", "Custom"):
        names.append(f"size '{scale}'")
    audio_quality = state.get("Audio.Audio_Quality_SelectedItem")
    if audio_quality not in (None, "Auto", "Custom", "None", "Mute"):
        names.append(f"audio quality '{audio_quality}'")
    return names
