"""Generate the preset parity matrix from the original Axiom preset list.

The preset code has a handful of context-sensitive branches (the default ``Preset``
row and a few grouped presets), so the oracle is run once per built-in preset and once
per input-container category for the default row.

Usage:
    python tools/codegen/gen_preset_cases.py [--src PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = Path(r"G:\Codex_workspace\Axiom\source\Axiom\Axiom")
DEFAULT_OUT = HERE.parent / "parity_harness" / "preset_cases.json"

PRESET_ENTRY = re.compile(
    r'new\s+Preset\(\)\s*\{\s*Name\s*=\s*"(?P<name>[^"]+)"\s*,'
    r"\s*Category\s*=\s*(?P<category>true|false)",
)

CONTAINERS = [
    "webm",
    "mp4",
    "mkv",
    "m2v",
    "mpg",
    "avi",
    "ogv",
    "jpg",
    "png",
    "webp",
    "m4a",
    "mp3",
    "ogg",
    "flac",
    "wav",
]

EXCLUDED = {"Video Download", "Music Download"}


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def slug(name: str) -> str:
    value = re.sub(r"[^a-z0-9]+", "-", name.lower()).strip("-")
    return value or "preset"


def case(case_id: str, preset: str, container: str) -> dict:
    return {
        "id": case_id,
        "preset": preset,
        "state": {
            "Main.Input_Text": "C:\\Input\\clip.mkv",
            "Format.Format_Container_SelectedItem": container,
            "Configure.Shell_SelectedItem": "CMD",
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


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(DEFAULT_SRC))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    source = read(Path(args.src) / "ViewModel" / "MainViewModel.cs")
    names: list[str] = []
    for match in PRESET_ENTRY.finditer(source):
        if match.group("category") != "false":
            continue
        name = match.group("name")
        if name in EXCLUDED or name in names:
            continue
        names.append(name)

    cases: list[dict] = []
    for name in names:
        if name == "Preset":
            for container in CONTAINERS:
                cases.append(
                    case(f"prs-default-{container}", name, container)
                )
        else:
            cases.append(case(f"prs-{slug(name)}", name, "mp4"))

    Path(args.out).write_text(
        json.dumps(cases, indent=2) + "\n", encoding="utf-8"
    )
    print(f"wrote {len(cases)} preset cases for {len(names)} built-ins")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
