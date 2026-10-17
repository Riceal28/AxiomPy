"""Assembly of the single-file FFmpeg command (1-pass and 2-pass)."""

from __future__ import annotations

from ..state import AxiomState
from ..text import remove_line_breaks
from . import audio, filters_audio, format as fmt, streams, subtitles, video
from .context import BuildContext, build_context, join_args


def _overwrite(state: AxiomState) -> str:
    return {"Always": "-y", "Never": "-n"}.get(
        str(state.get("Configure.OutputOverwrite_SelectedItem") or ""), ""
    )


def _video_enabled(state: AxiomState) -> bool:
    return (
        state.get("Format.Format_MediaType_SelectedItem") != "Audio"
        and state.get("Video.Video_Codec_SelectedItem") != "None"
        and state.get("Video.Video_Quality_SelectedItem") != "None"
    )


def _audio_enabled(state: AxiomState) -> bool:
    return (
        state.get("Format.Format_MediaType_SelectedItem") not in ("Image", "Sequence")
        and state.get("Audio.Audio_Codec_SelectedItem") != "None"
        and state.get("Audio.Audio_Stream_SelectedItem") != "none"
        and state.get("Audio.Audio_Quality_SelectedItem") not in ("None", "Mute")
    )


def _subtitle_enabled(state: AxiomState) -> bool:
    return (
        state.get("Format.Format_MediaType_SelectedItem") != "Audio"
        and state.get("Video.Video_Codec_SelectedItem") != "None"
        and state.get("Video.Video_Quality_SelectedItem") != "None"
    )


def _init(ctx: BuildContext) -> list[str]:
    return [ctx.ffmpeg, _overwrite(ctx.state)]


def _input(ctx: BuildContext, include_mux: bool = True) -> list[str]:
    state = ctx.state
    return [
        video.hw_accel_decode(state),
        "-i " + ctx.quote(ctx.input_path),
        audio.audio_mux(ctx) if include_mux else "",
        subtitles.subtitle_mux_args(ctx) if include_mux else "",
        video.hw_accel_transcode(state),
        fmt.cut_start(state, ctx),
        fmt.cut_end(state, ctx),
    ]


def _video_single(ctx: BuildContext, pass_name: str) -> list[str]:
    state = ctx.state
    codec = str(state.get("Video.Video_Codec_SelectedItem") or "")
    parts = [
        video.video_codec(state),
        video.encode_speed(state, pass_name),
        video.video_quality(ctx, pass_name),
        video.quality_params(ctx),
        video.pix_fmt(state),
        *video.color_args(state),
        video.optimize(state),
        video.fps(state),
        ctx.v_filter,
        video.vsync(state),
        video.aspect_ratio(state),
        video.images(state),
        streams.video_stream_maps(state, ctx),
    ]
    return parts


def _video_pass1(ctx: BuildContext, pass_name: str) -> list[str]:
    state = ctx.state
    codec = str(state.get("Video.Video_Codec_SelectedItem") or "")
    video.pass_params(ctx, codec, pass_name, "1")
    ctx.v_filter = video.video_filter(ctx)
    return [
        video.video_codec(state),
        video.quality_params(ctx),
        video.encode_speed(state, pass_name),
        video.video_quality(ctx, pass_name),
        video.pix_fmt(state),
        *video.color_args(state),
        video.optimize(state),
        video.fps(state),
        video.vsync(state),
        ctx.v_filter,
        video.aspect_ratio(state),
        video.images(state),
        video.pass1_modifier(codec, pass_name),
    ]


