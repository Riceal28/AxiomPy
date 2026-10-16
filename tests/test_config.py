"""Settings and preset storage (new JSON format, no legacy INI)."""

from axiom.core.config import Preset, PresetStore, Settings


def test_settings_round_trip(tmp_path):
    path = tmp_path / "axiom.json"
    settings = Settings({"Shell_SelectedItem": "PowerShell", "Threads_SelectedItem": "Optimal"})
    settings.save(path)
    assert Settings.load(path).values == settings.values


def test_settings_schema_is_enforced(tmp_path):
    path = tmp_path / "axiom.json"
    path.write_text('{"schema": 99, "settings": {}}', encoding="utf-8")
    try:
        Settings.load(path)
    except ValueError as error:
        assert "schema" in str(error)
    else:  # pragma: no cover - defensive
        raise AssertionError("expected a schema error")


def test_preset_store_lists_builtins_and_users(tmp_path):
    store = PresetStore(directory=tmp_path, builtin={"HD High": {"Video.Video_CRF_Text": "20"}})
    assert store.names() == ["HD High"]
    store.save("MyPreset", {"Format.Format_Container_SelectedItem": "mkv"})
    assert "MyPreset" in store.names()
    assert store.load("MyPreset")["Format.Format_Container_SelectedItem"] == "mkv"
    assert store.load("HD High")["Video.Video_CRF_Text"] == "20"
    assert store.delete("MyPreset")
    assert "MyPreset" not in store.names()


def test_preset_payload_shape():
    payload = Preset("X", {"a": 1}).to_dict()
    assert payload["schema"] == 1 and payload["name"] == "X"
    assert Preset.from_dict(payload).state == {"a": 1}

