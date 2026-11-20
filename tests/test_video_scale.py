from axiom.core.cli import generate_command


def _case(**video_state):
    return {
        "id": "video-scale-preset",
        "state": {
            "Main.Input_Text": "C:\\Input\\clip.mkv",
            "Format.Format_Container_SelectedItem": "mkv",
            "Configure.Shell_SelectedItem": "CMD",
            **video_state,
        },
        "ffprobe": {
            "inputVideoCodec": "h264",
            "inputAudioCodec": "aac",
            "inputVideoBitRate": "3000000",
            "inputAudioBitRate": "192000",
            "inputSize": "1280x720",
            "inputDuration": "5.0",
            "inputFrameRate": "30",
        },
        "controls": {"threads": "-threads 0", "maxthreads": "8"},
    }


def test_1080p_lanczos_without_width_generates_valid_scale_filter():
    command = generate_command(
        _case(
            **{
                "Video.Video_Codec_SelectedItem": "x264",
                "Video.Video_Scale_SelectedItem": "1080p",
                "Video.Video_ScreenFormat_SelectedItem": "Widescreen",
                "Video.Video_ScalingAlgorithm_SelectedItem": "lanczos",
            }
        )
    )

    assert '-vf "scale=1920:-2:flags=lanczos"' in command
    assert "scale=:-2" not in command


def test_full_screen_preset_without_height_uses_preset_dimensions():
    command = generate_command(
        _case(
            **{
                "Video.Video_Codec_SelectedItem": "x264",
                "Video.Video_Scale_SelectedItem": "1080p",
                "Video.Video_ScreenFormat_SelectedItem": "Full Screen",
                "Video.Video_ScalingAlgorithm_SelectedItem": "bicubic",
            }
        )
    )

    assert '-vf "scale=-2:1080:flags=bicubic"' in command
    assert "scale=-2::" not in command
