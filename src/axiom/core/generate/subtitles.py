"""Ports of ``Generate.Subtitle`` fragments."""

from __future__ import annotations

from ..state import AxiomState


def subtitle_codec(state: AxiomState) -> str:
    if state.get("Subtitle.Subtitle_Codec_SelectedItem") == "None":
        return ""
    return str(state.get("Subtitle.Subtitle_Codec") or "")


def subtitle_mux(state: AxiomState) -> str:
    # External subtitle files are not part of the core JSON state yet.
    return ""


def subtitle_metadata(state: AxiomState) -> str:
    return ""
