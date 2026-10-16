"""Application settings and preset storage (new JSON format, schema version 1).

The original stored an INI file (``axiom.conf``) through Win32 P/Invoke and custom
presets as ``*.ini``.  The Python port intentionally does **not** read those formats;
settings and presets are plain JSON with an explicit schema version.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator

SCHEMA_VERSION = 1
APP_DIR_NAME = "AxiomPy"
SETTINGS_FILE_NAME = "axiom.json"
PRESET_SUFFIX = ".json"


def default_config_dir(portable_root: Path | None = None) -> Path:
    """Portable ``config/`` wins over ``%APPDATA%\\AxiomPy\\`` (as the original did)."""
    if portable_root is not None:
        portable = Path(portable_root) / "config"
        if portable.is_dir():
            return portable
    return Path(os.environ.get("APPDATA", Path.home())) / APP_DIR_NAME


@dataclass
class Settings:
    """Flat key/value settings bag; unknown keys survive a round trip."""

    values: Dict[str, Any] = field(default_factory=dict)

    def get(self, key: str, default: Any = None) -> Any:
        return self.values.get(key, default)

    def set(self, key: str, value: Any) -> None:
        self.values[key] = value

    def to_dict(self) -> Dict[str, Any]:
        return {"schema": SCHEMA_VERSION, "settings": dict(self.values)}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Settings":
        schema = payload.get("schema")
        if schema != SCHEMA_VERSION:
            raise ValueError(f"unsupported settings schema: {schema!r}")
        return cls(values=dict(payload.get("settings") or {}))

    def save(self, path: Path | None = None) -> Path:
        target = Path(path) if path is not None else default_config_dir() / SETTINGS_FILE_NAME
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(json.dumps(self.to_dict(), indent=2) + "\n", encoding="utf-8")
        return target

    @classmethod
    def load(cls, path: Path | None = None) -> "Settings":
        target = Path(path) if path is not None else default_config_dir() / SETTINGS_FILE_NAME
        if not target.exists():
            return cls()
        return cls.from_dict(json.loads(target.read_text(encoding="utf-8")))


@dataclass
class Preset:
    """A partial state override saved by the user."""

    name: str
    state: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        return {"schema": SCHEMA_VERSION, "name": self.name, "state": dict(self.state)}

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "Preset":
        schema = payload.get("schema")
        if schema != SCHEMA_VERSION:
            raise ValueError(f"unsupported preset schema: {schema!r}")
        return cls(name=str(payload["name"]), state=dict(payload.get("state") or {}))


class PresetStore:
    """Built-in presets plus user presets from the presets directory."""

    def __init__(self, directory: Path | None = None, builtin: Dict[str, Dict[str, Any]] | None = None):
        self.directory = Path(directory) if directory is not None else default_config_dir() / "presets"
        self.builtin: Dict[str, Dict[str, Any]] = dict(builtin or {})

    def names(self) -> list[str]:
        return list(self.builtin) + [preset.name for preset in self.user_presets()]

    def user_presets(self) -> Iterator[Preset]:
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.glob("*" + PRESET_SUFFIX)):
            try:
                yield Preset.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, KeyError, json.JSONDecodeError):
                continue

    def load(self, name: str) -> Dict[str, Any]:
        if name in self.builtin:
            return dict(self.builtin[name])
        for preset in self.user_presets():
            if preset.name == name:
                return dict(preset.state)
        raise KeyError(f"unknown preset: {name}")

    def save(self, name: str, state: Dict[str, Any]) -> Path:
        self.directory.mkdir(parents=True, exist_ok=True)
        target = self.directory / (name + PRESET_SUFFIX)
        target.write_text(json.dumps(Preset(name, state).to_dict(), indent=2) + "\n", encoding="utf-8")
        return target

    def delete(self, name: str) -> bool:
        target = self.directory / (name + PRESET_SUFFIX)
        if target.exists():
            target.unlink()
            return True
        return False

