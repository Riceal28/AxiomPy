"""Media metadata used by Notify JSON callbacks."""

import json
import subprocess
from types import SimpleNamespace

from axiom.core.probe import MediaDetails, probe_details


def test_probe_details_parses_output_metadata(monkeypatch, tmp_path):
    output = tmp_path / "clip.mp4"
    output.write_bytes(b"x" * 123)
    payload = {
        "format": {
            "duration": "12.500000",
            "size": "123",
            "bit_rate": "1000000",
        },
        "streams": [
            {
                "codec_type": "video",
                "codec_name": "h264",
                "width": 1920,
                "height": 1080,
                "bit_rate": "900000",
            }
        ],
    }
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(
            stdout=json.dumps(payload)
        ),
    )

    details = probe_details(output, "ffprobe")

    assert details == MediaDetails(
        duration_seconds=12.5,
        file_size_bytes=123,
        video_codec="h264",
        width=1920,
        height=1080,
        overall_bitrate=1000000,
    )


def test_probe_details_handles_invalid_output(monkeypatch, tmp_path):
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *_args, **_kwargs: SimpleNamespace(stdout="not json"),
    )

    assert probe_details(tmp_path / "missing.mp4") == MediaDetails()
