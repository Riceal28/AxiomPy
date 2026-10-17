"""Audio filter chain ported from ``Filters/AudioFilters.cs``."""

from __future__ import annotations

from ..state import AxiomState
from ..text import normalize_value
from .context import BuildContext
from .filters_video import number_text, rounded


def _float(state: AxiomState, key: str) -> float:
    try:
        return float(state.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _volume(state: AxiomState) -> str:
    codec = state.get("Audio.Audio_Codec_SelectedItem")
    if not str(codec or "").strip():
        return ""
    text = str(state.get("Audio.Audio_Volume_Text") or "")
    if text in ("100%", "100") or not text.strip():
        return ""
    try:
        decimal = float(text.strip()) * 0.01
    except ValueError:
        return ""
    return "volume=" + rounded(decimal, 2)


def _hard_limiter(state: AxiomState) -> str:
    value = _float(state, "Audio.Audio_HardLimiter_Value")
    if not state.get("Audio.Audio_HardLimiter_IsEnabled") or value == 0:
        return ""

    limit = ""
    if value > -4:
        limit = rounded(normalize_value(value, -3, -0.1, 0.7, 0.99, 0.845), 4)
    elif value <= -4 and value >= -7:
        limit = rounded(normalize_value(value, -7, -4, 0.45, 0.65, 0.55), 4)
    elif value <= -8 and value >= -10:
        limit = rounded(normalize_value(value, -10, -8, 0.3, 0.4, 0.35), 4)
    elif value <= -11 and value >= -16:
        limit = rounded(normalize_value(value, -16, -11, 0.15, 0.275, 0.2125), 4)
    elif value <= -17 and value >= -19:
        limit = rounded(normalize_value(value, -19, -17, 0.1, 0.135, 0.1175), 4)
    elif value <= -20:
        limit = rounded(normalize_value(value, -24, -20, 0.0625, 0.0975, 0.08), 4)

    return (
        "alimiter=level_in=1:level_out=1:limit="
        + limit
        + ":attack=7:release=100:level=disabled"
    )


def _filter_list(state: AxiomState) -> list[str]:
    values = [
        _volume(state),
        _hard_limiter(state),
    ]

    if state.get("FilterAudio.FilterAudio_Lowpass_SelectedItem") == "enabled":
        values.append("lowpass")
    if state.get("FilterAudio.FilterAudio_Highpass_SelectedItem") == "enabled":
        values.append("highpass")

    contrast = _float(state, "FilterAudio.FilterAudio_Contrast_Value")
    if contrast != 0:
        values.append("acontrast=" + number_text(contrast))

    extra_stereo = _float(state, "FilterAudio.FilterAudio_ExtraStereo_Value")
    if extra_stereo != 0:
        normalized = normalize_value(extra_stereo, -100, 100, 0, 10, 2.5)
        values.append("extrastereo=" + rounded(normalized, 3))

    if state.get("FilterAudio.FilterAudio_Headphones_SelectedItem") == "enabled":
        values.append("earwax")

    tempo = _float(state, "FilterAudio.FilterAudio_Tempo_Value")
    if tempo != 100:
        values.append("atempo=" + rounded(tempo * 0.01, 2))

    return [value for value in values if value]


def audio_filter(ctx: BuildContext) -> str:
    state = ctx.state
    if not (
        state.get("Audio.Audio_Quality_SelectedItem") != "None"
        and state.get("Audio.Audio_Codec_SelectedItem") not in ("None", "Copy")
        and state.get("Audio.Audio_Quality_SelectedItem") != "Mute"
        and state.get("Audio.Audio_Stream_SelectedItem") != "none"
        and state.get("Format.Format_MediaType_SelectedItem") not in ("Image", "Sequence")
    ):
        return ""

    values = _filter_list(state)
    if not values:
        return ""
    return "-af " + ctx.quote(", ".join(values))
