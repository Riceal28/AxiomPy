"""State model: generated defaults, group access and case round trip."""

from axiom.core.defaults import DEFAULTS
from axiom.core.state import AxiomState


def test_defaults_cover_the_original_viewmodel_surface():
    assert len(DEFAULTS) > 400
    for key in (
        "Video.Video_Codec_SelectedItem",
        "Audio.Audio_Codec_SelectedItem",
        "Format.Format_Container_SelectedItem",
        "Configure.Shell_SelectedItem",
        "Main.Input_Text",
    ):
        assert key in DEFAULTS, key


def test_group_attribute_access_matches_dotted_names():
    state = AxiomState()
    state.video.Video_Codec_SelectedItem = "x264"
    assert state.get("Video.Video_Codec_SelectedItem") == "x264"
    assert state.group("Video").Video_Codec_SelectedItem == "x264"
    assert "Video_Codec_SelectedItem" in state.video


def test_case_mapping_keeps_overrides_and_sections():
    case = {
        "id": "demo",
        "state": {"Format.Format_Container_SelectedItem": "mp4"},
        "ffprobe": {"inputDuration": "10.0"},
        "controls": {"threads": "-threads 0"},
    }
    state = AxiomState.from_case(case)
    assert state.format.Format_Container_SelectedItem == "mp4"
    assert state.ffprobe == {"inputDuration": "10.0"}
    assert state.controls == {"threads": "-threads 0"}
    assert state.to_overrides()["Format.Format_Container_SelectedItem"] == "mp4"

