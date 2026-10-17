"""Custom quality rate-control argument generation."""

from axiom.core import controls
from axiom.core.generate import generate
from axiom.core.state import AxiomState


def _state(**values) -> AxiomState:
    video_values = {f"Video.{key}": value for key, value in values.items()}
    state = AxiomState(
        {
            "Main.Input_Text": "in.mkv",
            "Format.Format_Container_SelectedItem": "mp4",
            "Video.Video_Codec_SelectedItem": "x264",
            "Video.Video_Quality_SelectedItem": "Custom",
            "Video.Video_Pass_SelectedItem": "1 Pass",
            **video_values,
        }
    )
    controls.resolve(state)
    return state


def test_custom_bitrate_normalizes_bare_numbers_to_kilobits():
    command = generate(
        _state(
            Video_BitRate_Text="4500",
            Video_MinRate_Text="4000",
            Video_MaxRate_Text="8000",
            Video_BufSize_Text="9000",
            Video_VBR_IsChecked=True,
        )
    )

    assert "-b:v 4500K" in command
    assert "-minrate 4000K" in command
    assert "-maxrate 8000K" in command
    assert "-bufsize 9000K" in command
    assert "-q:v" not in command


def test_custom_crf_combines_with_normalized_bitrate():
    command = generate(
        _state(
            Video_Pass_SelectedItem="CRF",
            Video_CRF_Text="22",
            Video_BitRate_Text="4000",
        )
    )

    assert "-crf 22" in command
    assert "-b:v 4000K" in command


def test_custom_image_quality_uses_quality_scale():
    state = AxiomState(
        {
            "Main.Input_Text": "in.png",
            "Format.Format_Container_SelectedItem": "jpg",
            "Video.Video_Codec_SelectedItem": "JPEG",
            "Video.Video_Quality_SelectedItem": "Custom",
            "Video.Video_Pass_SelectedItem": "1 Pass",
            "Video.Video_BitRate_Text": "2",
        }
    )
    command = generate(state)

    assert "-q:v 2" in command
    assert "-b:v" not in command
    assert "-crf" not in command


def test_custom_values_survive_control_resolution():
    state = _state(
        Video_BitRate_Text="4500",
        Video_MinRate_Text="4000",
        Video_MaxRate_Text="8000",
        Video_BufSize_Text="9000",
    )

    assert state.get("Video.Video_BitRate_Text") == "4500"
    assert state.get("Video.Video_MinRate_Text") == "4000"
    assert state.get("Video.Video_MaxRate_Text") == "8000"
    assert state.get("Video.Video_BufSize_Text") == "9000"
