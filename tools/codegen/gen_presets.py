"""Generate ``axiom/core/presets_data.py`` from the C# preset snapshots.

The oracle writes the ViewModel state immediately after ``Profiles.Presets.SetPreset``.
This tool extracts the properties each C# branch assigns and takes their values from
that snapshot.  The default ``Preset`` row has separate video and audio variants.

Usage:
    python tools/codegen/gen_presets.py [--golden DIR] [--out PATH]
"""

from __future__ import annotations

import argparse
import json
import pprint
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_SRC = Path(r"G:\Codex_workspace\Axiom\source\Axiom\Axiom")
DEFAULT_GOLDEN = REPO / "tests" / "golden"
DEFAULT_OUT = REPO / "src" / "axiom" / "core" / "presets_data.py"

EXCLUDED_KEYS = {
    "Main.Preset_SelectedItem",
}

AUDIO_CONTAINERS = {"m4a", "mp3", "ogg", "flac", "wav"}

GROUP_PREFIX = {
    "MainView": "Main",
    "FormatView": "Format",
    "VideoView": "Video",
    "AudioView": "Audio",
    "SubtitleView": "Subtitle",
    "FilterVideoView": "FilterVideo",
    "FilterAudioView": "FilterAudio",
    "ConfigureView": "Configure",
}

ASSIGNMENT = re.compile(
    r"VM\.(?P<group>\w+View)\.(?P<name>\w+)\s*="
)


def is_preset_value(key: str) -> bool:
    """Only keep values actually owned by the preset assignments."""
    group, _, prop = key.partition(".")
    if group in ("Main", "Configure"):
        return False
    if prop.startswith("_"):
        return False
    if prop.endswith("_Items") or prop.endswith("_SelectedIndex"):
        return False
    if key in ("FilterVideo.SelectiveColorList", "FilterVideo.SelectiveColor"):
        return False
    return True


def strip_comments(text: str) -> str:
    out: list[str] = []
    index = 0
    in_string = False
    while index < len(text):
        char = text[index]
        if in_string:
            out.append(char)
            if char == "\\" and index + 1 < len(text):
                out.append(text[index + 1])
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            out.append(char)
            index += 1
            continue
        if text.startswith("//", index):
            newline = text.find("\n", index)
            index = len(text) if newline == -1 else newline
            continue
        out.append(char)
        index += 1
    return "".join(out)


