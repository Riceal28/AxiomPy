"""FFmpeg argument generation.

Port target (mirrors the original ``Generators`` namespace, ~8.5k lines of C#):

========================================  ==================================
original                                  python
========================================  ==================================
``Generate.FFmpeg.Generate_SingleArgs``   :func:`generate`
``Generate.FFmpeg._1_Pass.Arguments``     ``generate.pass_single``
``Generate.FFmpeg._2_Pass.Arguments``     ``generate.pass_two``
``Generate.FFmpeg.CRF.Arguments``         ``generate.pass_crf``
``Generate.FFmpeg.Batch.Generate_FFmpegArgs``  ``generate.batch``
``Generate.Video.*`` / ``Generate.Audio.*``    ``generate.video`` / ``generate.audio``
``Generate.Format`` / ``Generate.Streams``     ``generate.format`` / ``generate.streams``
``Filters.Video`` / ``Filters.Audio``          ``generate.filters_video`` / ``filters_audio``
========================================  ==================================

Every fragment mirrors the original's ``"\\r\\n\\r\\n" + arg`` structure and is assembled
with :func:`axiom.core.assembly.join_fragments`, which reproduces the original
"join with space, then delete line breaks" behaviour byte for byte.
"""

from __future__ import annotations

from ..assembly import join_fragments
from ..state import AxiomState

PENDING_MODULES = (
    "control layer: container/media-type/quality/optimize/pixel-format/cut controls",
    "format/cut/chapters",
    "video codec + encoding + quality + size + colour",
    "audio codec + quality + channels + metadata",
    "subtitles",
    "stream maps",
    "video/audio filters",
)


def generate(state: AxiomState) -> str:
    """Return the full command line Axiom would build for ``state``.

    Not implemented yet: the modules listed in :data:`PENDING_MODULES` are being ported
    one by one and validated against ``tests/golden`` (produced by the C# parity
    harness).  The signature is already final so callers and tests can be written now.
    """
    raise NotImplementedError(
        "generate() is being ported; pending: " + ", ".join(PENDING_MODULES)
    )


def resolve_controls(state: AxiomState) -> AxiomState:
    """Port target for ``Controls.Format/Video/Audio/Subtitles`` resolution."""
    raise NotImplementedError("control-layer resolution is being ported")


__all__ = ["generate", "resolve_controls", "join_fragments"]

