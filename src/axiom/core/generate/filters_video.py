"""Video filter fragments ported from ``Filters/VideoFilters.cs``.

The original accumulates strings in ``Filters.Video.vFiltersList``.  Callers append
the speed/scale/PNG fragments first, then this module adds the remaining filters in the
same order as ``VideoFilter()`` before the list is joined into one ``-vf`` argument.
"""

from __future__ import annotations

from typing import Any, Iterable

from ..state import AxiomState
from ..text import normalize_value
from .context import BuildContext


DENOISE_FILTERS = {
    "default": "removegrain=0",
    "nlmeans light": "nlmeans=3:1:7:3:2",
    "nlmeans medium": "nlmeans=6:1:7:3:2",
    "nlmeans strong": "nlmeans=10:1:7:3:2",
    "hqdn3d light": "hqdn3d=2:1:2:3",
    "hqdn3d medium": "hqdn3d=3:2:2:3",
    "hqdn3d strong": "hqdn3d=7:7:5:5",
    "vaguedenoiser light": "vaguedenoiser=threshold=1:method=soft:nsteps=5",
    "vaguedenoiser medium": "vaguedenoiser=threshold=3:method=soft:nsteps=5",
    "vaguedenoiser strong": "vaguedenoiser=threshold=6:method=soft:nsteps=5",
    "removegrain light": "removegrain=10",
    "removegrain medium": "removegrain=17",
    "removegrain strong": "removegrain=24",
}

DEINTERLACE_FILTERS = {
    "default": "yadif",
    "yes": "yadif=1",
    "frame": "yadif=0:-1:0",
    "field": "yadif=1:-1:0",
    "frame nospatial": "yadif=2:-1:0",
    "field nospatial": "yadif=3:-1:0",
}

DEBLOCK_FILTERS = {
    "default": "deblock",
    "weak": "deblock=filter=weak:block=4",
    "strong": "deblock=filter=strong:block=4",
    "strong+": (
        "deblock=filter=strong:block=4:alpha=0.12:beta=0.07:"
        "gamma=0.06:delta=0.05"
    ),
}

FLIP_FILTERS = {
    "horizontal": "hflip",
    "vertical": "vflip",
    "both": "hflip, vflip",
}

ROTATE_FILTERS = {
    "90° CW": "transpose=1",
    "180° CW": "transpose=1, transpose=1",
    "270° CW": "transpose=1, transpose=1, transpose=1",
    "90° CCW": "transpose=2",
    "180° CCW": "transpose=2, transpose=2",
    "270° CCW": "transpose=2, transpose=2, transpose=2",
}

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


def number_text(value: float) -> str:
    """Format a double like .NET ``Convert.ToString`` for the values Axiom uses."""
    if value == 0:
        return "0"
    text = format(value, ".15g")
    return text.replace("e+", "E+").replace("e-", "E-")


def rounded(value: float, places: int) -> str:
    return number_text(round(value, places))


def _float(state: AxiomState, key: str) -> float:
    try:
        return float(state.get(key) or 0)
    except (TypeError, ValueError):
        return 0.0


def _append_selected(
    ctx: BuildContext,
    key: str,
    mapping: dict[str, str],
) -> None:
    value = str(ctx.state.get(key) or "")
    if value and value != "disabled":
        ctx.v_filters.append(mapping.get(value, ""))


def _add_subtitle_burn(ctx: BuildContext) -> None:
    state = ctx.state
    if (
        state.get("Subtitle.Subtitle_Codec_SelectedItem") == "Burn"
        and ctx.subtitle_paths
    ):
        path = ctx.subtitle_paths[0]
        path = path.replace('`"', "'").replace('"', "'")
        path = path.replace("\\", "\\\\").replace(":", "\\:")
        ctx.v_filters.append("subtitles=" + path)


def selective_color_text(ctx: BuildContext) -> str:
    state = ctx.state
    values = [_float(state, f"FilterVideo.FilterVideo_SelectiveColor_{name}_{axis}_Value")
              for name in SELECTIVE_COLORS
              for axis in ("Cyan", "Magenta", "Yellow")]
    if sum(values) == 0:
        return ""

    method = str(
        state.get("FilterVideo.FilterVideo_SelectiveColor_Correction_Method_SelectedItem")
        or "relative"
    )
    groups = [f"correction_method={method}"]
    cursor = 0
    for name in SELECTIVE_COLORS:
        channels = []
        for _ in range(3):
            normalized = normalize_value(values[cursor], -100, 100, -1, 1, 0)
            channels.append(rounded(normalized, 2))
            cursor += 1
        groups.append(f"{name.lower()}=" + " ".join(channels))
    return "selectivecolor=" + ":".join(groups)


def _eq_text(ctx: BuildContext) -> str:
    state = ctx.state
    settings: Iterable[tuple[str, float, float, float, float, float]] = (
        ("brightness", -100, 100, -1, 1, 0),
        ("contrast", -100, 100, -2, 2, 1),
        ("saturation", -100, 100, 0, 3, 1),
        ("gamma", -100, 100, 0.1, 10, 1),
    )
    pieces = []
    for name, value_min, value_max, minimum, maximum, midpoint in settings:
        value = _float(state, "FilterVideo.FilterVideo_EQ_" + name.capitalize() + "_Value")
        if value == 0:
            continue
        normalized = normalize_value(
            value, value_min, value_max, minimum, maximum, midpoint
        )
        pieces.append(name + "=" + rounded(normalized, 2))
    return "eq=" + ":".join(pieces) if pieces else ""


def add_video_filters(ctx: BuildContext) -> None:
    """Append the filters that follow speed/scale/PNG in ``VideoFilter()``."""
    _add_subtitle_burn(ctx)

    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_DropFrames_SelectedItem",
        {"enabled": "mpdecimate"},
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Deinterlace_SelectedItem",
        DEINTERLACE_FILTERS,
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Deblock_SelectedItem",
        DEBLOCK_FILTERS,
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Deflicker_SelectedItem",
        {"enabled": "deflicker"},
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Denoise_SelectedItem",
        DENOISE_FILTERS,
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Deband_SelectedItem",
        {"enabled": "deband"},
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Deshake_SelectedItem",
        {"enabled": "deshake"},
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Dejudder_SelectedItem",
        {"enabled": "dejudder"},
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Flip_SelectedItem",
        FLIP_FILTERS,
    )
    _append_selected(
        ctx,
        "FilterVideo.FilterVideo_Rotate_SelectedItem",
        ROTATE_FILTERS,
    )

    eq = _eq_text(ctx)
    if eq:
        ctx.v_filters.append(eq)

    selective = selective_color_text(ctx)
    if selective:
        ctx.v_filters.append(selective)
