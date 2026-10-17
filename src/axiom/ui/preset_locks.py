"""Controls that a built-in or user preset owns.

Axiom presets model a complete encoding profile.  Once one is selected, the
identity of that profile (container, codecs, quality, stream selection and
hardware path) is fixed until the user explicitly unlocks editing.  Keeping the
list here makes the Qt layer declarative and easy to test without duplicating
the reasons in every widget builder.
"""

from __future__ import annotations


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
