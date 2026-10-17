"""Batch-script assembly ported from ``Generators/Arguments/Batch.cs``."""

from __future__ import annotations

from ..state import AxiomState
from . import pipeline
from .context import BuildContext, build_context


VIDEO_STREAM_EXTENSIONS = {
    ".wmv",
    ".webm",
    ".swf",
    ".qt",
    ".ogv",
    ".mp4",
    ".mov",
    ".m4v",
    ".flv",
    ".3gp",
    ".3g2",
}

VIDEO_FORMAT_EXTENSIONS = {
    ".vob",
    ".mpg",
    ".mpeg",
    ".mod",
    ".mkv",
    ".avi",
    ".asf",
}


def _video_entry_type(ctx: BuildContext) -> str:
    extension = ctx.input_ext.lower()
    kind = "stream" if extension in VIDEO_STREAM_EXTENSIONS else "format"
    if extension not in VIDEO_STREAM_EXTENSIONS and extension not in VIDEO_FORMAT_EXTENSIONS:
        kind = "stream"
    return kind + ("^=bit_rate" if ctx.shell == "CMD" else "=bit_rate")


def _audio_entry_type(ctx: BuildContext) -> str:
    kind = "format" if ctx.input_ext.lower() in (".flac", ".wav") else "stream"
    return kind + ("^=bit_rate" if ctx.shell == "CMD" else "=bit_rate")


def _cmd_video_auto(ctx: BuildContext) -> str:
    state = ctx.state
    if state.get("Video.Video_Codec_SelectedItem") == "Copy":
        return ""
    if state.get("Video.Video_Quality_SelectedItem") != "Auto":
        return ""
    if state.get("Format.Format_MediaType_SelectedItem") == "Image":
        return ""

    entry = _video_entry_type(ctx)
    return " ".join(
        [
            '& for /F "delims=" %S in (\'@'
            + ctx.ffprobe
            + ' -v error -select_streams v:0 -show_entries format^=size '
            + '-of default^=noprint_wrappers^=1:nokey^=1 "%~f" 2^>^&1\') '
            + "do (SET size=%S)",
            "& for /F %S in ('echo %size%') do (echo)",
            '& for /F "delims=" %D in (\'@'
            + ctx.ffprobe
            + ' -v error -select_streams v:0 -show_entries format^=duration '
            + '-of default^=noprint_wrappers^=1:nokey^=1 "%~f" 2^>^&1\') '
            + "do (SET duration=%D)",
            '& for /F "tokens=1 delims=." %R in (\'echo %duration%\') '
            + "do (SET duration=%R)",
            "& for /F %D in ('echo %duration%') do (echo)",
            '& for /F "delims=" %V in (\'@'
            + ctx.ffprobe
            + " -v error -select_streams v:0 -show_entries "
            + entry
            + ' -of default^=noprint_wrappers^=1:nokey^=1 "%~f" 2^>^&1\') '
            + "do (SET vBitRate=%V)",
            "& for /F %V in ('echo %vBitRate%') do (echo)",
            "& (if %V EQU N/A (SET /a vBitRate=%S*8/1000/%D*1000) "
            + "ELSE (echo Video Bit Rate Detected))",
            "& for /F %V in ('echo %vBitRate%') do (echo)",
        ]
    )


def _cmd_audio_auto(ctx: BuildContext) -> str:
    state = ctx.state
    codec = state.get("Audio.Audio_Codec_SelectedItem")
    if (
        codec == "Copy"
        or state.get("Audio.Audio_Quality_SelectedItem") != "Auto"
        or codec in ("FLAC", "PCM")
    ):
        return ""

    return " ".join(
        [
            '& for /F "delims=" %A in (\'@'
            + ctx.ffprobe
            + " -v error -select_streams a:0 -show_entries "
            + _audio_entry_type(ctx)
            + ' -of default^=noprint_wrappers^=1:nokey^=1 "%~f" 2^>^&1\') '
            + "do (SET aBitRate=%A)",
            "& for /F %A in ('echo %aBitRate%') do (echo)",
            '& (IF %A EQU N/A (SET aBitRate=320000))',
            '& (IF %A EQU "" (SET aBitRate=320000))',
            "& for /F %A in ('echo %aBitRate%') do (echo)",
        ]
    )


