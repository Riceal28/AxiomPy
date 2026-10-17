"""Notification configuration, parameter selection and template rendering.

This module is intentionally Qt-free.  The desktop shell owns the actual HTTP
transport and stores a JSON file so Notify settings can be hot-reloaded without
restarting the application.
"""

from __future__ import annotations

import json
import math
import os
import re
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Mapping
from urllib.parse import quote, quote_plus

NOTIFY_SCHEMA = 1
NOTIFY_FILE_NAME = "notify.json"
DEFAULT_NOTIFY_BODY = '{"message": {message_json}}'
HTTP_METHODS = ("POST", "PUT", "PATCH", "GET", "DELETE")
BATCH_NOTIFY_EACH_FILE = "each_file"
BATCH_NOTIFY_BATCH_END = "batch_end"
BATCH_NOTIFY_MODES = (BATCH_NOTIFY_EACH_FILE, BATCH_NOTIFY_BATCH_END)
PLACEHOLDER_PATTERN = re.compile(r"\{([A-Za-z_][A-Za-z0-9_]*)\}")
HEADER_NAME_PATTERN = re.compile(r"^[!#$%&'*+\-.^_`|~0-9A-Za-z]+$")
REQUIRED_NOTIFY_KEYS = (
    "enabled",
    "hot_reload",
    "method",
    "url",
    "timeout_ms",
    "headers",
    "body",
    "message_template",
    "parameters",
)


class NotifyLoadError(ValueError):
    """Raised when notify.json is not a complete, valid configuration."""


def _reject_json_constant(value: str) -> None:
    raise ValueError(f"non-finite number {value}")


