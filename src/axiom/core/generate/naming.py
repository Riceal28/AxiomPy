"""Output filename tokens, spacing and collision-safe renaming."""

from __future__ import annotations

import ntpath
import os
import re

from ..state import AxiomState


CHANNEL_NUMBERS = {
    "Mono": "1",
    "Stereo": "2",
    "Joint Stereo": "2",
    "1.0": "1",
    "2.0": "2",
    "2.1": "2.1",
    "5.1": "5.1",
    "6.1": "6.1",
    "7.1": "7.1",
}

OUTPUT_TOKEN_NAMES = (
    "HW Accel",
    "Video Codec",
    "Video Codec Copy",
    "Pass",
    "Video Bit Rate",
    "Video CRF",
    "Preset",
    "Pixel Format",
    "Size",
    "Size Source",
    "Scaling",
    "Frame Rate",
    "Vsync",
    "Audio Codec",
    "Audio Codec Copy",
    "Channel",
    "Audio Bit Rate",
    "Sample Rate",
    "Bit Depth",
    "Input Ext",
)


def settings_check(value: str | None) -> str:
    text = str(value or "")
    if not text.strip() or text.lower() in {"off", "none", "auto", "crf", "custom"}:
        return ""
    return text


def selected_tokens(state: AxiomState) -> list[str]:
    return list(state.get("Configure.OutputNaming_ListView_SelectedItems") or [])


def _input_ext(input_text: str) -> str:
    return settings_check(
        ntpath.splitext(input_text)[1].replace(".", "").lower()
    )


def token_appender(state: AxiomState, input_text: str, filename: str) -> str:
    selected = selected_tokens(state)
    if not selected or state.get("Main.Batch_IsChecked"):
        return filename

    media_type = state.get("Format.Format_MediaType_SelectedItem")
    tokens: dict[str, str] = {}
    if media_type in ("Video", "Image", "Sequence"):
        hw = state.get("Video.Video_HWAccel_Transcode_SelectedItem") or ""
        tokens["HW Accel"] = settings_check(str(hw).replace(" ", "-"))

        codec = state.get("Video.Video_Codec_SelectedItem") or ""
        tokens["Video Codec"] = (
            settings_check(codec) if codec != "Copy" else ""
        )
        tokens["Video Codec Copy"] = (
            "cv-" + settings_check(str(codec).lower()) if codec == "Copy" else ""
        )

        video_pass = state.get("Video.Video_Pass_SelectedItem") or ""
        tokens["Pass"] = settings_check(str(video_pass).replace(" ", "-"))

        bitrate = state.get("Video.Video_BitRate_Text") or ""
        tokens["Video Bit Rate"] = (
            settings_check(str(bitrate).upper()) if str(bitrate).strip() else ""
        )

        crf = state.get("Video.Video_CRF_Text") or ""
        tokens["Video CRF"] = (
            "CRF" + settings_check(str(crf)) if str(crf).strip() else ""
        )

        preset = settings_check(state.get("Video.Video_EncodeSpeed_SelectedItem"))
        tokens["Preset"] = (
            "p-" + preset.replace(" ", "-").lower() if preset else ""
        )

        pixel = state.get("Video.Video_PixelFormat_SelectedItem") or ""
        tokens["Pixel Format"] = (
            settings_check(str(pixel)) if str(pixel).strip() else ""
        )

        size = state.get("Video.Video_Scale_SelectedItem") or ""
        tokens["Size"] = (
            settings_check(str(size).replace(" ", "-"))
            if size != "Source" and str(size).strip()
            else ""
        )
        tokens["Size Source"] = (
            "sz-" + settings_check(str(size).lower()) if size == "Source" else ""
        )

        scaling = state.get("Video.Video_ScalingAlgorithm_SelectedItem") or ""
        scaling_text = settings_check(str(scaling)) if str(scaling).strip() else ""
        tokens["Scaling"] = (
            "sa-" + scaling_text.replace(" ", "-").lower() if scaling_text else ""
        )

        fps = state.get("Video.Video_FPS_SelectedItem") or ""
        fps_text = settings_check(str(fps)) if str(fps).strip() else ""
        tokens["Frame Rate"] = fps_text + "fps" if fps_text else ""

        vsync = state.get("Video.Video_Vsync_SelectedItem") or ""
        vsync_text = settings_check(str(vsync)) if str(vsync).strip() else ""
        tokens["Vsync"] = "vsync-" + vsync_text if vsync_text else ""

    audio_codec = state.get("Audio.Audio_Codec_SelectedItem") or ""
    tokens["Audio Codec"] = (
        settings_check(audio_codec) if audio_codec != "Copy" else ""
    )
    tokens["Audio Codec Copy"] = (
        "ca-" + settings_check(str(audio_codec).lower())
        if audio_codec == "Copy"
        else ""
    )

    channel = state.get("Audio.Audio_Channel_SelectedItem") or ""
    if channel != "Source" and str(channel).strip():
        channel_text = settings_check(channel)
        tokens["Channel"] = (
            CHANNEL_NUMBERS.get(str(channel), "") + "CH" if channel_text else ""
        )
    else:
        tokens["Channel"] = ""

    audio_quality = state.get("Audio.Audio_Quality_SelectedItem") or ""
    audio_bitrate = state.get("Audio.Audio_BitRate_Text") or ""
    if audio_quality == "Custom":
        tokens["Audio Bit Rate"] = (
            settings_check(audio_bitrate) + "k" if str(audio_bitrate).strip() else ""
        )
    elif str(audio_quality).strip():
        value = settings_check(audio_quality)
        tokens["Audio Bit Rate"] = (
            value + ("k" if audio_quality != "Lossless" else "")
        )
    else:
        tokens["Audio Bit Rate"] = ""

    if state.get("Audio.Audio_VBR_IsChecked") and str(audio_bitrate).strip():
        tokens["Audio Bit Rate"] += "VBR"

    sample = state.get("Audio.Audio_SampleRate_SelectedItem") or ""
    tokens["Sample Rate"] = (
        settings_check(str(sample).replace("k", "")) + "kHz"
        if str(sample).strip()
        else ""
    )

    depth = state.get("Audio.Audio_BitDepth_SelectedItem") or ""
    tokens["Bit Depth"] = (
        settings_check(depth) + "-bit" if str(depth).strip() else ""
    )
    tokens["Input Ext"] = _input_ext(input_text)

    empty = {
        "",
        "cv-",
        "CRF",
        "fps",
        "p-",
        "sz-",
        "sa-",
        "ca-",
        "CH-",
        "k",
        "-bit",
        "kHz",
    }
    values = [filename]
    for name in selected:
        values.append(tokens.get(name, ""))
    return " ".join(value for value in values if value and value not in empty)


