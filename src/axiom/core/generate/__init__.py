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
from ..script import Script, generate_script, to_argv

PENDING_MODULES: tuple[str, ...] = ()


def generate(state: AxiomState) -> str:
    """Return the full command line Axiom would build for ``state``.

    The control layer is resolved first when the caller has not already done it, then
    the single-file pipeline assembles the FFmpeg fragments.
    """
    from . import batch
    from .pipeline import generate as generate_single

    if not state.flags.get("controlsResolved"):
        resolve_controls(state)
    if state.get("Main.Batch_IsChecked"):
        return batch.generate(state)
    return generate_single(state)


def generate_runnable(state: AxiomState) -> str:
    """Return a command with line-break-separated fragments safely spaced.

    The original ``ffmpegArgs`` removes line breaks without replacing them, which
    can concatenate external-stream maps.  The parity surface keeps that quirk;
    the desktop runner uses this clean assembly instead.
    """
    from . import batch
    from .pipeline import generate as generate_single

    if not state.flags.get("controlsResolved"):
        resolve_controls(state)
    if state.get("Main.Batch_IsChecked"):
        return batch.generate(state, clean=True)
    return generate_single(state, clean=True)


def resolve_controls(state: AxiomState) -> AxiomState:
    """Resolve the container/media-type/codec/quality state like the GUI does."""
    from ..controls import resolve

    return resolve(state)


def generate_args(state: AxiomState) -> list[str]:
    """Return the generated single-file command split into argument tokens.

    ``generate`` remains the byte-for-byte parity surface.  New callers that want
    argv-style access can use this helper without affecting the C# golden corpus.
    """
    return to_argv(generate(state))


__all__ = [
    "generate",
    "generate_runnable",
    "generate_args",
    "generate_script",
    "Script",
    "resolve_controls",
    "join_fragments",
]

