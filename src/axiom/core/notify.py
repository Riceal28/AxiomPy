"""Notification configuration, parameter selection and template rendering.

This module is intentionally Qt-free.  The desktop shell owns the actual HTTP
transport and stores a JSON file so Notify settings can be hot-reloaded without
restarting the application.
"""

from __future__ import annotations

import json
import os
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping

NOTIFY_SCHEMA = 1
NOTIFY_FILE_NAME = "notify.json"
HTTP_METHODS = ("POST", "PUT", "PATCH", "GET", "DELETE")
PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")

# A ready-to-use template that exercises the common placeholders.  Keeping it
# in the core module makes it available to both the UI and tests without
# duplicating the wording.
NOTIFY_MESSAGE_EXAMPLE = (
    "{status}: {input_name} → {output_name}\n"
    "Exit code: {exit_code} | Elapsed: {elapsed}s | Shell: {shell}\n"
    "Progress: {total_progress} | FPS: {fps} | "
    "Bitrate: {bitrate} | Speed: {speed}\n"
    "Batch: {batch_completed}/{batch_count} completed, "
    "{batch_failed} failed, {batch_cancelled} cancelled\n"
    "Started: {started_at}\n"
    "Finished: {finished_at}\n"
    "Error: {error}"
)


@dataclass(frozen=True)
class ParameterDefinition:
    key: str
    label: str
    enabled: bool
    description: str


PARAMETER_DEFINITIONS: tuple[ParameterDefinition, ...] = (
    ParameterDefinition(
        "status", "Status", True, "Completed, Failed or Cancelled."
    ),
    ParameterDefinition(
        "exit_code", "Exit Code", True, "Process exit code."
    ),
    ParameterDefinition(
        "input_name", "Input Name", True, "Input file or batch directory name."
    ),
    ParameterDefinition(
        "output_name", "Output Name", True, "Generated output file name."
    ),
    ParameterDefinition(
        "elapsed", "Elapsed", True, "Wall-clock run time in seconds."
    ),
    ParameterDefinition(
        "error", "Error", True, "Last error diagnostics, when present."
    ),
    ParameterDefinition(
        "input", "Input", False, "Full input path."
    ),
    ParameterDefinition(
        "output", "Output", False, "Full output path."
    ),
    ParameterDefinition(
        "current_file", "Current File", False, "Current batch file."
    ),
    ParameterDefinition(
        "file_progress", "File Progress", False, "Current file progress."
    ),
    ParameterDefinition(
        "total_progress", "Total Progress", False, "Batch total progress."
    ),
    ParameterDefinition(
        "started_at", "Started", False, "Run start time."
    ),
    ParameterDefinition(
        "finished_at", "Finished", False, "Run finish time."
    ),
    ParameterDefinition(
        "duration", "Media Duration", False, "Input duration in seconds."
    ),
    ParameterDefinition(
        "time", "Out Time", False, "Last FFmpeg output timestamp."
    ),
    ParameterDefinition(
        "frame", "Frame", False, "Last FFmpeg frame counter."
    ),
    ParameterDefinition(
        "fps", "FPS", False, "Last FFmpeg encoding FPS."
    ),
    ParameterDefinition(
        "bitrate", "Bitrate", False, "Last FFmpeg bitrate."
    ),
    ParameterDefinition(
        "size", "Size", False, "Last FFmpeg output size."
    ),
    ParameterDefinition(
        "speed", "Speed", False, "Last FFmpeg encoding speed."
    ),
    ParameterDefinition(
        "ffmpeg_progress", "FFmpeg Progress", False,
        "Last progress state reported by FFmpeg."
    ),
    ParameterDefinition(
        "command", "Command", False, "The complete command that was run."
    ),
    ParameterDefinition(
        "shell", "Shell", False, "CMD or PowerShell."
    ),
    ParameterDefinition(
        "cancelled", "Cancelled", False, "Whether the run was cancelled."
    ),
    ParameterDefinition(
        "batch", "Batch", False, "Whether this was a batch run."
    ),
    ParameterDefinition(
        "batch_count", "Batch Count", False, "Number of queued files."
    ),
    ParameterDefinition(
        "batch_completed", "Batch Completed", False,
        "Number of completed batch files."
    ),
    ParameterDefinition(
        "batch_failed", "Batch Failed", False,
        "Number of failed batch files."
    ),
    ParameterDefinition(
        "batch_cancelled", "Batch Cancelled", False,
        "Number of cancelled batch files."
    ),
    ParameterDefinition(
        "log", "FFmpeg Log", False, "Complete captured FFmpeg log."
    ),
)