def _replace_periods(filename: str, replacement: str) -> str:
    return re.sub(
        r"(\d\.\d)|[.]",
        lambda match: match.group(1) if match.group(1) else replacement,
        filename,
    )


def output_filename_spacing(state: AxiomState, filename: str) -> str:
    mode = state.get("Configure.OutputFileNameSpacing_SelectedItem")
    if mode == "Spaces":
        filename = _replace_periods(filename, " ")
        filename = filename.replace("_", " ")
    elif mode == "Periods":
        filename = filename.replace(" ", ".").replace("-", ".").replace("_", ".")
    elif mode == "Dashes":
        filename = filename.replace(" ", "-")
        filename = _replace_periods(filename, "-").replace("_", "-")
    elif mode == "Underscores":
        filename = filename.replace(" ", "_")
        filename = _replace_periods(filename, "_").replace("-", "_")
    return filename


def file_renamer(
    state: AxiomState,
    input_dir: str,
    output_dir: str,
    input_filename: str,
    input_ext: str,
    output_filename: str,
    output_ext: str,
) -> str:
    input_full = ntpath.join(input_dir, input_filename + input_ext)
    output_full = ntpath.join(output_dir, output_filename + output_ext)
    input_text = str(state.get("Main.Input_Text") or "")
    if input_text.strip() and ntpath.normcase(input_full) == ntpath.normcase(output_full):
        if os.path.exists(output_full):
            count = 1
            while os.path.exists(output_full):
                new_name = f"{output_filename} ({count})"
                output_full = ntpath.join(output_dir, new_name + output_ext)
                count += 1
            return f"{output_filename} ({count - 1})"
        return output_filename
    return output_filename


