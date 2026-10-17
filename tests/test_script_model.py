"""Typed script and control-rule helpers."""

from axiom.core.script import Script, to_argv
from axiom.ui.control_rules import enabled_key, structural_scope


def test_script_inline_and_sorted_round_trip():
    script = Script('ffmpeg -y -i "C:\\Input\\clip one.mkv" -c:v libx264 out.mp4')
    assert script.inline == script.text
    assert script.sorted_text.splitlines()[0] == "ffmpeg"
    assert '"C:\\Input\\clip one.mkv"' in script.sorted_text


def test_to_argv_preserves_quoted_paths():
    args = to_argv('ffmpeg -i "C:\\Input\\clip one.mkv" out.mp4')
    assert args[:3] == ["ffmpeg", "-i", '"C:\\Input\\clip one.mkv"']


def test_enabled_key_mapping():
    assert enabled_key("Video.Video_BitRate_Text") == "Video.Video_BitRate_IsEnabled"
    assert enabled_key("Format.Format_Cut_SelectedItem") == (
        "Format.Format_Cut_IsEnabled"
    )
    assert enabled_key("Main.Input_Text") == "Main.Input_IsEnabled"


def test_structural_scopes_are_specific():
    assert structural_scope("Video.Video_Codec_SelectedItem") == "video_codec"
    assert structural_scope("Video.Video_Quality_SelectedItem") == "video_quality"
    assert structural_scope("Video.Video_Scale_SelectedItem") == "video_scale"
    assert structural_scope("Audio.Audio_Codec_SelectedItem") == "audio_codec"
