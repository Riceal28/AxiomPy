"""Hardware-acceleration control linkage."""

from axiom.core import controls
from axiom.core.generate import generate
from axiom.core.presets_data import BUILTIN_PRESETS
from axiom.core.state import AxiomState


def _mp4_state() -> AxiomState:
    return AxiomState(
        {
            "Format.Format_Container_SelectedItem": "mp4",
            "Video.Video_Codec_SelectedItem": "x264",
        }
    )


def test_hwaccel_on_exposes_hardware_codecs_and_auto_children():
    state = _mp4_state()
    state.set("Video.Video_HWAccel_SelectedItem", "On")

    controls.hwaccel_mode_controls(state)

    assert "H264 NVENC" in controls.item_names(
        state.get("Video.Video_Codec_Items")
    )
    assert "HEVC QSV" in controls.item_names(state.get("Video.Video_Codec_Items"))
    assert state.get("Video.Video_HWAccel_Decode_IsEnabled") is True
    assert state.get("Video.Video_HWAccel_Transcode_IsEnabled") is True
    assert state.get("Video.Video_HWAccel_Decode_SelectedItem") == "auto"
    assert state.get("Video.Video_HWAccel_Transcode_SelectedItem") == "auto"


def test_hwaccel_transcode_switches_codec_family():
    state = _mp4_state()
    state.set("Video.Video_HWAccel_SelectedItem", "On")
    controls.hwaccel_mode_controls(state)

    state.set("Video.Video_HWAccel_Transcode_SelectedItem", "NVIDIA NVENC")
    controls.select_hwaccel_video_codec(state)
    assert state.get("Video.Video_Codec_SelectedItem") == "H264 NVENC"

    state.set("Video.Video_Codec_SelectedItem", "HEVC NVENC")
    controls.change_hwaccel_transcode(state)
    assert state.get("Video.Video_HWAccel_Transcode_SelectedItem") == "NVIDIA NVENC"

    state.set("Video.Video_Codec_SelectedItem", "HEVC QSV")
    controls.change_hwaccel_transcode(state)
    assert state.get("Video.Video_HWAccel_Transcode_SelectedItem") == "Intel QSV"


def test_hwaccel_off_restores_software_list_and_codec():
    state = _mp4_state()
    state.set("Video.Video_HWAccel_SelectedItem", "On")
    state.set("Video.Video_Codec_SelectedItem", "HEVC NVENC")
    controls.hwaccel_mode_controls(state)

    state.set("Video.Video_HWAccel_SelectedItem", "Off")
    controls.hwaccel_mode_controls(state)

    assert state.get("Video.Video_Codec_SelectedItem") == "x265"
    assert "HEVC NVENC" not in controls.item_names(
        state.get("Video.Video_Codec_Items")
    )
    assert state.get("Video.Video_HWAccel_Decode_SelectedItem") == "off"
    assert state.get("Video.Video_HWAccel_Transcode_SelectedItem") == "off"
    assert state.get("Video.Video_HWAccel_Decode_IsEnabled") is False
    assert state.get("Video.Video_HWAccel_Transcode_IsEnabled") is False


def test_video_presets_do_not_enable_hardware_implicitly():
    for name, preset in BUILTIN_PRESETS.items():
        codec = preset.get("Video.Video_Codec_SelectedItem")
        if codec in (None, "None", "Copy"):
            continue
        assert preset.get("Video.Video_HWAccel_SelectedItem") == "Off", name


def _hardware_command(codec: str, vendor: str) -> str:
    state = _mp4_state()
    controls.resolve(state)
    state.set("Video.Video_HWAccel_SelectedItem", "On")
    controls.hwaccel_mode_controls(state)
    state.set("Video.Video_HWAccel_Transcode_SelectedItem", vendor)
    controls.select_hwaccel_video_codec(state)
    state.set("Video.Video_Codec_SelectedItem", codec)
    controls.change_hwaccel_transcode(state)
    controls.codec_controls(state, "video", codec)
    controls.encoding_pass_controls(state)
    state.set("Video.Video_Quality_SelectedItem", "High")
    state.set("Video.Video_Pass_SelectedItem", "CRF")
    controls.video_quality_controls(state)
    controls.video_bitrate_display(state)
    return generate(state)


def test_amf_uses_native_qvbr_quality_options():
    command = _hardware_command("H264 AMF", "AMD AMF")
    assert "-c:v h264_amf" in command
    assert "-rc qvbr -qvbr_quality_level 20" in command
    assert "-crf " not in command


def test_nvenc_uses_original_quality_arguments():
    command = _hardware_command("H264 NVENC", "NVIDIA NVENC")
    assert "-c:v h264_nvenc" in command
    assert "-rc:v vbr_hq -crf 20" in command
