"""Ports of ``Generate.Subtitle`` fragments."""

from __future__ import annotations

from ..state import AxiomState
from .context import BuildContext


def subtitle_codec(state: AxiomState) -> str:
    if state.get("Subtitle.Subtitle_Codec_SelectedItem") == "None":
        return ""
    return str(state.get("Subtitle.Subtitle_Codec") or "")


def subtitle_mux(state: AxiomState) -> str:
    return ""


def subtitle_mux_args(ctx: BuildContext) -> str:
    state = ctx.state
    if (
        state.get("Subtitle.Subtitle_Codec_SelectedItem") != "Burn"
        and state.get("Subtitle.Subtitle_Stream_SelectedItem") in ("mux", "external")
        and ctx.subtitle_paths
    ):
        return "-i " + " -i ".join(
            path for path in ctx.subtitle_paths if path.strip()
        )
    return ""


def subtitle_metadata(state: AxiomState) -> str:
    return ""
