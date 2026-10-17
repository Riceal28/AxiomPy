"""Notify configuration, parameter renaming and template rendering."""

import json

import pytest

from axiom.core.notify import (
    BATCH_NOTIFY_EACH_FILE,
    NOTIFY_MESSAGE_EXAMPLE,
    NOTIFY_SCHEMA,
    NotifyConfig,
    NotifyHeader,
    NotifyLoadError,
    NotifyParameter,
    NotifyStore,
    compose_message,
    render_notify,
)


def _sample_context() -> dict[str, str]:
    return {
        "status": "Completed",
        "exit_code": "0",
        "input_name": "clip.mkv",
        "output_name": "clip.mp4",
        "elapsed": "12.50",
        "error": "",
        "total_progress": "100.0%",
    }


def test_notify_config_round_trip_preserves_parameter_settings(tmp_path):
    path = tmp_path / "notify.json"
    config = NotifyConfig.defaults()
    config.enabled = True
    config.batch_mode = BATCH_NOTIFY_EACH_FILE
    config.url = "https://example.test/hook"
    config.method = "PUT"
    config.headers = []
    for parameter in config.parameters:
        if parameter.key == "status":
            parameter.label = "State"
            parameter.enabled = False
    store = NotifyStore(path)

    store.save(config)
    loaded = store.load()

    assert loaded.enabled is True
    assert loaded.batch_mode == BATCH_NOTIFY_EACH_FILE
    assert loaded.method == "PUT"
    assert loaded.headers == []
    status = next(
        parameter
        for parameter in loaded.parameters
        if parameter.key == "status"
    )
    assert status.label == "State"
    assert status.enabled is False


def test_legacy_log_parameter_is_removed_when_loading(tmp_path):
    path = tmp_path / "notify.json"
    payload = NotifyConfig.defaults().to_dict()
    payload["parameters"].append(
        {"key": "log", "label": "FFmpeg Log", "enabled": True}
    )
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = NotifyStore(path).load_strict()

    assert "log" not in {parameter.key for parameter in loaded.parameters}
    assert "log" not in {
        parameter["key"] for parameter in loaded.to_dict()["parameters"]
    }


def test_render_notify_uses_renamed_enabled_parameters_and_json_braces():
    config = NotifyConfig.defaults()
    config.url = "https://example.test/{status}/{output_name}"
    config.body = (
        '{"message": "{message}", "code": {exit_code}, '
        '"meta": {params_json}}'
    )
    config.message_template = "{status}: {output_name}"
    config.headers = []
    config.parameters = [
        NotifyParameter("status", "State", True),
        NotifyParameter("exit_code", "Code", True),
        NotifyParameter("input_name", "Ignored", False),
    ]

    rendered = render_notify(config, _sample_context())

    assert rendered.url == "https://example.test/Completed/clip.mp4"
    assert rendered.message == "Completed: clip.mp4"
    assert rendered.parameters == {"State": "Completed", "Code": "0"}
    assert rendered.body == (
        '{"message": "Completed: clip.mp4", "code": 0, '
        '"meta": {"State": "Completed", "Code": "0"}}'
    )


def test_empty_message_template_builds_lines_from_enabled_parameters():
    message, params, params_json = compose_message(
        _sample_context(),
        [
            NotifyParameter("status", "State", True),
            NotifyParameter("output_name", "Output", True),
            NotifyParameter("elapsed", "Elapsed", False),
            NotifyParameter("error", "Error", True),
        ],
        "",
    )

    assert message == "State: Completed\nOutput: clip.mp4"
    assert params == {
        "State": "Completed",
        "Output": "clip.mp4",
        "Error": "",
    }
    assert '"State": "Completed"' in params_json
    assert "Elapsed" not in params_json


def test_notify_store_missing_file_returns_defaults(tmp_path):
    config = NotifyStore(tmp_path / "missing.json").load()
    assert config.enabled is False
    assert config.method == "POST"
    assert config.hot_reload is True
    assert any(
        parameter.key == "exit_code" and parameter.enabled
        for parameter in config.parameters
    )


def test_default_body_is_valid_json_with_escaped_multiline_message():
    rendered = render_notify(NotifyConfig.defaults(), _sample_context())
    payload = json.loads(rendered.body)
    assert payload["message"].startswith("Status: Completed")


