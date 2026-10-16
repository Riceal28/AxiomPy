"""State snapshots in the same shape the C# harness writes.

The harness dumps every resolved ViewModel property; item sources are reduced to their
names (rows become their ``Name``, plain strings stay).  Keeping the Python snapshot in
the same shape means the two can be diffed key by key.
"""

from __future__ import annotations

from typing import Any, Dict, Mapping

from .state import AxiomState, GROUPS


def _normalise(value: Any) -> Any:
    if isinstance(value, str) or isinstance(value, bool) or isinstance(value, (int, float)):
        return value
    if value is None:
        return None
    if isinstance(value, (list, tuple)):
        normalised = []
        for item in value:
            if isinstance(item, Mapping):
                normalised.append(item.get("Name"))
            else:
                normalised.append(item)
        return normalised
    return None


def dump_state(state: AxiomState) -> Dict[str, Any]:
    """Flatten the state to ``Group.Property`` keys, mirroring Program.DumpState()."""
    dump: Dict[str, Any] = {}
    for key, value in state.values.items():
        if key.startswith("_") or "." not in key:
            continue
        group = key.split(".", 1)[0]
        if group not in GROUPS:
            continue
        dump[key] = _normalise(value)
    return dump

