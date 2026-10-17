"""Settings and preset storage (new JSON format, no legacy INI)."""

from axiom.core.config import (
    Preset,
    PresetStore,
    Settings,
    default_config_dir,
    migrate_legacy_config,
    source_project_root,
)


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


def test_portable_config_environment_override(tmp_path, monkeypatch):
    portable = tmp_path / "config"
    portable.mkdir()
    monkeypatch.setenv("AXIOM_PORTABLE_ROOT", str(tmp_path))
    assert default_config_dir() == portable


def test_source_config_lives_in_project(monkeypatch):
    monkeypatch.delenv("AXIOM_PORTABLE_ROOT", raising=False)
    assert default_config_dir() == source_project_root() / "config"


def test_legacy_appdata_config_migrates_once(tmp_path, monkeypatch):
    legacy = tmp_path / "AxiomPy"
    presets = legacy / "presets"
    presets.mkdir(parents=True)
    (legacy / "axiom.json").write_text('{"schema": 1}', encoding="utf-8")
    (legacy / "notify.json").write_text('{"schema": 1}', encoding="utf-8")
    (presets / "Mine.json").write_text("{}", encoding="utf-8")
    monkeypatch.setenv("APPDATA", str(tmp_path))
    target = tmp_path / "project" / "config"

    copied = migrate_legacy_config(target)

    assert (target / "axiom.json").read_text(encoding="utf-8") == (
        '{"schema": 1}'
    )
    assert (target / "notify.json").is_file()
    assert (target / "presets" / "Mine.json").is_file()
    assert len(copied) == 3

    (target / "axiom.json").write_text('{"keep": true}', encoding="utf-8")
    migrate_legacy_config(target)

    assert (target / "axiom.json").read_text(encoding="utf-8") == (
        '{"keep": true}'
    )

