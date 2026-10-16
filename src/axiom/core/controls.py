"""Control-layer resolution.

The original GUI resolves a lot of state as the user picks a container, media type and
codecs: it copies the codec's item tables into the ViewModel, applies the codec's
``controls_Enabled`` / ``controls_Selected`` overrides, defaults the pass mode and keeps
the previous codec's choice where sensible.  The generators then read that resolved
state.

This module reproduces the same steps from :mod:`axiom.core.controls_data` (extracted
from the C# control files) and :mod:`axiom.core.codecs_data`, so the CLI and the UI share
one implementation and the parity tests can compare it against the oracle's state dump.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping, Sequence

from . import codecs
from .controls_data import CONTROLS
from .state import AxiomState

KIND_GROUP = {"video": "Video", "audio": "Audio", "subtitle": "Subtitle"}
KIND_CODEC_FLAG = {"video": "-c:v", "audio": "-c:a", "subtitle": "-c:s"}

# Item sources that hold objects rather than plain strings.
OBJECT_ITEMS = {
    "Video_EncodeSpeed_Items",
    "Video_Quality_Items",
    "Video_Optimize_Items",
    "Audio_EncodeSpeed_Items",
    "Audio_Quality_Items",
}


def item_names(items: Sequence[Any]) -> list[str]:
    """Names of an item source (rows become their ``Name``, strings stay as they are)."""
    names: list[str] = []
    for item in items or []:
        if isinstance(item, Mapping):
            names.append(str(item.get("Name", "")))
        else:
            names.append(str(item))
    return names


def save_previous_item_cond(selected_item: str | None) -> bool:
    """Port of MainWindow.SavePreviousItemCond (its guard uses ``&&``, so it is a no-op)."""
    return bool(selected_item and selected_item.strip())


def selected_item(items: Sequence[Any], previous_item: str | None) -> str | None:
    """Port of MainWindow.SelectedItem: reuse the previous choice when it still exists."""
    names = item_names(items)
    if previous_item and previous_item.strip() and previous_item in names:
        return previous_item
    return names[0] if names else None


def _previous_flags(state: AxiomState) -> Dict[str, Any]:
    return state.flags.setdefault("previousItems", {})


def _enabled_row(kind: str, name: str) -> Dict[str, Any]:
    rows = codecs.table(kind, name, "controls_Enabled")
    return dict(rows[0]) if rows else {}


def _selected_row(kind: str, name: str) -> Dict[str, Any]:
    rows = codecs.table(kind, name, "controls_Selected")
    return dict(rows[0]) if rows else {}


def codec_controls(state: AxiomState, kind: str, name: str) -> Dict[str, Any]:
    """Replay ``Controls.<Kind>.Controls.CodecControls`` for one codec."""
    if not name or not name.strip():
        return {}
    if not codecs.has(kind, name):
        raise KeyError(f"unknown {kind} codec: {name}")

    group = KIND_GROUP[kind]
    view = state.group(group)
    rules = CONTROLS.get(kind, {"enabled": [], "selected": []})
    applied: Dict[str, Any] = {}

    # 1. Codec + parameters, exactly as the original joins them (empty parts dropped).
    codec_rows = codecs.table(kind, name, "codec")
    codec_name = str(codec_rows[0].get("Codec", "")) if codec_rows else ""
    parameters = str(codec_rows[0].get("Parameters", "")) if codec_rows else ""
    state.set(
        f"{group}.{group}_Codec",
        " ".join(part for part in (KIND_CODEC_FLAG[kind], codec_name, parameters) if part),
    )

    # 2. Remember the current choices before the item sources change.
    previous = _previous_flags(state)
    for rule in rules["selected"]:
        field = f"{group}.{rule['field']}"
        current = state.get(field)
        if rule["previousItem"] and save_previous_item_cond(current):
            previous[rule["previousItem"]] = current

    # 3. Item sources, in the original order (the pass state machine runs in between).
    for section, field in (
        ("encodeSpeed", f"{group}_EncodeSpeed_Items"),
        ("pixelFormat", f"{group}_PixelFormat_Items"),
    ):
        if codecs.table(kind, name, section):
            state.set(f"{group}.{field}", codecs.table(kind, name, section))

    codecs.apply_quality_pass(state, kind, name)

    for section, field in (
        ("quality", f"{group}_Quality_Items"),
        ("optimize", f"{group}_Optimize_Items"),
        ("tune", f"{group}_Optimize_Tune_Items"),
        ("profile", f"{group}_Optimize_Profile_Items"),
        ("level", f"{group}_Optimize_Level_Items"),
    ):
        if codecs.table(kind, name, section):
            state.set(f"{group}.{field}", codecs.table(kind, name, section))

    # 4. controls_Enabled overrides - note the guard variable is the one the original
    #    actually tested (verbatim from the source, including its copy/paste slip).
    enabled_row = _enabled_row(kind, name)
    for rule in rules["enabled"]:
        guard_value = enabled_row.get(rule["guard"])
        value = True if guard_value is None else bool(guard_value)
        state.set(f"{rule['view']}.{rule['field']}", value)
        applied[rule["field"]] = value

    # 5. controls_Selected overrides.
    selected_row = _selected_row(kind, name)
    for rule in rules["selected"]:
        field = f"{group}.{rule['field']}"
        value = selected_row.get(rule["prop"])
        if value not in (None, ""):
            state.set(field, value)
            applied[rule["field"]] = value
        elif rule["previousItem"]:
            items = state.get(f"{group}.{rule['previousItems']}") or []
            previous_value = previous.pop(rule["previousItem"], None)
            chosen = selected_item(items, previous_value)
            if chosen is not None:
                state.set(field, chosen)
                applied[rule["field"]] = chosen
    return applied


def resolve(state: AxiomState) -> AxiomState:
    """Resolve every control group the way the GUI does before a conversion.

    Container/media-type controls (which install the codec item lists and the
    media-type dependent enable flags) are the next module to land; until then this
    resolves the codec layer only.
    """
    for kind, group in KIND_GROUP.items():
        name = state.get(f"{group}.{group}_Codec_SelectedItem")
        if name:
            codec_controls(state, kind, str(name))
    return state

