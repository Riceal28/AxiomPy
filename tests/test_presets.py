"""Built-in preset lookup and default variants."""

from axiom.core.config import PresetStore
from axiom.core.state import AxiomState


def test_builtin_presets_are_available():
    store = PresetStore()
    assert store.names()[0] == "Preset"
    assert "HD High" in store.names()
    assert "HEVC Ultra" in store.names()
    assert "Video Download" not in store.names()
    assert store.load("HTML5")["Format.Format_Container_SelectedItem"] == "webm"


def test_default_preset_selects_audio_or_video_variant():
    store = PresetStore()
    audio = AxiomState({"Format.Format_Container_SelectedItem": "mp3"})
    store.apply("Preset", audio)
    assert audio.get("Format.Format_Container_SelectedItem") == "mp3"
    assert audio.get("Audio.Audio_Codec_SelectedItem") == "LAME"

    video = AxiomState({"Format.Format_Container_SelectedItem": "mkv"})
    store.apply("Preset", video)
    assert video.get("Format.Format_Container_SelectedItem") == "webm"
    assert video.get("Video.Video_Codec_SelectedItem") == "VP8"
