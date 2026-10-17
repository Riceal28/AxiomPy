"""Generate ``axiom/core/defaults.py`` from the original ViewModel sources.

The WPF application keeps its whole state in eight ``ViewModel`` classes (~615
properties).  Rather than hand-copying that surface (and its startup defaults), the
values are extracted mechanically:

* property declarations give the name and CLR type,
* ``LoadControlsDefaults`` / ``LoadConfigDefaults`` / ``LoadFilterVideoDefaults`` /
  ``LoadFilterAudioDefaults`` give the startup value,
* literal initialisers on the declaration line are used when there is no assignment.

Usage:
    python tools/codegen/gen_defaults.py [--src PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import os
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
DEFAULT_SRC = Path(
    os.environ.get(
        "AXIOM_REFERENCE_SRC",
        REPO.parent / "Axiom" / "source" / "Axiom" / "Axiom",
    )
)
DEFAULT_OUT = HERE.parent.parent / "src" / "axiom" / "core" / "defaults.py"

GROUP_FILES = {
    "Main": "MainViewModel.cs",
    "Format": "FormatViewModel.cs",
    "Video": "VideoViewModel.cs",
    "Audio": "AudioViewModel.cs",
    "Subtitle": "SubtitleViewModel.cs",
    "FilterVideo": "FilterVideoViewModel.cs",
    "FilterAudio": "FilterAudioViewModel.cs",
    "Configure": "ConfigureViewModel.cs",
}

PROPERTY = re.compile(
    r"^[ \t]*public\s+(?P<type>[\w\.<>,\[\]\?\s]+?)\s+(?P<name>\w+)\s*"
    r"(?:\{\s*get;\s*set;\s*\}|=\s*(?P<literal>[^;]+);|(?=\r?\n[ \t]*\{))",
    re.MULTILINE,
)
ASSIGNMENT = re.compile(
    r"^\s*(?:[A-Za-z_]\w*\.)*(?P<name>\w+)\s*=\s*(?P<value>[^;]+);",
    re.MULTILINE,
)
FIELD = re.compile(
    r"^[ \t]*public\s+(?P<type>[\w\.<>,\[\]\?\s]+?)\s+(?P<name>\w+)\s*(?:=\s*(?P<literal>[^;]+))?;",
    re.MULTILINE,
)
BACKING = re.compile(
    r"^[ \t]*(?:public|private|protected|internal)?[ \t]*(?:static[ \t]+)?"
    r"[\w<>\[\],\?\.]+[ \t]+_(?P<name>\w+)[ \t]*=[ \t]*(?P<value>[^;]+);",
    re.MULTILINE,
)
DEFAULTS_METHOD = re.compile(
    r"public\s+(?:static\s+)?void\s+(?P<name>Load\w*Defaults)\s*\([^)]*\)\s*\{",
    re.MULTILINE,
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def method_body(text: str, start: int) -> str:
    depth = 0
    for index in range(start, len(text)):
        if text[index] == "{":
            depth += 1
        elif text[index] == "}":
            depth -= 1
            if depth == 0:
                return text[start + 1 : index]
    return text[start:]


COLLECTION = re.compile(
    r"^new\s+(?:ObservableCollection|List)<[^>]+>\s*\(\s*\)\s*\{(?P<body>.*)\}\s*$",
    re.DOTALL,
)
OBJECT_ENTRY = re.compile(
    r"^new\s+[\w\.<>]+\s*\(\s*\)\s*\{(?P<body>.*)\}\s*$", re.DOTALL
)


def strip_comments(text: str) -> str:
    """Remove C# line comments, ignoring ``//`` inside string literals."""
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
            if newline == -1:
                break
            index = newline
            continue
        out.append(char)
        index += 1
    return "".join(out)


def split_top_level(text: str, separator: str = ",") -> list[str]:
    """Split on ``separator`` outside strings and (), {}, []."""
    parts: list[str] = []
    start = 0
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
        elif char in "({[":
            depth += 1
        elif char in ")}]":
            depth -= 1
        elif char == separator and depth == 0:
            parts.append(text[start:index])
            start = index + 1
        index += 1
    tail = text[start:]
    if tail.strip():
        parts.append(tail)
    return parts