def _video_pass2(ctx: BuildContext, pass_name: str) -> list[str]:
    state = ctx.state
    codec = str(state.get("Video.Video_Codec_SelectedItem") or "")
    video.pass_params(ctx, codec, pass_name, "2")
    return [
        video.video_codec(state),
        video.quality_params(ctx),
        video.encode_speed(state, pass_name),
        video.video_quality(ctx, pass_name),
        video.pix_fmt(state),
        *video.color_args(state),
        video.fps(state),
        ctx.v_filter,
        video.aspect_ratio(state),
        video.images(state),
        video.optimize(state),
        streams.video_stream_maps(state, ctx),
        video.pass2_modifier(codec, pass_name),
    ]


def _audio_parts(ctx: BuildContext) -> list[str]:
    state = ctx.state
    if not _audio_enabled(state):
        return ["-an"]
    return [
        audio.audio_codec(state),
        audio.audio_quality(ctx),
        audio.compression_level(state),
        audio.sample_rate(state),
        audio.bit_depth(state),
        audio.channel(state),
        filters_audio.audio_filter(ctx),
        streams.audio_stream_maps(state, ctx),
        audio.audio_metadata(state),
    ]


def _subtitle_parts(ctx: BuildContext) -> list[str]:
    state = ctx.state
    if not _subtitle_enabled(state):
        return ["-sn"]
    return [
        subtitles.subtitle_codec(state),
        streams.subtitle_maps(state, ctx),
        subtitles.subtitle_metadata(state),
    ]


def _tail(ctx: BuildContext) -> list[str]:
    state = ctx.state
    chapters = ""
    if state.get("Format.Format_MediaType_SelectedItem") not in ("Image", "Sequence"):
        chapters = streams.chapters_maps(state, ctx)
    return [
        chapters,
        streams.format_maps(state, ctx),
        fmt.force_format(state.get("Format.Format_Container_SelectedItem")),
        ctx.threads,
        ctx.quote(ctx.output_path),
    ]


def single_pass(state: AxiomState, ctx: BuildContext) -> str:
    pass_name = str(state.get("Video.Video_Pass_SelectedItem") or "1 Pass")
    if _video_enabled(state):
        ctx.v_filter = video.video_filter(ctx)
        video_parts = _video_single(ctx, pass_name)
    else:
        video_parts = ["-vn"]
    parts = (
        _init(ctx)
        + _input(ctx)
        + video_parts
        + _audio_parts(ctx)
        + _subtitle_parts(ctx)
        + _tail(ctx)
    )
    return remove_line_breaks(join_args(*parts))


def two_pass_commands(state: AxiomState, ctx: BuildContext) -> tuple[str, str]:
    """Return ``(pass 1, pass 2)`` without choosing the shell's join operator."""
    pass_name = "2 Pass"
    video_parts_1 = (
        _video_pass1(ctx, pass_name) if _video_enabled(state) else ["-vn"]
    )
    pass1_parts = (
        _init(ctx)
        + _input(ctx, include_mux=False)
        + video_parts_1
        + ["-an", "-sn"]
        + [
            fmt.force_format(state.get("Format.Format_Container_SelectedItem")),
            ctx.threads,
            "NUL",
        ]
    )
    pass1 = remove_line_breaks(join_args(*pass1_parts))

    video_parts_2 = (
        _video_pass2(ctx, pass_name) if _video_enabled(state) else ["-vn"]
    )
    pass2_parts = (
        _init(ctx)
        + _input(ctx)
        + video_parts_2
        + _audio_parts(ctx)
        + _subtitle_parts(ctx)
        + _tail(ctx)
    )
    pass2 = remove_line_breaks(join_args(*pass2_parts))

    return pass1, pass2


def two_pass(state: AxiomState, ctx: BuildContext) -> str:
    pass1, pass2 = two_pass_commands(state, ctx)
    return pass1 + " && " + pass2


def generate(state: AxiomState) -> str:
    ctx = build_context(state)
    pass_name = str(state.get("Video.Video_Pass_SelectedItem") or "")
    if pass_name == "2 Pass" and state.get("Format.Format_MediaType_SelectedItem") == "Video":
        return two_pass(state, ctx)
    return single_pass(state, ctx)
