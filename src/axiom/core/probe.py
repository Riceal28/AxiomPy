"""FFprobe wrapper - the Python counterpart of ``Analyze/FFprobe.cs``.

The original ran one ffprobe process per property and parsed CSV output.  Here the same
``-show_entries`` queries are issued and immediately turned into a structured object.
"""

from __future__ import annotations

import json
import subprocess
from dataclasses import dataclass
from pathlib import Path


@dataclass
class MediaInfo:
    """The subset of ffprobe results Axiom's generators consume."""

    video_codec: str = ""
    video_bit_rate: str = ""
    audio_codec: str = ""
    audio_bit_rate: str = ""
    size: str = ""  # "1920x1080"
    duration: str = ""  # seconds, ffprobe's raw value
    frame_rate: str = ""


@dataclass
class MediaDetails:
    """Output metadata used by JSON notifications."""

    duration_seconds: float | None = None
    file_size_bytes: int | None = None
    video_codec: str = ""
    width: int | None = None
    height: int | None = None
    overall_bitrate: int | None = None


def _int_value(value: object) -> int | None:
    try:
        return int(str(value))
    except (TypeError, ValueError):
        return None


def _float_value(value: object) -> float | None:
    try:
        return float(str(value))
    except (TypeError, ValueError):
        return None


def probe_details(
    input_path: Path | str,
    ffprobe: Path | str = "ffprobe",
) -> MediaDetails:
    """Read duration, size, codec and dimensions from one media file."""
    if not str(input_path):
        return MediaDetails()
    try:
        completed = subprocess.run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-show_entries",
                "format=duration,size,bit_rate:"
                "stream=codec_type,codec_name,width,height,bit_rate",
                "-of",
                "json",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        payload = json.loads(completed.stdout or "{}")
    except (
        OSError,
        ValueError,
        TypeError,
        subprocess.SubprocessError,
    ):
        return MediaDetails()

    if not isinstance(payload, dict):
        return MediaDetails()
    format_info = payload.get("format") or {}
    if not isinstance(format_info, dict):
        format_info = {}
    streams = payload.get("streams") or []
    if not isinstance(streams, list):
        streams = []
    video = next(
        (
            stream
            for stream in streams
            if isinstance(stream, dict)
            and stream.get("codec_type") == "video"
        ),
        {},
    )
    size = _int_value(format_info.get("size"))
    if size is None:
        try:
            size = Path(input_path).stat().st_size
        except OSError:
            size = None
    duration = _float_value(format_info.get("duration"))
    if duration is None:
        duration = _float_value(video.get("duration"))
    bitrate = _int_value(format_info.get("bit_rate"))
    if bitrate is None:
        bitrate = _int_value(video.get("bit_rate"))
    return MediaDetails(
        duration_seconds=duration,
        file_size_bytes=size,
        video_codec=str(video.get("codec_name") or ""),
        width=_int_value(video.get("width")),
        height=_int_value(video.get("height")),
        overall_bitrate=bitrate,
    )


def _merge_details(
    primary: MediaDetails,
    fallback: MediaDetails,
) -> MediaDetails:
    return MediaDetails(
        duration_seconds=(
            primary.duration_seconds
            if primary.duration_seconds is not None
            else fallback.duration_seconds
        ),
        file_size_bytes=(
            primary.file_size_bytes
            if primary.file_size_bytes is not None
            else fallback.file_size_bytes
        ),
        video_codec=primary.video_codec or fallback.video_codec,
        width=(
            primary.width
            if primary.width is not None
            else fallback.width
        ),
        height=(
            primary.height
            if primary.height is not None
            else fallback.height
        ),
        overall_bitrate=(
            primary.overall_bitrate
            if primary.overall_bitrate is not None
            else fallback.overall_bitrate
        ),
    )


def probe_notification_metadata(
    input_path: Path | None,
    output_path: Path | None,
    ffprobe: Path | str = "ffprobe",
) -> dict[str, str]:
    """Return the metadata fields consumed by Notify templates."""

    details = MediaDetails()
    if output_path is not None and output_path.is_file():
        details = probe_details(output_path, ffprobe)
        needs_fallback = details.duration_seconds is None
    else:
        needs_fallback = True
    if (
        input_path is not None
        and input_path.is_file()
        and needs_fallback
    ):
        details = _merge_details(
            details,
            probe_details(input_path, ffprobe),
        )
    size = 0
    if output_path is not None and output_path.is_file():
        try:
            size = output_path.stat().st_size
        except OSError:
            size = 0
    duration = details.duration_seconds
    bitrate = details.overall_bitrate
    return {
        "duration_seconds": (
            f"{duration:.3f}" if duration is not None else "null"
        ),
        "file_size_bytes": str(size),
        "video_codec": details.video_codec,
        "width": (
            str(details.width) if details.width is not None else "null"
        ),
        "height": (
            str(details.height) if details.height is not None else "null"
        ),
        "overall_bitrate": (
            str(bitrate) if bitrate is not None else "null"
        ),
        "duration": f"{duration:.3f}" if duration is not None else "",
        "size": str(size) if size else "",
        "bitrate": str(bitrate) if bitrate is not None else "",
    }


def _query(ffprobe: Path | str, args: list[str]) -> str:
    completed = subprocess.run(
        [str(ffprobe), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        check=False,
    )
    return completed.stdout.strip()


def _stream_entry(ffprobe: Path | str, input_path: Path | str, entry: str) -> str:
    return _query(
        ffprobe,
        ["-i", str(input_path), "-select_streams", "v:0", "-show_entries", entry,
         "-v", "quiet", "-of", 'csv=p=0'],
    )


def probe(input_path: Path | str, ffprobe: Path | str = "ffprobe", entry_type: str = "format") -> MediaInfo:
    """Collect the metadata the generators need (mirrors FFprobe.Metadata())."""
    info = MediaInfo()
    info.frame_rate = _stream_entry(ffprobe, input_path, "stream=r_frame_rate")
    info.size = _stream_entry(ffprobe, input_path, "format=scale")
    info.duration = _stream_entry(ffprobe, input_path, "format=duration")
    info.video_codec = _stream_entry(ffprobe, input_path, "stream=codec_name")
    info.video_bit_rate = _stream_entry(ffprobe, input_path, f"{entry_type}=bit_rate")
    info.audio_codec = _query(
        ffprobe,
        ["-i", str(input_path), "-select_streams", "a:0", "-show_entries", "stream=codec_name",
         "-v", "quiet", "-of", 'csv=p=0'],
    )
    info.audio_bit_rate = _query(
        ffprobe,
        ["-i", str(input_path), "-select_streams", "a:0", "-show_entries", "stream=bit_rate",
         "-v", "quiet", "-of", 'csv=p=0'],
    )
    return info


def duration_timestamp(seconds: str) -> str:
    """Format seconds as ``HH:MM:SS.mmm`` exactly like FFprobe.CutDuration."""
    if not seconds or not seconds.strip():
        return seconds
    total = float(seconds)
    hours, remainder = divmod(total, 3600.0)
    minutes, secs = divmod(remainder, 60.0)
    whole = int(secs)
    millis = int(round((secs - whole) * 1000))
    return f"{int(hours):02d}:{int(minutes):02d}:{whole:02d}.{millis:03d}"