def _contains_non_finite(value: Any) -> bool:
    if isinstance(value, float):
        return not math.isfinite(value)
    if isinstance(value, Mapping):
        return any(_contains_non_finite(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return any(_contains_non_finite(item) for item in value)
    return False


# A ready-to-use template that exercises the common placeholders.  Keeping it
# in the core module makes it available to both the UI and tests without
# duplicating the wording.
NOTIFY_MESSAGE_EXAMPLE = (
    "{status}: {input_name} → {output_name}\n"
    "Sequence: {seq}/{batch_count}\n"
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
        "success", "Success", False,
        "true when the run completed successfully."
    ),
    ParameterDefinition(
        "seq", "Sequence", True,
        "One-based file sequence number in a batch."
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
        "duration_seconds", "Duration Seconds", False,
        "Output duration in seconds."
    ),
    ParameterDefinition(
        "file_size_bytes", "File Size Bytes", False,
        "Output file size in bytes."
    ),
    ParameterDefinition(
        "video_codec", "Video Codec", False, "Output video codec."
    ),
    ParameterDefinition(
        "width", "Width", False, "Output video width."
    ),
    ParameterDefinition(
        "height", "Height", False, "Output video height."
    ),
    ParameterDefinition(
        "overall_bitrate", "Overall Bitrate", False,
        "Output overall bitrate in bits per second."
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


def _as_bool(value: Any, default: bool) -> bool:
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)) and value in (0, 1):
        return bool(value)
    if isinstance(value, str):
        normalized = value.strip().lower()
        if normalized in {"true", "1", "yes", "on"}:
            return True
        if normalized in {"false", "0", "no", "off"}:
            return False
    return default


def render_template(text: str, context: Mapping[str, Any]) -> str:
    """Replace known ``{key}`` placeholders and leave other braces untouched."""

    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            return match.group(0)
        return _as_text(context[key])

    return PLACEHOLDER_PATTERN.sub(replace, text)


def _render_escaped_template(
    text: str,
    context: Mapping[str, Any],
    encoder,
) -> str:
    def replace(match: re.Match[str]) -> str:
        key = match.group(1)
        if key not in context:
            return match.group(0)
        return encoder(_as_text(context[key]))

    return PLACEHOLDER_PATTERN.sub(replace, text)


def render_url_template(text: str, context: Mapping[str, Any]) -> str:
    """Render a URL while percent-encoding substituted values."""

    return _render_escaped_template(
        text,
        context,
        lambda value: quote(value, safe=""),
    )


def render_form_template(text: str, context: Mapping[str, Any]) -> str:
    """Render form data while escaping substituted field values."""

    return _render_escaped_template(
        text,
        context,
        lambda value: quote_plus(value, safe=""),
    )


def _json_string_fragment(value: Any) -> str:
    """Return *value* escaped for use inside an existing JSON string."""

    return json.dumps(_as_text(value), ensure_ascii=False)[1:-1]


def render_json_template(
    text: str,
    context: Mapping[str, Any],
    null_keys: set[str] | None = None,
) -> str:
    """Render placeholders while preserving valid JSON string escaping.

    Placeholders inside JSON string literals are escaped as JSON string
    content, so Windows paths, quotes and newlines cannot break the document.
    Placeholders outside strings keep their existing raw substitution
    semantics, which lets ``{message_json}`` and ``{params_json}`` embed
    complete JSON values and lets numeric fields stay unquoted.
    """

    null_keys = null_keys or set()
    rendered: list[str] = []
    in_string = False
    escaped = False
    index = 0
    while index < len(text):
        character = text[index]
        if in_string:
            if escaped:
                rendered.append(character)
                escaped = False
                index += 1
                continue
            if character == "\\":
                rendered.append(character)
                escaped = True
                index += 1
                continue
            if character == '"':
                rendered.append(character)
                in_string = False
                index += 1
                continue
            if character == "{":
                match = PLACEHOLDER_PATTERN.match(text, index)
                if match is not None and match.group(1) in context:
                    rendered.append(
                        _json_string_fragment(context[match.group(1)])
                    )
                    index = match.end()
                    continue
            rendered.append(character)
            index += 1
            continue

        if character == '"':
            rendered.append(character)
            in_string = True
            index += 1
            continue
        if character == "{":
            match = PLACEHOLDER_PATTERN.match(text, index)
            if match is not None and match.group(1) in context:
                key = match.group(1)
                rendered.append(
                    "null" if key in null_keys else _as_text(context[key])
                )
                index = match.end()
                continue
        rendered.append(character)
        index += 1
    return "".join(rendered)


def _content_type(
    headers: tuple[tuple[str, str], ...],
) -> str:
    media_type = ""
    for name, value in headers:
        if name.strip().lower() != "content-type":
            continue
        candidate = value.split(";", 1)[0].strip().lower()
        if candidate:
            # Qt's setRawHeader replaces an existing header with the same
            # name, so the last enabled occurrence is the effective one.
            media_type = candidate
    return media_type


def _is_json_body(
    headers: tuple[tuple[str, str], ...],
    body: str,
) -> bool:
    media_type = _content_type(headers)
    if media_type:
        return (
            media_type == "application/json"
            or media_type.endswith("+json")
        )
    return body.lstrip().startswith(("{", "["))


def _is_form_body(headers: tuple[tuple[str, str], ...]) -> bool:
    return _content_type(headers) == "application/x-www-form-urlencoded"


def _unknown_placeholders(
    text: str,
    context: Mapping[str, Any],
) -> set[str]:
    return set(PLACEHOLDER_PATTERN.findall(text)).difference(context)


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
    batch_mode: str = BATCH_NOTIFY_BATCH_END
    method: str = "POST"
    url: str = ""
    timeout_ms: int = 10000
    headers: list[NotifyHeader] = field(default_factory=_default_headers)
    body: str = DEFAULT_NOTIFY_BODY
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
            "batch_mode": self.batch_mode,
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
        raw_parameters = payload.get("parameters")
        saved: dict[str, Mapping[str, Any]] = {}
        if isinstance(raw_parameters, (list, tuple)):
            saved = {
                str(item.get("key", "")): item
                for item in raw_parameters
                if isinstance(item, Mapping) and item.get("key")
            }
        parameters: list[NotifyParameter] = []
        for definition in PARAMETER_DEFINITIONS:
            item = saved.pop(definition.key, {})
            parameters.append(
                NotifyParameter(
                    key=definition.key,
                    label=str(item.get("label") or definition.label),
                    enabled=_as_bool(
                        item.get("enabled"),
                        definition.enabled,
                    ),
                )
            )
        # Keep unknown keys for forward compatibility.
        for key, item in saved.items():
            if key == "log":
                # The full FFmpeg log was removed from configurable fields.
                continue
            parameters.append(
                NotifyParameter(
                    key=key,
                    label=str(item.get("label") or key),
                    enabled=_as_bool(item.get("enabled"), True),
                )
            )

        raw_headers = payload.get("headers")
        if not isinstance(raw_headers, (list, tuple)):
            headers = _default_headers()
        else:
            headers = []
            for item in raw_headers:
                if not isinstance(item, Mapping):
                    continue
                headers.append(
                    NotifyHeader(
                        enabled=_as_bool(item.get("enabled"), True),
                        name=(
                            item.get("name")
                            if isinstance(item.get("name"), str)
                            else ""
                        ),
                        value=(
                            item.get("value")
                            if isinstance(item.get("value"), str)
                            else ""
                        ),
                    )
                )

        try:
            timeout_ms = int(payload.get("timeout_ms", 10000))
        except (TypeError, ValueError, OverflowError):
            timeout_ms = 10000
        method = payload.get("method")
        method_text = method.strip().upper() if isinstance(method, str) else ""
        if method_text not in HTTP_METHODS:
            method_text = "POST"
        batch_mode = payload.get("batch_mode")
        if batch_mode not in BATCH_NOTIFY_MODES:
            batch_mode = BATCH_NOTIFY_BATCH_END
        url = payload.get("url")
        body = payload.get("body")
        message_template = payload.get("message_template")
        return cls(
            enabled=_as_bool(payload.get("enabled"), False),
            hot_reload=_as_bool(payload.get("hot_reload"), True),
            batch_mode=batch_mode,
            method=method_text,
            url=url if isinstance(url, str) else "",
            timeout_ms=max(1000, min(120000, timeout_ms)),
            headers=headers,
            body=body if isinstance(body, str) else DEFAULT_NOTIFY_BODY,
            message_template=(
                message_template if isinstance(message_template, str) else ""
            ),
            parameters=parameters,
        )


class NotifyStore:
    """JSON persistence for the hot-reloadable Notify configuration."""

    def __init__(self, path: Path | str | None = None) -> None:
        from .config import default_config_dir

        self.path = Path(path) if path is not None else (
            default_config_dir() / NOTIFY_FILE_NAME
        )

    def load_strict(self) -> NotifyConfig:
        """Load a complete, valid configuration or raise ``NotifyLoadError``."""
        try:
            data = self.path.read_bytes()
        except (OSError, UnicodeError) as error:
            raise NotifyLoadError(
                f"Could not read {self.path.name}: {error}"
            ) from error
        try:
            # Accept UTF-8/UTF-8 BOM and the UTF-16 files some Windows
            # editors still produce.
            if data.startswith((b"\xff\xfe", b"\xfe\xff")):
                text = data.decode("utf-16")
            else:
                text = data.decode("utf-8-sig")
        except UnicodeError as error:
            raise NotifyLoadError(
                f"Could not decode {self.path.name}: {error}"
            ) from error
        try:
            payload = json.loads(
                text,
                parse_constant=_reject_json_constant,
            )
        except (TypeError, ValueError) as error:
            raise NotifyLoadError(
                f"Invalid JSON in {self.path.name}: {error}"
            ) from error
        if not isinstance(payload, Mapping):
            raise NotifyLoadError(
                f"{self.path.name} must contain a JSON object"
            )
        if _contains_non_finite(payload):
            raise NotifyLoadError(
                f"{self.path.name} contains a non-finite number"
            )
        schema = payload.get("schema")
        if schema is not None and (
            isinstance(schema, bool)
            or not isinstance(schema, int)
            or schema != NOTIFY_SCHEMA
        ):
            raise NotifyLoadError(
                f"Unsupported Notify schema {schema!r}; "
                f"expected {NOTIFY_SCHEMA}"
            )
        missing = [
            key for key in REQUIRED_NOTIFY_KEYS if key not in payload
        ]
        if missing:
            raise NotifyLoadError(
                "Notify configuration is incomplete; missing "
                + ", ".join(missing)
            )
        try:
            return NotifyConfig.from_dict(payload)
        except (
            TypeError,
            ValueError,
            AttributeError,
            KeyError,
            OverflowError,
        ) as error:
            raise NotifyLoadError(
                f"Invalid Notify configuration: {error}"
            ) from error

    def load(self) -> NotifyConfig:
        """Load the configuration, falling back to defaults on any error."""
        try:
            return self.load_strict()
        except NotifyLoadError:
            return NotifyConfig.defaults()

    def save(self, config: NotifyConfig) -> Path:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        rendered = json.dumps(config.to_dict(), indent=2) + "\n"
        temporary: Path | None = None
        try:
            with tempfile.NamedTemporaryFile(
                mode="w",
                encoding="utf-8",
                newline="\n",
                prefix=f".{self.path.name}.",
                suffix=".tmp",
                dir=self.path.parent,
                delete=False,
            ) as stream:
                temporary = Path(stream.name)
                stream.write(rendered)
                stream.flush()
                os.fsync(stream.fileno())
            for attempt in range(4):
                try:
                    os.replace(temporary, self.path)
                    break
                except PermissionError:
                    if attempt == 3:
                        raise
                    time.sleep(0.05 * (attempt + 1))
        finally:
            if temporary is not None:
                try:
                    temporary.unlink()
                except FileNotFoundError:
                    pass
        return self.path


@dataclass(frozen=True)
class RenderedNotify:
    method: str
    url: str
    headers: tuple[tuple[str, str], ...]
    body: str
    message: str
    parameters: dict[str, str]
    body_error: str = ""
    unknown_placeholders: tuple[str, ...] = ()


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
    disabled_placeholders: set[str] = set()
    for parameter in config.parameters:
        if parameter.enabled or parameter.key not in context:
            continue
        disabled_placeholders.add(parameter.key)
        label = parameter.resolved_label()
        if label:
            disabled_placeholders.add(label)
    body_values = dict(values)
    for key in disabled_placeholders:
        body_values[key] = ""
    rendered_headers: list[tuple[str, str]] = []
    for header in config.headers:
        if not header.enabled:
            continue
        name = render_template(header.name, values).strip()
        if not HEADER_NAME_PATTERN.fullmatch(name):
            continue
        value = re.sub(
            r"[\r\n]+",
            " ",
            render_template(header.value, values),
        )
        rendered_headers.append((name, value))
    headers = tuple(rendered_headers)
    body_is_json = _is_json_body(headers, config.body)
    if body_is_json:
        body = render_json_template(
            config.body,
            body_values,
            disabled_placeholders,
        )
    elif _is_form_body(headers):
        body = render_form_template(config.body, body_values)
    else:
        body = render_template(config.body, body_values)
    body_error = ""
    if body_is_json and body.strip():
        try:
            json.loads(body)
        except (TypeError, ValueError) as error:
            body_error = f"Invalid JSON body: {error}"
    unknown: set[str] = set()
    for text in (
        config.url,
        config.message_template,
        config.body,
        *(part for header in headers for part in header),
    ):
        unknown.update(_unknown_placeholders(text, values))
    return RenderedNotify(
        method=config.method.upper(),
        url=render_url_template(config.url, values),
        headers=headers,
        body=body,
        message=message,
        parameters=params,
        body_error=body_error,
        unknown_placeholders=tuple(sorted(unknown)),
    )
