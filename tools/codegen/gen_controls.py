"""Generate ``axiom/core/controls_data.py`` from the original ``Controls/**`` sources.

The control layer is written as long runs of two perfectly regular patterns, so the
rules can be lifted mechanically instead of transcribed:

* **enabled** - ``bool? x_IsEnabled = codec.controls_Enabled.FirstOrDefault().X;`` followed
  by ``if (!x_IsEnabled.HasValue) field = true; else field = x_IsEnabled;`` (the guard
  variable is captured verbatim, because the original has at least one copy/paste slip
  that changes behaviour),
* **selected** - ``string x = codec.controls_Selected.FirstOrDefault().X;`` with either a
  plain "set when non-empty", or "set when non-empty else fall back to the previous
  codec's item / the first item".

Usage:
    python tools/codegen/gen_controls.py [--src PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import pprint
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = Path(r"G:\Codex_workspace\Axiom\source\Axiom\Axiom")
DEFAULT_OUT = HERE.parent.parent / "src" / "axiom" / "core" / "controls_data.py"

KINDS = {
    "video": "Controls/VideoControls.cs",
    "audio": "Controls/AudioControls.cs",
    "subtitle": "Controls/SubtitleControls.cs",
}

ENABLED = re.compile(
    r"bool\?\s+(?P<key>\w+)_IsEnabled\s*=\s*_codec_class\[[^\]]*\]\.controls_Enabled\."
    r"FirstOrDefault\(\)\.(?P<prop>\w+);\s*"
    r"if\s*\(!(?P<guard>\w+)_IsEnabled\.HasValue\)\s*"
    r"VM\.(?P<view>\w+)View\.(?P<field>\w+)\s*=\s*true;\s*"
    r"else\s*VM\.\w+View\.(?P<field2>\w+)\s*=\s*(?P<key2>\w+)_IsEnabled;",
    re.DOTALL,
)

SELECTED_BLOCK = re.compile(
    r"string\s+(?P<key>\w+)\s*=\s*_codec_class\[[^\]]*\]\.controls_Selected\."
    r"FirstOrDefault\(\)\.(?P<prop>\w+);(?P<body>.*?)(?=\n\s{16}string\s+\w+\s*=|"
    r"\n\s{16}//\s*-{5,}\n\s{16}//\s+\w+\n\s{16}//\s*-{5,}|"
    r"\n\s{16}//\s*-{5,}\n\s{16}//\s+Filters|\Z)",
    re.DOTALL,
)

TARGET = re.compile(r"VM\.(?P<view>\w+)View\.(?P<field>\w+)\s*=\s*(?P<key>\w+)\s*;")
PREVIOUS = re.compile(
    r"MainWindow\.SelectedItem\(\s*VM\.\w+View\.(?P<items>\w+)[^,]*,\s*"
    r"MainWindow\.(?P<previous>\w+)\s*\)"
)

FLAG = re.compile(
    r"if\s*\(VM\.(?P<view>\w+)View\.(?P<gate>\w+)\s*==\s*true\)\s*\{\s*"
    r"bool\?\s+(?P<key>\w+)\s*=\s*_codec_class\[[^\]]*\]\.controls_(?P<group>Checked|Expanded)"
    r"\.FirstOrDefault\(\)\.(?P<prop>\w+);\s*"
    r"if\s*\(!(?P=key)\.HasValue\)\s*VM\.\w+View\.(?P<field>\w+)\s*=\s*true;\s*"
    r"else\s*VM\.\w+View\.(?P<field2>\w+)\s*=\s*(?P=key);\s*\}\s*"
    r"else\s*\{\s*VM\.\w+View\.(?P<field3>\w+)\s*=\s*false;",
    re.DOTALL,
)


def parse_flags(text: str) -> list[dict]:
    """``controls_Checked`` / ``controls_Expanded`` overrides, gated on an enable flag."""
    rules = []
    for match in FLAG.finditer(text):
        rules.append(
            {
                "group": match.group("group"),
                "prop": match.group("prop"),
                "gate": match.group("gate"),
                "view": match.group("view"),
                "field": match.group("field"),
            }
        )
    return rules


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def strip_comments(text: str) -> str:
    text = re.sub(r"^[ \t]*//.*$", "", text, flags=re.MULTILINE)
    return re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)


def parse_enabled(text: str) -> list[dict]:
    rules = []
    for match in ENABLED.finditer(text):
        rules.append(
            {
                "prop": match.group("prop"),
                "guard": match.group("guard"),
                "view": match.group("view"),
                "field": match.group("field"),
            }
        )
    return rules


def parse_selected(text: str) -> list[dict]:
    rules = []
    for match in SELECTED_BLOCK.finditer(text):
        body = match.group("body")
        target = TARGET.search(body)
        if target is None or target.group("key") != match.group("key"):
            continue
        rule = {
            "prop": match.group("prop"),
            "view": target.group("view"),
            "field": target.group("field"),
            "previousItems": None,
            "previousItem": None,
        }
        previous = PREVIOUS.search(body)
        if previous:
            rule["previousItems"] = previous.group("items")
            rule["previousItem"] = previous.group("previous")
        rules.append(rule)
    return rules


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(DEFAULT_SRC))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    src = Path(args.src)
    data = {}
    for kind, relative in KINDS.items():
        text = strip_comments(read(src / relative))
        data[kind] = {
            "enabled": parse_enabled(text),
            "selected": parse_selected(text),
            "flags": parse_flags(text),
        }
        print(
            f"{kind}: {len(data[kind]['enabled'])} enabled, "
            f"{len(data[kind]['selected'])} selected, "
            f"{len(data[kind]['flags'])} checked/expanded rules"
        )

    header = [
        '"""Generated by tools/codegen/gen_controls.py - do not edit by hand.',
        "",
        "Declarative form of the codec control layer: for every codec kind the",
        "``controls_Enabled`` overrides (with the guard variable the original actually",
        "tested) and the ``controls_Selected`` overrides (including whether the previous",
        "codec's item is restored when the codec does not specify one).",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "CONTROLS: dict = ",
    ]
    text = "\n".join(header) + pprint.pformat(data, width=110, sort_dicts=False) + "\n"
    Path(args.out).write_text(text, encoding="utf-8")
    print("wrote " + args.out)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