PARAMETER_BY_KEY = {
    definition.key: definition for definition in PARAMETER_DEFINITIONS
}


def _as_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (dict, list, tuple)):
        return json.dumps(value, ensure_ascii=False)
    return str(value)


def render_template(text: str, context: Mapping[str, Any]) -> str:
    """Replace known ``{key}`` placeholders and leave other braces untouched."""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            return match.group(0)
        return _as_text(context[key])

    return PLACEHOLDER_PATTERN.sub(replace, text)


@dataclass
class NotifyParameter:
    key: str
    label: str = ""
    enabled: bool = True

    def resolved_label(self) -> str:
        if self.label.strip():
            return self.label.strip()
        definition = PARAMETER_BY_KEY.get(self.key)
        return definition.label if definition else self.key


@dataclass
class NotifyHeader:
    enabled: bool = True
    name: str = ""
    value: str = ""


def _default_parameters() -> list[NotifyParameter]:
    return [
        NotifyParameter(
            key=definition.key,
            label=definition.label,
            enabled=definition.enabled,
        )
        for definition in PARAMETER_DEFINITIONS
    ]


def _default_headers() -> list[NotifyHeader]:
    return [NotifyHeader(True, "Content-Type", "application/json")]


@dataclass
class NotifyConfig:
    enabled: bool = False
    hot_reload: bool = True
    method: str = "POST"
    url: str = ""
    timeout_ms: int = 10000
    headers: list[NotifyHeader] = field(default_factory=_default_headers)
    body: str = '{"message": {message_json}}'
    message_template: str = ""
    parameters: list[NotifyParameter] = field(default_factory=_default_parameters)

    @classmethod
    def defaults(cls) -> "NotifyConfig":
        return cls()

    def to_dict(self) -> dict:
        return {
            "schema": NOTIFY_SCHEMA,
            "enabled": bool(self.enabled),
            "hot_reload": bool(self.hot_reload),
            "method": self.method,
            "url": self.url,
            "timeout_ms": int(self.timeout_ms),
            "headers": [
                {
                    "enabled": bool(header.enabled),
                    "name": header.name,
                    "value": header.value,
                }
                for header in self.headers
            ],
            "body": self.body,
            "message_template": self.message_template,
            "parameters": [
                {
                    "key": parameter.key,
                    "label": parameter.label,
                    "enabled": bool(parameter.enabled),
                }
                for parameter in self.parameters
            ],
        }

    @classmethod
    def from_dict(cls, payload: Mapping[str, Any]) -> "NotifyConfig":
        saved = {
            str(item.get("key", "")): item
            for item in (payload.get("parameters") or [])
            if isinstance(item, Mapping) and item.get("key")
        }
        parameters: list[NotifyParameter] = []
        for definition in PARAMETER_DEFINITIONS:
            item = saved.pop(definition.key, {})
            parameters.append(
                NotifyParameter(
                    key=definition.key,
                    label=str(item.get("label") or definition.label),
                    enabled=bool(
                        item.get("enabled", definition.enabled)
                    ),
                )
            )
        # Keep unknown keys for forward compatibility.
        for key, item in saved.items():
            parameters.append(
                NotifyParameter(
                    key=key,
                    label=str(item.get("label") or key),
                    enabled=bool(item.get("enabled", True)),
                )
            )

        raw_headers = payload.get("headers")
        if raw_headers is None:
            headers = _default_headers()
        else:
            headers = []
            for item in raw_headers:
                if not isinstance(item, Mapping):
                    continue
                headers.append(
                    NotifyHeader(
                        enabled=bool(item.get("enabled", True)),
                        name=str(item.get("name") or ""),
                        value=str(item.get("value") or ""),
                    )
                )

        try:
            timeout_ms = int(payload.get("timeout_ms", 10000))
        except (TypeError, ValueError):
            timeout_ms = 10000
        return cls(
            enabled=bool(payload.get("enabled", False)),
            hot_reload=bool(payload.get("hot_reload", True)),
            method=str(payload.get("method") or "POST").upper(),
            url=str(payload.get("url") or ""),
            timeout_ms=max(1000, min(120000, timeout_ms)),
            headers=headers,
            body=str(payload.get("body", '{"message": {message_json}}')),
            message_template=str(payload.get("message_template") or ""),
            parameters=parameters,
        )


