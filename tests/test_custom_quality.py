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


def test_custom_crf_preserves_bitrate_without_synthesizing_vbv():
    command = generate(
        _state(
            Video_Pass_SelectedItem="CRF",
            Video_CRF_Text="22",
            Video_BitRate_Text="4000",
        )
    )

    assert "-crf 22" in command
    assert "-b:v 4000K" in command
    assert "-maxrate" not in command
    assert "-bufsize" not in command


def test_custom_vbr_uses_average_bitrate():
    state = _state(
        Video_Pass_SelectedItem="1 Pass",
        Video_BitRate_Text="4500",
    )
    state.set("Video.Video_VBR_IsChecked", True)
    command = generate(state)

    assert "-b:v 4500K" in command
    assert "-minrate" not in command
    assert "-maxrate" not in command


def test_custom_cbr_adds_default_vbv_constraints():
    state = _state(
        Video_Pass_SelectedItem="1 Pass",
        Video_BitRate_Text="4500",
    )
    state.set("Video.Video_VBR_IsChecked", False)
    command = generate(state)

    assert "-b:v 4500K" in command
    assert "-minrate 4500K" in command
    assert "-maxrate 4500K" in command
    assert "-bufsize 9000K" in command


def test_custom_explicit_limits_override_cbr_defaults():
    state = _state(
        Video_Pass_SelectedItem="1 Pass",
        Video_BitRate_Text="4500",
        Video_MinRate_Text="4000",
        Video_MaxRate_Text="8000",
        Video_BufSize_Text="9000",
    )
    state.set("Video.Video_VBR_IsChecked", False)
    command = generate(state)

    assert "-b:v 4500K" in command
    assert "-minrate 4000K" in command
    assert "-maxrate 8000K" in command
    assert "-bufsize 9000K" in command
    assert "-minrate 4500K" not in command


def test_custom_maxrate_gets_a_default_vbv_buffer():
    command = generate(
        _state(
            Video_Pass_SelectedItem="CRF",
            Video_CRF_Text="22",
            Video_MaxRate_Text="8000",
        )
    )

    assert "-maxrate 8000K" in command
    assert "-bufsize 16000K" in command


def test_custom_crf_does_not_emit_an_ineffective_minrate():
    command = generate(
        _state(
            Video_Pass_SelectedItem="CRF",
            Video_CRF_Text="22",
            Video_MinRate_Text="4000",
            Video_MaxRate_Text="8000",
        )
    )

    assert "-crf 22" in command
    assert "-minrate" not in command
    assert "-maxrate 8000K" in command


def test_custom_crf_clamps_maxrate_to_bitrate():
    command = generate(
        _state(
            Video_Pass_SelectedItem="CRF",
            Video_CRF_Text="22",
            Video_BitRate_Text="8000",
            Video_MaxRate_Text="4000",
        )
    )

    assert "-b:v 8000K" in command
    assert "-maxrate 8000K" in command
    assert "-maxrate 4000K" not in command
    assert "-bufsize 16000K" in command


def test_custom_crf_clamps_mixed_unit_maxrate_to_bitrate():
    command = generate(
        _state(
            Video_Pass_SelectedItem="CRF",
            Video_CRF_Text="22",
            Video_BitRate_Text="4M",
            Video_MaxRate_Text="3500K",
        )
    )

    assert "-b:v 4M" in command
    assert "-maxrate 4M" in command
    assert "-bufsize 8M" in command
    assert "-maxrate 3500K" not in command


def test_custom_minrate_with_bitrate_fills_missing_maxrate():
    state = _state(
        Video_Pass_SelectedItem="1 Pass",
        Video_BitRate_Text="4500",
        Video_MinRate_Text="4000",
    )
    state.set("Video.Video_VBR_IsChecked", True)
    command = generate(state)

    assert "-b:v 4500K" in command
    assert "-minrate 4000K" in command
    assert "-maxrate 4500K" in command
    assert "-bufsize 9000K" in command


def test_custom_bufsize_with_bitrate_fills_missing_maxrate():
    state = _state(
        Video_Pass_SelectedItem="1 Pass",
        Video_BitRate_Text="4500",
        Video_BufSize_Text="9000",
    )
    state.set("Video.Video_VBR_IsChecked", True)
    command = generate(state)

    assert "-b:v 4500K" in command
    assert "-maxrate 4500K" in command
    assert "-bufsize 9000K" in command


def test_custom_second_pass_ignores_incompatible_crf():
    command = generate(
        _state(
            Video_Pass_SelectedItem="2 Pass",
            Video_CRF_Text="22",
            Video_BitRate_Text="6000",
        )
    )

    assert "-crf" not in command
    assert command.count("-b:v 6000K") == 2
    assert command.count("-maxrate 6000K") == 2
    assert command.count("-pass 1") == 1
    assert command.count("-pass 2") == 1


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
