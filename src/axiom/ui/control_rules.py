"""Small, testable rules shared by the Qt widgets."""

from __future__ import annotations

import re


_ENABLE_SUFFIX = re.compile(r"_(?:SelectedItem|Text|Value|IsChecked|IsExpanded)$")


def enabled_key(state_key: str) -> str | None:
    """Map a bound field to the ViewModel flag that controls its widget."""
    if "." not in state_key:
        return None
    group, field = state_key.split(".", 1)
    if field.startswith("_"):
        return None
    match = _ENABLE_SUFFIX.search(field)
    if not match:
        return None
    return f"{group}.{field[: match.start()]}_IsEnabled"


def structural_scope(state_key: str) -> str:
    """Return which control-resolution chain a changed field triggers."""
    group, _, field = state_key.partition(".")
    if state_key == "Format.Format_Container_SelectedItem":
        return "container"
    if state_key == "Format.Format_MediaType_SelectedItem":
        return "media_type"
    if state_key == "Format.Format_Cut_SelectedItem":
        return "cut"
    if group == "Video":
        if field == "Video_Codec_SelectedItem":
            return "video_codec"
        if field == "Video_HWAccel_SelectedItem":
            return "hardware_mode"
        if field == "Video_HWAccel_Transcode_SelectedItem":
            return "hardware_transcode"
        if field in {
            "Video_Quality_SelectedItem",
            "Video_Pass_SelectedItem",
            "Video_VBR_IsChecked",
        }:
            return "video_quality"
        if field == "Video_Optimize_SelectedItem":
            return "video_optimize"
        if field == "Video_Scale_SelectedItem":
            return "video_scale"
    if group == "Audio":
        if field == "Audio_Codec_SelectedItem":
            return "audio_codec"
        if field in {
            "Audio_Quality_SelectedItem",
            "Audio_VBR_IsChecked",
        }:
            return "audio_quality"
    if group == "Subtitle" and field == "Subtitle_Codec_SelectedItem":
        return "subtitle"
    if group == "Configure" and field == "Shell_SelectedItem":
        return "settings"
    return ""