def token_remover(state: AxiomState, filename: str) -> str:
    if state.get("Configure.InputFileNameTokens_SelectedItem") != "Remove":
        return filename

    text = re.sub(r"\[.*?\]", "", filename)
    patterns = [
        r"\b(?:webm|mp4|mkv|m2v|mpg|mpeg|avi|ogv|m4a|mp3|ogg|flac|wav|jpg|jpeg|png|webp)\b",
        r"\b(?:h[.\-]?264|h[.\-]?265|x264|x265|hevc|av1|vp8|vp9|mpeg-?2|mpeg-?4|theora|ffv1|huffyuv|magicyuv|prores|"
        r"aac|ac3|dts|flac|mp2|mp3|lame|vorbis|opus|pcm|alac|copy|raw|lossless|qoq)\b",
        r"\bhi(?:10|12|444|422|420)p{1,2}\b",
        r"\b(?:nv|amf|qsv|nvenc|quicksync|cuda|cuvid|dxva2|d3d11va)\b",
        r"\b[12]-?\s?pass\b",
        r"\bp-(?:placebo|very-slow|slower|slow|medium|fast|faster|very-fast|super-fast|ultra-fast|"
        r"quality|balanced|speed|default|lossless|lossless-hp|hp|hq|bd|low-latency(?:-hp|-hq)?)\b",
        r"\bcrf\d+\b",
        r"\b\d+(?:\.\d+)?(?:kvbr|kbps|k|m)\b",
        r"\b\d+p\b",
        r"\b[248]\s?k(?:\s?uhd)?\b",
        r"\b\d{3,4}x\d{3,4}\b",
        r"\b(?:yuva?420p|yuva?422p|yuva?444p|nv12|nv16|nv20le|nv21|gray|gray10le)(?:\d+le)?\b",
        r"\b\d+\.?\d?khz\b",
        r"\b\d+\s?bit\b",
        r"\b\d+(?:\.\d+)?\s?fps\b",
        r"\bvsync-[a-z]+\b",
        r"-?(?:neighbor|area|fast_bilinear|bilinear|bicubic|experimental|bicublin|gauss|sinc|lanczos|spline)\b",
        r"\b(?:blu[\-\s]?ray|web[\-\s]?dl|brrip|bdrip|dvdrip|hdtv|hdrip|uhd|hd|sd|rip|playlist)\b",
        r"\b(?:4|8|2)\s?k(?:\s?uhd)?\b",
        r"\b(?:english|arabic|bengali|chinese|dutch|finnish|french|german|hindi|"
        r"italian|japanese|korean|mandarin|portuguese|russian|spanish|swedish|"
        r"telugu|vietnamese)\b",
        r"\b(?:multi[\-\s]?subs?|subtitle(?:s|d)?|subs?|subbed)\b",
        r"\b(?:dual|multi|original|orig|org)[\-\s]?(?:audio|aud|dub(?:bed)?)\b",
        r"\b(?:dolby(?:\s?(?:digital|atmos|truehd))?|dts[\-\s]?hd(?:[\-\s.]?ma)?|atmos|truehd)\b",
        r"\bma\b",
        r"\b(?:ddp?|ac3|aac|dts)[\-\s]?\d(?:\.\d)?\b",
        r"\b\d+(?:\.\d+)?\s?(?:mb|gb|tb)\b",
        r"\b(?:amazon|amzn|itunes|spotify|repack|complete)\b",
        r"\b\d+\s?ch\b",
        r"\b\d\.\d(?:\.\d)?\b",
    ]
    for pattern in patterns:
        text = re.sub(pattern, "", text, flags=re.IGNORECASE)
    custom = str(state.get("Configure.InputFileNameTokensCustom_Text") or "")
    for item in custom.split(","):
        token = item.strip()
        if token:
            text = re.sub(re.escape(token), "", text, flags=re.IGNORECASE)
    text = re.sub(r"[ ]{2,}", " ", text)
    text = re.sub(r"[.]{2,}", ".", text)
    text = re.sub(r"[-]{2,}", "-", text)
    text = re.sub(r"[_]{2,}", "_", text)
    return text.strip().strip(".-_")
