"""Generate ``axiom/core/codecs_data.py`` from the original ``Codecs/**`` sources.

Every codec class in the original is a bag of object initialisers plus one
``EncodingPass()`` switch that drives the pass/CRF control state.  Both are regular
enough to translate mechanically, which keeps 40 files (~7.3k lines of C#) in sync
without hand copying:

* ``codec`` / ``encodeSpeed`` / ``quality`` / ``optimize`` / ``controls_*`` become lists
  of dicts,
* ``pixelFormat`` / ``tune`` / ``profile`` / ``level`` become lists of strings,
* ``EncodingPass()`` becomes a ``qualityPass`` table keyed by the selected quality, with
  the ``passUserSelected`` guard captured as ``userSelectedAssign``.

Usage:
    python tools/codegen/gen_codecs.py [--src PATH] [--out PATH]
"""

from __future__ import annotations

import argparse
import pprint
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = Path(r"G:\Codex_workspace\Axiom\source\Axiom\Axiom")
DEFAULT_OUT = HERE.parent.parent / "src" / "axiom" / "core" / "codecs_data.py"

KINDS = {
    "Codecs/Video": "video",
    "Codecs/Audio": "audio",
    "Codecs/Image": "image",
    "Codecs/Subtitle": "subtitle",
}

PROPERTY = re.compile(
    r"^[ \t]*public\s+(?P<type>[\w\.<>,\[\]\?\s]+?)\s+(?P<name>\w+)\s*\{\s*get;\s*set;\s*\}\s*=\s*",
    re.MULTILINE,
)
CLASS = re.compile(r"public\s+class\s+(?P<name>\w+)\s*:\s*[\w\.]+", re.MULTILINE)
ENCODING_PASS = re.compile(r"public\s+void\s+EncodingPass\s*\([^)]*\)\s*\{", re.MULTILINE)
CASE = re.compile(r"case\s+\"(?P<name>[^\"]*)\"\s*:")
ASSIGN = re.compile(r"(?:VM\.\w+View\.)?(?P<field>\w+)\s*=(?!=)\s*(?P<value>[^;]+);")
STRING_LITERAL = re.compile(r'@?"((?:[^"\\]|\\.)*)"')


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def match_brace(text: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(text)):
        char = text[index]
        if char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
            if depth == 0:
                return index
    return len(text) - 1


def strip_comments(text: str) -> str:
    text = re.sub(r"/\*.*?\*/", "", text, flags=re.DOTALL)
    return re.sub(r"^[ \t]*//.*$", "", text, flags=re.MULTILINE)


def parse_value(raw: str):
    value = raw.strip()
    if value.startswith("new ") and "ObservableCollection<string>" in value:
        return parse_string_list(value)
    if value in ("true", "false"):
        return value == "true"
    if value in ("string.Empty", "String.Empty", "null"):
        return ""
    literal = re.fullmatch(r'@?"(.*)"', value, re.DOTALL)
    if literal:
        return literal.group(1).replace('\\"', '"').replace("\\\\", "\\")
    number = re.fullmatch(r"-?\d+(\.\d+)?", value)
    if number:
        return float(value) if "." in value else int(value)
    return value


def parse_string_list(block: str) -> list:
    body = block[block.find("{") : match_brace(block, block.find("{")) + 1]
    return [parse_value(literal) for literal in STRING_LITERAL.findall(body)]


def parse_object_list(block: str) -> list:
    items = []
    for match in re.finditer(r"new\s+[\w\.]+\(\)\s*\{", block):
        end = match_brace(block, match.end() - 1)
        body = block[match.end() : end]
        item = {}
        depth = 0
        current = ""
        for char in body:
            if char in "([{":
                depth += 1
            elif char in ")]}":
                depth -= 1
            if char == "," and depth <= 0:
                pair = current.split("=", 1)
                if len(pair) == 2:
                    item[pair[0].strip()] = parse_value(pair[1])
                current = ""
            else:
                current += char
        pair = current.split("=", 1)
        if len(pair) == 2:
            item[pair[0].strip()] = parse_value(pair[1])
        if item:
            items.append(item)
    return items