def test_message_example_is_complete_and_renders_every_placeholder():
    context = {
        **_sample_context(),
        "shell": "CMD",
        "fps": "59.94",
        "bitrate": "4500kbits/s",
        "speed": "1.85x",
        "batch_count": "3",
        "seq": "2",
        "batch_completed": "2",
        "batch_failed": "1",
        "batch_cancelled": "0",
        "started_at": "2026-10-17T20:00:00+08:00",
        "finished_at": "2026-10-17T20:00:13+08:00",
    }
    config = NotifyConfig.defaults()
    config.message_template = NOTIFY_MESSAGE_EXAMPLE

    rendered = render_notify(config, context)

    assert "Completed: clip.mkv → clip.mp4" in rendered.message
    assert "Sequence: 2/3" in rendered.message
    assert "Progress: 100.0%" in rendered.message
    assert "Batch: 2/3 completed, 1 failed, 0 cancelled" in rendered.message
    assert "{" not in rendered.message


def test_json_body_escapes_string_values():
    config = NotifyConfig.defaults()
    config.url = "https://example.test/hook"
    config.body = (
        '{"input": "{input_name}", "output": "{output}", '
        '"message": "{message}", "code": {exit_code}, '
        '"meta": {params_json}}'
    )
    config.message_template = "{status}: {input_name}"
    config.headers = []
    config.parameters = [
        NotifyParameter("status", "State", True),
        NotifyParameter("exit_code", "Code", True),
    ]
    context = {
        "status": "Completed",
        "exit_code": "0",
        "input_name": 'a"b\nc.mkv',
        "output": r"G:\videos\foo\bar.mp4",
    }

    rendered = render_notify(config, context)
    payload = json.loads(rendered.body)

    assert rendered.body_error == ""
    assert payload["input"] == context["input_name"]
    assert payload["output"] == context["output"]
    assert payload["message"] == rendered.message
    assert payload["code"] == 0
    assert payload["meta"] == {"State": "Completed", "Code": "0"}


def test_form_body_encodes_placeholder_values():
    config = NotifyConfig.defaults()
    config.headers = [
        NotifyHeader(
            True,
            "Content-Type",
            "application/x-www-form-urlencoded",
        )
    ]
    config.body = "error={error}&status={status}"
    config.parameters = [NotifyParameter("status", "Status", True)]

    rendered = render_notify(
        config,
        {"status": "Completed", "error": "line one\nline two"},
    )

    assert rendered.body == (
        "error=line+one%0Aline+two&status=Completed"
    )
    assert rendered.body_error == ""


def test_invalid_json_body_is_reported():
    config = NotifyConfig.defaults()
    config.body = '{"message": {missing_placeholder}}'
    config.headers = []

    rendered = render_notify(config, _sample_context())

    assert rendered.body == '{"message": {missing_placeholder}}'
    assert rendered.body_error.startswith("Invalid JSON body:")


def test_disabled_parameter_is_removed_from_json_body():
    config = NotifyConfig.defaults()
    config.headers = []
    config.body = (
        '{"input": "{input_name}", "raw_input": {input_name}, '
        '"message": {message_json}, "params": {params_json}}'
    )
    config.parameters = [
        NotifyParameter("status", "Status", True),
        NotifyParameter("input_name", "Input Name", False),
    ]

    rendered = render_notify(
        config,
        {
            "status": "Completed",
            "input_name": "clip.mkv",
        },
    )
    payload = json.loads(rendered.body)

    assert "Input Name" not in rendered.message
    assert payload["input"] == ""
    assert payload["raw_input"] is None
    assert "Input Name" not in payload["params"]


def test_notify_store_invalid_structure_returns_defaults(tmp_path):
    path = tmp_path / "notify.json"
    path.write_text(
        json.dumps(
            {
                "enabled": "false",
                "hot_reload": "false",
                "method": "POST",
                "url": "",
                "timeout_ms": 10000,
                "headers": 5,
                "parameters": 5,
                "body": None,
                "message_template": "",
            }
        ),
        encoding="utf-8",
    )

    config = NotifyStore(path).load()

    assert config.enabled is False
    assert config.hot_reload is False
    assert config.headers == [
        NotifyHeader(True, "Content-Type", "application/json")
    ]
    assert config.body == NotifyConfig.defaults().body
    assert len(config.parameters) == len(
        NotifyConfig.defaults().parameters
    )