def python_literal(raw: str):
    """Convert a C# literal / simple expression into a Python value."""
    value = raw.strip()
    if re.fullmatch(r"new\s+(?:ObservableCollection|List)<[^>]+>\s*\(\s*\)", value):
        return []
    if value in ("true", "True"):
        return True
    if value in ("false", "False"):
        return False
    if value in ("null", "string.Empty", "String.Empty"):
        return ""
    string_match = re.fullmatch(r'@"(.*)"', value, re.DOTALL)
    if string_match:
        return string_match.group(1).replace('""', '"')
    string_match = re.fullmatch(r'"(.*)"', value, re.DOTALL)
    if string_match:
        return (
            string_match.group(1)
            .replace('\\"', '"')
            .replace("\\\\", "\\")
        )
    if re.fullmatch(r"-?\d+(\.\d+)?", value):
        return float(value) if "." in value else int(value)
    collection = COLLECTION.match(value)
    if collection:
        entries: list[object] = []
        for entry in split_top_level(strip_comments(collection.group("body"))):
            entry = entry.strip()
            if not entry:
                continue
            parsed = python_literal(entry)
            if parsed is not None:
                entries.append(parsed)
        return entries
    obj = OBJECT_ENTRY.match(value)
    if obj:
        row: dict[str, object] = {}
        for entry in split_top_level(strip_comments(obj.group("body"))):
            key, separator, raw_value = entry.partition("=")
            if not separator:
                continue
            row[key.strip()] = python_literal(raw_value)
        return row
    return None  # complex initialiser: fall back to the CLR default for the type


def clr_default(type_name: str):
    if type_name.endswith("?"):
        return None
    if "bool" in type_name:
        return False
    if "int" in type_name or "double" in type_name:
        return 0
    # In C# an uninitialised reference type is null; ViewModel constructors and
    # Load*Defaults assign the real "" defaults where the UI expects them.
    if type_name in ("string", "String"):
        return None
    return None


def parse_file(path: Path) -> dict[str, object]:
    text = read(path)
    values: dict[str, object] = {}

    for match in PROPERTY.finditer(text):
        # Only top level members of the ViewModel class: nested helper classes
        # (Preset, VideoCodec, ...) are handled separately by the UI layer.
        prefix = text[: match.start()]
        if prefix.count("{") - prefix.count("}") != 2:
            continue
        name = match.group("name")
        type_name = match.group("type").strip()
        literal = match.group("literal")
        value = clr_default(type_name)
        if literal is not None:
            parsed = python_literal(literal)
            if parsed is not None:
                value = parsed
        values.setdefault(name, value)

    # Public fields are part of the state too (e.g. Video_Codec, Audio_Codec).
    for match in FIELD.finditer(text):
        prefix = text[: match.start()]
        if prefix.count("{") - prefix.count("}") != 2:
            continue
        value = clr_default(match.group("type").strip())
        literal = match.group("literal")
        if literal is not None:
            parsed = python_literal(literal)
            if parsed is not None:
                value = parsed
        values.setdefault(match.group("name"), value)

    # Defaults usually live on the backing field, not the property declaration.
    for match in BACKING.finditer(text):
        name = match.group("name")
        if name not in values:
            continue
        parsed = python_literal(match.group("value"))
        if parsed is not None:
            values[name] = parsed

    # Explicit startup defaults win; they run when the ViewModel is constructed.
    for method in DEFAULTS_METHOD.finditer(text):
        body_start = text.find("{", method.end() - 1)
        for assign in ASSIGNMENT.finditer(method_body(text, body_start)):
            name = assign.group("name")
            if name not in values:
                continue
            parsed = python_literal(assign.group("value"))
            if parsed is not None:
                values[name] = parsed

    # Properties write through to their public/private backing field.  The harness
    # dumps both, so keep the pair in sync exactly like AxiomState.set() does.
    for name in list(values):
        alias = "_" + name
        if not name.startswith("_") and alias in values:
            values[alias] = values[name]
    return values


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(DEFAULT_SRC))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    src = Path(args.src) / "ViewModel"
    groups = {group: parse_file(src / filename) for group, filename in GROUP_FILES.items()}

    lines = [
        '"""Generated by tools/codegen/gen_defaults.py - do not edit by hand.',
        "",
        "Startup state of the original WPF ViewModels (name -> value).  Keys are",
        "``Group.Property`` so they line up with the parity-harness case files.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "DEFAULTS: dict[str, object] = {",
    ]
    total = 0
    for group, values in groups.items():
        lines.append(f"    # --- {group} ---")
        for name, value in values.items():
            total += 1
            lines.append(f"    {group + '.' + name!r}: {value!r},")
        lines.append("")
    lines.append("}")
    lines.append("")
    lines.append(f"PROPERTY_COUNT = {total}")
    lines.append("")

    Path(args.out).write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {total} properties to {args.out}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