def _cmd_audio_limiter(ctx: BuildContext) -> str:
    state = ctx.state
    codec = state.get("Audio.Audio_Codec_SelectedItem")
    if codec == "Copy" or state.get("Audio.Audio_Quality_SelectedItem") != "Auto":
        return ""

    limits = {
        "Vorbis": 500000,
        "Opus": 510000,
        "AAC": 400000,
        "AC3": 640000,
        "MP2": 384000,
        "LAME": 320000,
    }
    if codec == "DTS":
        return (
            "& (IF %A lss 320000 (SET aBitRate=320000) "
            "ELSE (echo BitRate within DTS Limit of 320k)) "
            "& for /F %A in ('echo %aBitRate%') do (echo)"
            " & (IF %A gtr 1509075 (SET aBitRate=640000) "
            "ELSE (echo BitRate within DTS Limit of 1509.75k)) "
            "& for /F %A in ('echo %aBitRate%') do (echo)"
        )
    limit = limits.get(str(codec))
    if limit is None:
        return ""
    name = str(codec)
    return (
        f"& (IF %A gtr {limit} (SET aBitRate={limit}) "
        f"ELSE (echo BitRate within {name} Limit of {limit // 1000}k)) "
        "& for /F %A in ('echo %aBitRate%') do (echo)"
    )


def _power_shell_header(ctx: BuildContext) -> str:
    state = ctx.state
    parts = [
        f'$files = Get-ChildItem "{ctx.batch_input_directory.rstrip(chr(92))}"'
        f" -Filter *{ctx.input_ext};",
        "foreach ($f in $files) {"
        "$fullName = $f.FullName; "
        "$inputName = $f.Name; "
        "$outputName = (Get-Item $fullName).Basename;",
    ]

    if state.get("Video.Video_Quality_SelectedItem") == "Auto":
        parts.append(
            "$vBitrate = & "
            + ctx.ffprobe
            + " -v error -select_streams v:0 -show_entries "
            + _video_entry_type(ctx)
            + " -of default=noprint_wrappers=1:nokey=1 `\"$fullName`\";"
        )
    if state.get("Audio.Audio_Quality_SelectedItem") == "Auto":
        parts.append(
            "$aBitrate = & "
            + ctx.ffprobe
            + " -v error -select_streams a:0 -show_entries "
            + _audio_entry_type(ctx)
            + " -of default=noprint_wrappers=1:nokey=1 `\"$fullName`\";"
        )
        parts.append("if (!$aBitrate) { $aBitrate = 0};")
        limiter = {
            "Vorbis": (
                "if ($aBitrate -gt 500000) { $aBitrate = 500000 };"
            ),
            "Opus": (
                "if ($aBitrate -gt 510000) { $aBitrate = 510000 };"
            ),
            "AAC": (
                "if ($aBitrate -gt 400000) { $aBitrate = 400000 };"
            ),
            "AC3": (
                "if ($aBitrate -gt 640000) { $aBitrate = 640000 };"
            ),
            "DTS": (
                "if ($aBitrate -lt 320000) { $aBitrate = 320000 };"
                "if ($aBitrate -gt 1509075) { $aBitrate = 1509075 };"
            ),
            "MP2": (
                "if ($aBitrate -gt 384000) { $aBitrate = 384000 };"
            ),
            "LAME": (
                "if ($aBitrate -gt 320000) { $aBitrate = 320000 };"
            ),
        }.get(str(state.get("Audio.Audio_Codec_SelectedItem")))
        if limiter:
            parts.append(limiter)

    return " ".join(parts)


def _inner_command(state: AxiomState, ctx: BuildContext) -> str:
    pass_name = state.get("Video.Video_Pass_SelectedItem")
    if pass_name == "2 Pass":
        first, second = pipeline.two_pass_commands(state, ctx)
        operator = " ; " if ctx.shell == "PowerShell" else " && "
        return first + operator + second
    return pipeline.single_pass(state, ctx)


def generate(state: AxiomState) -> str:
    ctx = build_context(state)
    command = _inner_command(state, ctx)

    if ctx.shell == "PowerShell":
        return _power_shell_header(ctx) + " " + command + " }"

    header = (
        f'cd /d "{ctx.batch_input_directory}" &&  '
        f"for %f in (*{ctx.input_ext}) do (echo)"
    )
    for fragment in (_cmd_video_auto(ctx), _cmd_audio_auto(ctx), _cmd_audio_limiter(ctx)):
        if fragment:
            header += " " + fragment
    return header + " && " + command
