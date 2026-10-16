"""Application state model.

``AxiomState`` is a thin, typed-enough wrapper over the generated ``DEFAULTS`` table:
the original kept eight ``ViewModel`` classes with 491 properties between them, and the
Python port keeps the same names so that every generator can be translated literally
(``VM.VideoView.Video_Codec_SelectedItem`` -> ``state.video.Video_Codec_SelectedItem``).

Case files use ``"Group.Property"`` keys, which is also the format the parity harness
consumes, so one fixture drives both sides.
"""

from __future__ import annotations

from typing import Any, Dict, Iterator, Mapping, MutableMapping

from .defaults import DEFAULTS

GROUPS = (
    "Main",
    "Format",
    "Video",
    "Audio",
    "Subtitle",
    "FilterVideo",
    "FilterAudio",
    "Configure",
)

GROUP_ALIASES = {
    "main": "Main",
    "format": "Format",
    "video": "Video",
    "audio": "Audio",
    "subtitle": "Subtitle",
    "filter_video": "FilterVideo",
    "filtervideo": "FilterVideo",
    "filter_audio": "FilterAudio",
    "filteraudio": "FilterAudio",
    "configure": "Configure",
}


class Group:
    """Attribute view over the ``Group.*`` slice of the state."""

    __slots__ = ("_state", "_prefix")

    def __init__(self, state: "AxiomState", prefix: str) -> None:
        self._state = state
        self._prefix = prefix + "."

    def __getattr__(self, name: str) -> Any:
        if name.startswith("_"):
            raise AttributeError(name)
        return self._state.get(self._prefix + name)

    def __setattr__(self, name: str, value: Any) -> None:
        if name in ("_state", "_prefix"):
            object.__setattr__(self, name, value)
        else:
            self._state.set(self._prefix + name, value)

    def __contains__(self, name: str) -> bool:
        return (self._prefix + name) in self._state.values

    def items(self) -> Iterator[tuple[str, Any]]:
        for key, value in self._state.values.items():
            if key.startswith(self._prefix):
                yield key[len(self._prefix) :], value


class AxiomState:
    """Mutable state bag; unknown keys are accepted so ports can add fields freely."""

    def __init__(self, overrides: Mapping[str, Any] | None = None) -> None:
        self.values: MutableMapping[str, Any] = dict(DEFAULTS)
        if overrides:
            self.update(overrides)

    # -- dict-like access -------------------------------------------------
    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def update(self, overrides: Mapping[str, Any]) -> None:
        for key, value in overrides.items():
            self.values[key] = value

    def pop(self, key: str) -> Any:
        return self.values.pop(key)

    def __contains__(self, key: str) -> bool:
        return key in self.values

    def __iter__(self) -> Iterator[str]:
        return iter(self.values)

    # -- group access -----------------------------------------------------
    def __getattr__(self, name: str) -> Group:
        if name.startswith("_"):
            raise AttributeError(name)
        group = GROUP_ALIASES.get(name) or GROUP_ALIASES.get(name.lower())
        if group is None:
            raise AttributeError(name)
        return Group(self, group)

    def group(self, group: str) -> Group:
        return Group(self, group)

    def group_items(self, group: str) -> Dict[str, Any]:
        prefix = group + "."
        return {
            key[len(prefix) :]: value
            for key, value in self.values.items()
            if key.startswith(prefix)
        }

    def to_overrides(self) -> Dict[str, Any]:
        """Only the entries that differ from the defaults (used by presets/tests)."""
        return {
            key: value
            for key, value in sorted(self.values.items())
            if key not in DEFAULTS or DEFAULTS[key] != value
        }

    # -- fixture helpers --------------------------------------------------
    @classmethod
    def from_case(cls, case: Mapping[str, Any]) -> "AxiomState":
        """Build a state from a parity-harness case (``state`` section + preset)."""
        state = cls(dict(case.get("state") or {}))
        probe = case.get("ffprobe") or {}
        if probe:
            state.set("_ffprobe", dict(probe))
        controls = case.get("controls") or {}
        if controls:
            state.set("_controls", dict(controls))
        return state

    @property
    def ffprobe(self) -> Dict[str, Any]:
        return dict(self.values.get("_ffprobe") or {})

    @property
    def controls(self) -> Dict[str, Any]:
        return dict(self.values.get("_controls") or {})

