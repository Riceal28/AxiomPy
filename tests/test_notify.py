"""Notify configuration, parameter renaming and template rendering."""

import json

from axiom.core.notify import (
    NOTIFY_MESSAGE_EXAMPLE,
    NotifyConfig,
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
    assert loaded.method == "PUT"
    assert loaded.headers == []
    status = next(
        parameter
        for parameter in loaded.parameters
        if parameter.key == "status"
    )
    assert status.label == "State"
    assert status.enabled is False


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
    assert "Progress: 100.0%" in rendered.message
    assert "Batch: 2/3 completed, 1 failed, 0 cancelled" in rendered.message
    assert "{" not in rendered.message
