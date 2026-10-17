"""Application settings and preset storage (new JSON format, schema version 1).

The original stored an INI file (``axiom.conf``) through Win32 P/Invoke and custom
presets as ``*.ini``.  The Python port intentionally does **not** read those formats;
settings and presets are plain JSON with an explicit schema version.
"""

from __future__ import annotations

import json
import os
import shutil
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Dict, Iterator

from .presets_data import BUILTIN_PRESETS, PRESET_VARIANTS

SCHEMA_VERSION = 1
APP_DIR_NAME = "AxiomPy"
SETTINGS_FILE_NAME = "axiom.json"
NOTIFY_FILE_NAME = "notify.json"
PRESET_SUFFIX = ".json"


def source_project_root() -> Path:
    """Return the repository root when running from source."""
    module_path = Path(__file__).resolve()
    for parent in module_path.parents:
        if (parent / "pyproject.toml").is_file():
            return parent
    working_dir = Path.cwd().resolve()
    for parent in (working_dir, *working_dir.parents):
        if (parent / "pyproject.toml").is_file():
            return parent
    return working_dir


def legacy_config_dir() -> Path:
    """Return the pre-portable ``%APPDATA%\\AxiomPy`` location."""
    return Path(os.environ.get("APPDATA", Path.home())) / APP_DIR_NAME


def default_config_dir(portable_root: Path | None = None) -> Path:
    """Store configuration beside the application, never in ``%APPDATA%``.

    A frozen or portable build uses ``<root>/config``.  A source checkout uses
    the repository's own ``config/`` directory so local runs keep their data in
    the project.  ``AXIOM_PORTABLE_ROOT`` explicitly selects the portable root.
    """
    root = portable_root
    if root is None:
        override = os.environ.get("AXIOM_PORTABLE_ROOT")
        if override:
            root = Path(override)
    if root is not None:
        return Path(root) / "config"
    return source_project_root() / "config"


def migrate_legacy_config(target: Path | None = None) -> list[Path]:
    """Copy ``%APPDATA%\\AxiomPy`` data into the project config once.

    Existing target files always win.  The legacy directory is left untouched
    so the migration remains non-destructive and can be repeated safely.
    """
    destination_root = (
        Path(target) if target is not None else default_config_dir()
    )
    legacy_root = legacy_config_dir()
    try:
        if (
            not legacy_root.is_dir()
            or legacy_root.resolve() == destination_root.resolve()
        ):
            return []
    except OSError:
        return []

    destination_root.mkdir(parents=True, exist_ok=True)
    copied: list[Path] = []
    for name in (SETTINGS_FILE_NAME, NOTIFY_FILE_NAME):
        source = legacy_root / name
        destination = destination_root / name
        if source.is_file() and not destination.exists():
            shutil.copy2(source, destination)
            copied.append(destination)

    legacy_presets = legacy_root / "presets"
    if legacy_presets.is_dir():
        destination_presets = destination_root / "presets"
        destination_presets.mkdir(parents=True, exist_ok=True)
        for source in sorted(legacy_presets.glob("*" + PRESET_SUFFIX)):
            destination = destination_presets / source.name
            if not destination.exists():
                shutil.copy2(source, destination)
                copied.append(destination)
    return copied


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
        self.builtin: Dict[str, Dict[str, Any]] = dict(
            BUILTIN_PRESETS if builtin is None else builtin
        )
        self.variants: Dict[str, Dict[str, Dict[str, Any]]] = (
            PRESET_VARIANTS if builtin is None else {}
        )

    def names(self) -> list[str]:
        defaults = ["Preset"] if self.variants else []
        return defaults + list(self.builtin) + [
            preset.name for preset in self.user_presets()
        ]

    def user_presets(self) -> Iterator[Preset]:
        if not self.directory.is_dir():
            return
        for path in sorted(self.directory.glob("*" + PRESET_SUFFIX)):
            try:
                yield Preset.from_dict(json.loads(path.read_text(encoding="utf-8")))
            except (ValueError, KeyError, json.JSONDecodeError):
                continue

    def load(self, name: str, state: Any = None) -> Dict[str, Any]:
        if name in self.variants:
            container = (
                state.get("Format.Format_Container_SelectedItem")
                if state is not None
                else None
            )
            variant = (
                "audio"
                if container in {"m4a", "mp3", "ogg", "flac", "wav"}
                else "video"
            )
            return dict(self.variants[name].get(variant, {}))
        if name in self.builtin:
            return dict(self.builtin[name])
        for preset in self.user_presets():
            if preset.name == name:
                return dict(preset.state)
        raise KeyError(f"unknown preset: {name}")

    def apply(self, name: str, state: Any) -> Any:
        state.update(self.load(name, state))
        return state

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