def test_notify_store_strict_load_rejects_partial_json(tmp_path):
    path = tmp_path / "notify.json"
    path.write_text('{"enabled": ', encoding="utf-8")

    with pytest.raises(NotifyLoadError):
        NotifyStore(path).load_strict()

    assert NotifyStore(path).load().enabled is False


def test_notify_store_strict_load_rejects_invalid_utf8(tmp_path):
    path = tmp_path / "notify.json"
    path.write_bytes(b"\xff\xfe\x00")

    with pytest.raises(NotifyLoadError):
        NotifyStore(path).load_strict()

    assert NotifyStore(path).load().enabled is False


def test_notify_store_strict_load_accepts_utf8_bom(tmp_path):
    path = tmp_path / "notify.json"
    payload = NotifyConfig.defaults().to_dict()
    payload["enabled"] = True
    payload["url"] = "https://bom.example/hook"
    path.write_text(json.dumps(payload), encoding="utf-8-sig")

    loaded = NotifyStore(path).load_strict()

    assert loaded.enabled is True
    assert loaded.url == "https://bom.example/hook"


def test_notify_store_strict_load_accepts_utf16(tmp_path):
    path = tmp_path / "notify.json"
    payload = NotifyConfig.defaults().to_dict()
    payload["enabled"] = True
    payload["url"] = "https://utf16.example/hook"
    path.write_text(json.dumps(payload), encoding="utf-16")

    loaded = NotifyStore(path).load_strict()

    assert loaded.enabled is True
    assert loaded.url == "https://utf16.example/hook"


def test_notify_store_strict_load_rejects_valid_but_incomplete_object(
    tmp_path,
):
    path = tmp_path / "notify.json"
    path.write_text("{}", encoding="utf-8")

    with pytest.raises(NotifyLoadError, match="incomplete"):
        NotifyStore(path).load_strict()


def test_notify_store_rejects_non_finite_numbers_as_load_error(tmp_path):
    path = tmp_path / "notify.json"
    path.write_text('{"timeout_ms": 1e999}', encoding="utf-8")

    with pytest.raises(NotifyLoadError, match="non-finite"):
        NotifyStore(path).load_strict()


def test_notify_store_rejects_unknown_schema(tmp_path):
    path = tmp_path / "notify.json"
    payload = NotifyConfig.defaults().to_dict()
    payload["schema"] = NOTIFY_SCHEMA + 1
    path.write_text(json.dumps(payload), encoding="utf-8")

    with pytest.raises(NotifyLoadError, match="Unsupported"):
        NotifyStore(path).load_strict()


def test_notify_store_accepts_complete_legacy_config_without_schema(tmp_path):
    path = tmp_path / "notify.json"
    payload = NotifyConfig.defaults().to_dict()
    payload.pop("schema")
    payload["url"] = "https://legacy.example/hook"
    path.write_text(json.dumps(payload), encoding="utf-8")

    loaded = NotifyStore(path).load_strict()

    assert loaded.url == "https://legacy.example/hook"


def test_url_placeholders_are_percent_encoded():
    config = NotifyConfig.defaults()
    config.url = "https://example.test/{input_name}"

    rendered = render_notify(
        config,
        {"input_name": "a#b?c d.mkv"},
    )

    assert rendered.url == "https://example.test/a%23b%3Fc%20d.mkv"


def test_unknown_placeholders_are_reported_without_breaking_json():
    config = NotifyConfig.defaults()
    config.headers = []
    config.body = json.dumps({"value": "{statuss}"})

    rendered = render_notify(config, {})

    assert rendered.body_error == ""
    assert rendered.unknown_placeholders == ("statuss",)


def test_invalid_header_names_are_skipped_and_newlines_are_removed():
    config = NotifyConfig.defaults()
    config.headers = [
        NotifyHeader(True, "Bad Header", "ignored"),
        NotifyHeader(True, "X-Test", "line one\r\nline two"),
    ]

    rendered = render_notify(config, {})

    assert rendered.headers == (("X-Test", "line one line two"),)
