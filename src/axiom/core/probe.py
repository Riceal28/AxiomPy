"""FFprobe wrapper - the Python counterpart of ``Analyze/FFprobe.cs``.

The original ran one ffprobe process per property and parsed CSV output.  Here the same
``-show_entries`` queries are issued and immediately turned into a structured object.
"""

from __future__ import annotations

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

