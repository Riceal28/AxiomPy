"""Runtime access to the generated codec tables.

``codecs_data.CODECS`` holds what the original codec classes published as combo box
item sources; this module gives them names, lookups and the behavioural part - the
``EncodingPass()`` state machine that decides which pass options a codec offers for the
selected quality.
"""

from __future__ import annotations

from typing import Any, Dict, Iterable, Mapping

from .codecs_data import CODECS
from .state import AxiomState

KIND_TO_GROUP = {
    "video": "Video",
    "audio": "Audio",
    "subtitle": "Subtitle",
    "image": "Video",
}


def lookup(kind: str, name: str) -> Dict[str, Any]:
    """Return the codec table for ``name`` (matches the combo box label)."""
    # The original video control class keeps the image codecs (JPEG/PNG/WebP) in
    # the same dictionary as VP8/x264/..., so a video codec selection may resolve
    # to the image table.
    if kind == "video" and name not in CODECS.get("video", {}) and name in CODECS.get(
        "image", {}
    ):
        kind = "image"
    table = CODECS.get(kind)
    if table is None:
        raise KeyError(f"unknown codec kind: {kind}")
    if name not in table:
        raise KeyError(f"unknown {kind} codec: {name}")
    return table[name]


def names(kind: str) -> list[str]:
    return list(CODECS.get(kind, {}))


def has(kind: str, name: str) -> bool:
    if name in CODECS.get(kind, {}):
        return True
    return kind == "video" and name in CODECS.get("image", {})


def table(kind: str, name: str, section: str) -> list:
    """Item source lookup (``codec``, ``encodeSpeed``, ``quality``, ``optimize`` ...)."""
    value = lookup(kind, name).get(section) or []
    return list(value)


def _field_key(kind: str, field: str) -> str:
    return KIND_TO_GROUP.get(kind, "Video") + "." + field


def apply_quality_pass(
    state: AxiomState,
    kind: str,
    name: str,
    quality_field: str | None = None,
) -> Dict[str, Any]:
    """Replay the codec's ``EncodingPass()`` for the currently selected quality.

    Mirrors the C# switch exactly:

    * the branch is keyed by the selected quality, falling back to ``default``,
    * ``userSelectedAssign`` only runs while ``passUserSelected`` is false - the same
      guard the original applies before defaulting to CRF.

    Returns the assignments that were applied (useful for tests and logging).
    """
    codec_table = lookup(kind, name)
    pass_table: Mapping[str, Any] = codec_table.get("qualityPass") or {}
    if not pass_table:
        return {}

    field = quality_field or (KIND_TO_GROUP.get(kind, "Video") + "_Quality_SelectedItem")
    quality = state.get(_field_key(kind, field))
    entry = pass_table.get(quality) if quality is not None else None
    entry = entry or pass_table.get("default") or {}

    applied: Dict[str, Any] = {}
    for target, value in (entry.get("assign") or {}).items():
        if target == "passUserSelected":
            state.flags["passUserSelected"] = bool(value)
        else:
            state.set(_field_key(kind, target), value)
        applied[target] = value

    guarded = entry.get("userSelectedAssign") or {}
    if guarded and not state.flags.get("passUserSelected", False):
        for target, value in guarded.items():
            if target == "passUserSelected":
                state.flags["passUserSelected"] = bool(value)
            else:
                state.set(_field_key(kind, target), value)
            applied[target] = value

    return applied


def quality_entry(kind: str, name: str, quality: str) -> Dict[str, Any]:
    """The codec's quality row (CRF/CBR/VBR tables) for ``quality``."""
    for row in table(kind, name, "quality"):
        if row.get("Name") == quality:
            return dict(row)
    return {}


def quality_names(kind: str, name: str) -> list[str]:
    return [row.get("Name", "") for row in table(kind, name, "quality")]


def encode_speed_command(kind: str, name: str, speed: str) -> str:
    for row in table(kind, name, "encodeSpeed"):
        if row.get("Name") == speed:
            return str(row.get("Command", ""))
    return ""


def codec_arguments(kind: str, name: str) -> Iterable[tuple[str, str]]:
    """``codec`` rows as (codec, parameters) pairs."""
    for row in table(kind, name, "codec"):
        yield str(row.get("Codec", "")), str(row.get("Parameters", ""))