def matching(text: str, start: int, opening: str, closing: str) -> int:
    depth = 0
    in_string = False
    index = start
    while index < len(text):
        char = text[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
        elif char == opening:
            depth += 1
        elif char == closing:
            depth -= 1
            if depth == 0:
                return index
        index += 1
    raise ValueError(f"unbalanced {opening}{closing}")


def if_blocks(text: str) -> list[tuple[str, str, int, int]]:
    result = []
    depth = 0
    in_string = False
    index = 0
    while index < len(text):
        char = text[index]
        if in_string:
            if char == "\\":
                index += 2
                continue
            if char == '"':
                in_string = False
            index += 1
            continue
        if char == '"':
            in_string = True
            index += 1
            continue
        if char == "{":
            depth += 1
            index += 1
            continue
        if char == "}":
            depth -= 1
            index += 1
            continue
        if depth == 0 and text.startswith("if", index):
            before = text[index - 1] if index else " "
            after = text[index + 2] if index + 2 < len(text) else " "
            if not (before.isalnum() or before == "_") and not (
                after.isalnum() or after == "_"
            ):
                open_paren = text.find("(", index + 2)
                close_paren = matching(text, open_paren, "(", ")")
                condition = text[open_paren + 1 : close_paren]
                open_brace = text.find("{", close_paren + 1)
                close_brace = matching(text, open_brace, "{", "}")
                result.append(
                    (condition, text[open_brace + 1 : close_brace], open_brace, close_brace)
                )
                index = close_brace + 1
                continue
        index += 1
    return result


def preset_names(condition: str) -> set[str]:
    return set(re.findall(r'Preset_SelectedItem\s*==\s*"([^"]+)"', condition))


def selected_text(block: str, preset: str, source_container: str) -> str:
    nested = if_blocks(block)
    preset_nested = [item for item in nested if preset_names(item[0])]
    if preset_nested:
        pieces = []
        cursor = 0
        for condition, body, start, end in preset_nested:
            pieces.append(block[cursor:start])
            if preset in preset_names(condition):
                pieces.append(selected_text(body, preset, source_container))
            cursor = end + 1
        pieces.append(block[cursor:])
        return "\n".join(pieces)

    container_nested = [
        item for item in nested if "Format_Container_SelectedItem" in item[0]
    ]
    if preset == "Preset" and container_nested:
        chosen = container_nested[1] if source_container in AUDIO_CONTAINERS else container_nested[0]
        pieces = []
        cursor = 0
        for _, _, start, end in container_nested:
            pieces.append(block[cursor:start])
            cursor = end + 1
        pieces.append(block[cursor:])
        pieces.append(selected_text(chosen[1], preset, source_container))
        return "\n".join(pieces)

    return block


def assigned_keys(source: str, preset: str, source_container: str) -> set[str]:
    body_match = re.search(r"public\s+static\s+void\s+SetPreset\s*\([^)]*\)\s*\{", source)
    if not body_match:
        raise ValueError("SetPreset not found")
    body_open = body_match.end() - 1
    body = source[body_open + 1 : matching(source, body_open, "{", "}")]
    for condition, block, _, _ in if_blocks(body):
        if preset in preset_names(condition):
            selected = selected_text(block, preset, source_container)
            return {
                GROUP_PREFIX[match.group("group")] + "." + match.group("name")
                for match in ASSIGNMENT.finditer(selected)
            }
    raise ValueError(f"preset branch not found: {preset}")


def read_json(path: Path) -> dict:
    return json.loads(path.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(DEFAULT_SRC))
    parser.add_argument("--golden", default=str(DEFAULT_GOLDEN))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    import sys

    sys.path.insert(0, str(REPO / "src"))
    from axiom.core.defaults import DEFAULTS
    from axiom.core.state import AxiomState
    from axiom.core.dump import dump_state

    golden = Path(args.golden)
    source_text = strip_comments(
        (Path(args.src) / "Presets" / "Presets.cs").read_text(
            encoding="utf-8-sig", errors="replace"
        )
    )
    entries: dict[str, list[tuple[str, dict]]] = {}
    for path in sorted(golden.glob("prs-*.json")):
        payload = read_json(path)
        if payload.get("error"):
            raise SystemExit(f"oracle failed for {payload.get('id')}: {payload['error']}")
        preset = payload.get("preset")
        snapshot = payload.get("presetState")
        if not preset or not snapshot:
            continue
        entries.setdefault(preset, []).append((payload["id"], snapshot))

    variants: dict[str, dict[str, dict]] = {}
    builtins: dict[str, dict] = {}
    for preset, items in entries.items():
        if preset == "Preset":
            video = None
            audio = None
            for case_id, snapshot in items:
                container = snapshot.get("Format.Format_Container_SelectedItem")
                source = (read_json(golden / f"{case_id}.json")["state"]
                          .get("Format.Format_Container_SelectedItem"))
                if source in AUDIO_CONTAINERS:
                    audio = audio or snapshot
                else:
                    video = video or snapshot
            for group, snapshot in (("video", video), ("audio", audio)):
                if snapshot is None:
                    raise SystemExit(f"missing default {group} preset snapshot")
                source_container = (
                    read_json(golden / "prs-default-mp3.json")["state"]
                    .get("Format.Format_Container_SelectedItem")
                    if group == "audio"
                    else read_json(golden / "prs-default-mp4.json")["state"]
                    .get("Format.Format_Container_SelectedItem")
                )
                keys = assigned_keys(source_text, preset, source_container)
                changed = {
                    key: snapshot[key]
                    for key in keys
                    if key in snapshot
                    and key not in EXCLUDED_KEYS
                    and is_preset_value(key)
                }
                for key, value in snapshot.items():
                    if key.startswith(("FilterVideo.", "FilterAudio.")) and is_preset_value(key):
                        changed[key] = value
                variants.setdefault("Preset", {})[group] = changed
            continue

        snapshot = items[0][1]
        source_container = next(
            read_json(golden / f"{case_id}.json")["state"].get(
                "Format.Format_Container_SelectedItem"
            )
            for case_id, _ in items
        )
        keys = assigned_keys(source_text, preset, source_container)
        changed = {
            key: snapshot[key]
            for key in keys
            if key in snapshot
            and key not in EXCLUDED_KEYS
            and is_preset_value(key)
        }
        for key, value in snapshot.items():
            if key.startswith(("FilterVideo.", "FilterAudio.")) and is_preset_value(key):
                changed[key] = value
        builtins[preset] = changed

    # Validate that replaying the extracted deltas reproduces every snapshot field.
    for preset, items in entries.items():
        for case_id, snapshot in items:
            state = AxiomState()
            if preset == "Preset":
                source = read_json(golden / f"{case_id}.json")["state"]
                source_container = source.get("Format.Format_Container_SelectedItem")
                group = "audio" if source_container in AUDIO_CONTAINERS else "video"
                state.update(variants["Preset"][group])
                expected_keys = set(variants["Preset"][group])
            else:
                state.update(builtins[preset])
                expected_keys = set(builtins[preset])
            actual = dump_state(state)
            mismatches = {
                key: (snapshot.get(key), actual.get(key))
                for key in expected_keys
                if actual.get(key) != snapshot.get(key)
            }
            if mismatches:
                raise SystemExit(
                    f"{case_id}: preset replay differs: {mismatches}"
                )

    lines = [
        '"""Generated from the original Axiom preset snapshots. Do not edit by hand."""',
        "",
        "BUILTIN_PRESETS = "
        + pprint.pformat(builtins, width=100, sort_dicts=True),
        "",
        "PRESET_VARIANTS = "
        + pprint.pformat(variants, width=100, sort_dicts=True),
        "",
    ]
    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(
        f"wrote {len(builtins)} built-ins and "
        f"{sum(len(value) for value in variants.values())} default variants"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