def parse_statements(segment: str) -> dict:
    result = {"assign": {}}
    guard = re.search(r"if\s*\(\s*Controls\.passUserSelected\s*==\s*false\s*\)\s*\{", segment)
    guarded = ""
    if guard:
        end = match_brace(segment, guard.end() - 1)
        guarded = segment[guard.end() : end]
        segment = segment[: guard.start()] + segment[end + 1 :]
    for statement in ASSIGN.finditer(segment):
        result["assign"][statement.group("field")] = parse_value(statement.group("value"))
    if guarded:
        result["userSelectedAssign"] = {
            statement.group("field"): parse_value(statement.group("value"))
            for statement in ASSIGN.finditer(guarded)
        }
    return result


def parse_encoding_pass(body: str) -> dict:
    table = {}
    branches = [(match.group("name"), match.end()) for match in CASE.finditer(body)]
    default_match = re.search(r"default\s*:", body)
    for index, (name, start) in enumerate(branches):
        if index + 1 < len(branches):
            end = branches[index + 1][1] - len(branches[index + 1][0]) - 8
        else:
            end = len(body)
        if default_match and default_match.start() > start:
            end = min(end, default_match.start())
        table[name] = parse_statements(body[start:end])
    if default_match:
        table["default"] = parse_statements(body[default_match.end() :])
    return table


def parse_codec(path: Path):
    text = strip_comments(read(path))
    class_match = CLASS.search(text)
    if class_match is None:
        return None
    data = {}
    for match in PROPERTY.finditer(text):
        end = match.end()
        depth = 0
        while end < len(text):
            char = text[end]
            if char in "{[(":
                depth += 1
            elif char in "}])":
                depth -= 1
            elif char == ";" and depth <= 0:
                break
            end += 1
        block = text[match.end() : end]
        if "ObservableCollection<string>" in block or "List<string>" in block:
            data[match.group("name")] = parse_string_list(block)
        else:
            data[match.group("name")] = parse_object_list(block)
    pass_match = ENCODING_PASS.search(text)
    if pass_match:
        body = text[pass_match.end() : match_brace(text, pass_match.end() - 1)]
        data["qualityPass"] = parse_encoding_pass(body)
    return class_match.group("name"), data


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(DEFAULT_SRC))
    parser.add_argument("--out", default=str(DEFAULT_OUT))
    args = parser.parse_args()

    src = Path(args.src)
    codecs = {kind: {} for kind in set(KINDS.values())}
    for relative, kind in KINDS.items():
        for path in sorted((src / relative).glob("*.cs")):
            parsed = parse_codec(path)
            if parsed is None:
                print("  ! skipped " + path.name)
                continue
            name, data = parsed
            codecs[kind][name] = data

    header = [
        '"""Generated by tools/codegen/gen_codecs.py - do not edit by hand.',
        "",
        "Codec tables extracted from the original ``Codecs/**`` sources: the combo box item",
        "lists (codec, encodeSpeed, pixelFormat, quality, optimize, tune/profile/level), the",
        "control overrides (controls_Selected/Expanded/Checked/Enabled) and the per-codec",
        "``qualityPass`` table translated from ``EncodingPass()``.",
        '"""',
        "",
        "from __future__ import annotations",
        "",
        "CODECS: dict = ",
    ]
    payload = pprint.pformat(codecs, width=110, sort_dicts=False)
    counts = ", ".join(kind + "=" + str(len(entries)) for kind, entries in codecs.items())
    text = "\n".join(header) + payload + "\n\n# " + counts + "\n"
    Path(args.out).write_text(text, encoding="utf-8")
    print("wrote " + str(sum(len(v) for v in codecs.values())) + " codecs (" + counts + ")")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
