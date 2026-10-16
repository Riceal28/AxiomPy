"""Codec tables and the EncodingPass state machine."""

import pytest

from axiom.core import codecs
from axiom.core.state import AxiomState


def test_all_codec_kinds_are_generated():
    assert len(codecs.names("video")) == 19
    assert len(codecs.names("audio")) == 12
    assert len(codecs.names("subtitle")) == 6
    assert len(codecs.names("image")) == 3


def test_video_codec_tables_match_the_original():
    x264 = codecs.lookup("video", "x264")
    assert x264["codec"][0]["Codec"] == "libx264"
    assert codecs.encode_speed_command("video", "x264", "Fast") == "-preset fast"
    assert "yuv420p" in codecs.table("video", "x264", "pixelFormat")
    assert codecs.quality_names("video", "x264") == [
        "Auto",
        "Lossless",
        "Ultra",
        "High",
        "Medium",
        "Low",
        "Sub",
        "Custom",
    ]
    assert codecs.quality_entry("video", "x264", "High")["CRF"] == "20"
    assert codecs.quality_entry("video", "x264", "Auto")["NA"] == "3000K"


def test_unknown_codec_reports_a_clear_error():
    with pytest.raises(KeyError):
        codecs.lookup("video", "NotACodec")
    with pytest.raises(KeyError):
        codecs.lookup("nosuchkind", "x264")


def test_quality_pass_auto_locks_two_pass():
    state = AxiomState({"Video.Video_Quality_SelectedItem": "Auto"})
    codecs.apply_quality_pass(state, "video", "x264")
    assert state.video.Video_Pass_Items == ["2 Pass"]
    assert state.video.Video_Pass_SelectedItem == "2 Pass"
    assert state.video.Video_Pass_IsEnabled is False
    assert state.video.Video_CRF_IsEnabled is False
    assert state.flags["passUserSelected"] is False


def test_quality_pass_default_branch_defaults_to_crf_once():
    state = AxiomState({"Video.Video_Quality_SelectedItem": "High"})
    applied = codecs.apply_quality_pass(state, "video", "x264")
    assert state.video.Video_Pass_Items == ["CRF", "1 Pass", "2 Pass"]
    assert state.video.Video_Pass_SelectedItem == "CRF"
    assert state.flags["passUserSelected"] is True
    assert applied["Video_Pass_SelectedItem"] == "CRF"

    # A second pass through must not override the user's choice.
    state.video.Video_Pass_SelectedItem = "2 Pass"
    codecs.apply_quality_pass(state, "video", "x264")
    assert state.video.Video_Pass_SelectedItem == "2 Pass"


def test_quality_pass_custom_enables_crf():
    state = AxiomState({"Video.Video_Quality_SelectedItem": "Custom"})
    codecs.apply_quality_pass(state, "video", "x264")
    assert state.video.Video_CRF_IsEnabled is True
    assert state.video.Video_Pass_Items == ["CRF", "1 Pass", "2 Pass"]


def test_audio_codec_tables_are_exposed():
    assert codecs.lookup("audio", "AAC")["codec"] == [
        {"Codec": "aac", "Parameters": ""}
    ]
    assert codecs.names("subtitle")[0] in codecs.CODECS["subtitle"]