class NotifyStore:
    """JSON persistence for the hot-reloadable Notify configuration."""

    def __init__(self, path: Path | str | None = None) -> None:
        from .config import default_config_dir

        self.path = Path(path) if path is not None else (
            default_config_dir() / NOTIFY_FILE_NAME
        )

    def load(self) -> NotifyConfig:
        try:
            payload = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, ValueError, TypeError):
            return NotifyConfig.defaults()
        if not isinstance(payload, Mapping):
            return NotifyConfig.defaults()
        return NotifyConfig.from_dict(payload)

    def save(self, config: NotifyConfig) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temporary = self.path.with_name(self.path.name + ".tmp")
        temporary.write_text(
            json.dumps(config.to_dict(), indent=2) + "\n",
            encoding="utf-8",
        )
        os.replace(temporary, self.path)
        return self.path


@dataclass(frozen=True)
class RenderedNotify:
    method: str
    url: str
    headers: tuple[tuple[str, str], ...]
    body: str
    message: str
    parameters: dict[str, str]


def compose_message(
    context: Mapping[str, Any],
    parameters: list[NotifyParameter],
    template: str,
) -> tuple[str, dict[str, str], str]:
    """Build the message and the renamed enabled-parameter object."""
    selected: list[tuple[str, str]] = []
    params: dict[str, str] = {}
    used_labels: dict[str, int] = {}
    for parameter in parameters:
        if not parameter.enabled or parameter.key not in context:
            continue
        label = parameter.resolved_label()
        count = used_labels.get(label, 0) + 1
        used_labels[label] = count
        if count > 1:
            label = f"{label} #{count}"
        value = _as_text(context[parameter.key])
        selected.append((label, value))
        params[label] = value

    params_json = json.dumps(params, ensure_ascii=False)
    base = dict(context)
    for label, value in selected:
        base.setdefault(label, value)
    base["params"] = params
    base["params_json"] = params_json
    if template.strip():
        message = render_template(template, base)
    else:
        message = "\n".join(
            f"{label}: {value}"
            for label, value in selected
            if value != ""
        )
    return message, params, params_json


def render_notify(
    config: NotifyConfig,
    context: Mapping[str, Any],
) -> RenderedNotify:
    """Render URL, headers and body from a run-context dictionary."""
    message, params, params_json = compose_message(
        context,
        config.parameters,
        config.message_template,
    )
    values = dict(context)
    for parameter in config.parameters:
        if parameter.key not in context:
            continue
        label = parameter.resolved_label()
        if label and label not in values:
            values[label] = _as_text(context[parameter.key])
    message_json = json.dumps(message, ensure_ascii=False)
    values.update(
        {
            "message": message,
            "message_json": message_json,
            "params": params,
            "params_json": params_json,
        }
    )
    headers = tuple(
        (
            render_template(header.name, values),
            render_template(header.value, values),
        )
        for header in config.headers
        if header.enabled and header.name.strip()
    )
    return RenderedNotify(
        method=config.method.upper(),
        url=render_template(config.url, values),
        headers=headers,
        body=render_template(config.body, values),
        message=message,
        parameters=params,
    )
