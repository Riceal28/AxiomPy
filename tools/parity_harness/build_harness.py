"""Build the C# parity harness out of the original (read-only) Axiom sources.

The harness is a headless console app that reuses the *original* generator sources and
dumps the exact ffmpeg command line Axiom would produce for a given state.  Goldens
produced this way are byte-compared against the Python port.

The original repository is never modified: every file is copied into ``gen_src/`` first,
with two mechanical transforms applied:

* ``MessageBox.Show(`` -> ``Harness.Dialog.Show(`` (non-blocking, deterministic)
* members that live in WPF-bound classes are extracted verbatim into ``MainWindow.Shim.cs``

Usage:
    python tools/parity_harness/build_harness.py [--src PATH] [--no-build]
"""

from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
DEFAULT_SRC = Path(r"G:\Codex_workspace\Axiom\source\Axiom\Axiom")
GEN = HERE / "gen_src"
MEMBERS_JSON = HERE / "members.json"

COPY_DIRS = ["ViewModel", "Types", "Codecs", "Filters", "Generators"]
COPY_FILES = ["Log.cs", "Controls/FormatContainers.cs"]
EXCLUDE = {"Generators/Arguments/YouTubeDL.cs"}

DECL_TEMPLATE = (
    r"^[ \t]*(?:\[[^\]]*\][ \t]*)?"
    r"(?P<mods>(?:public|private|protected|internal|static|readonly|const|new|override|partial|async|virtual|sealed)\s+)+"
    r"(?P<type>[A-Za-z_][\w\.<>,\[\]\?\s]*?)\s+"
    r"(?P<name>{name})\s*"
    r"(?P<tail>\(|=|\{{|;)"
)


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8-sig", errors="replace")


def transform(code: str) -> str:
    return code.replace("MessageBox.Show(", "Harness.Dialog.Show(")


def extract_member(text: str, name: str) -> str | None:
    """Return the full declaration text of ``name`` (method, field or property)."""
    interface = re.compile(
        r"^[ \t]*public interface " + re.escape(name) + r"\b", re.MULTILINE
    )
    for match in interface.finditer(text):
        body_start = text.find("{", match.end())
        if body_start == -1:
            continue
        depth = 0
        for index in range(body_start, len(text)):
            char = text[index]
            if char == "{":
                depth += 1
            elif char == "}":
                depth -= 1
                if depth == 0:
                    return text[match.start() : index + 1]
        continue
    pattern = re.compile(DECL_TEMPLATE.format(name=re.escape(name)), re.MULTILINE)
    for match in pattern.finditer(text):
        line_start = text.rfind("\n", 0, match.start()) + 1
        if "//" in text[line_start : match.start()]:
            continue
        if match.group("tail") == "(":
            body_start = text.find("{", match.end() - 1)
            if body_start == -1:
                continue
            depth = 0
            for index in range(body_start, len(text)):
                char = text[index]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return text[match.start() : index + 1]
            continue
        if match.group("tail") == "{":
            # auto property: public static string X { get; set; }
            depth = 0
            for index in range(match.end() - 1, len(text)):
                char = text[index]
                if char == "{":
                    depth += 1
                elif char == "}":
                    depth -= 1
                    if depth == 0:
                        return text[match.start() : index + 1]
            continue
        depth = 0
        for index in range(match.start(), len(text)):
            char = text[index]
            if char in "{(":
                depth += 1
            elif char in "})":
                depth -= 1
            elif char == ";" and depth <= 0:
                return text[match.start() : index + 1]
    return None


def brace_delta(body: str) -> int:
    """Net brace balance, ignoring braces inside string/char literals and comments."""
    depth = 0
    index = 0
    while index < len(body):
        char = body[index]
        if char == "/" and index + 1 < len(body) and body[index + 1] == "/":
            index = body.find("\n", index)
            if index == -1:
                break
        elif char == "/" and index + 1 < len(body) and body[index + 1] == "*":
            end = body.find("*/", index + 2)
            index = len(body) if end == -1 else end + 1
        elif char == "@" and index + 1 < len(body) and body[index + 1] == '"':
            end = body.find('"', index + 2)
            while end != -1 and end + 1 < len(body) and body[end + 1] == '"':
                end = body.find('"', end + 2)
            index = len(body) if end == -1 else end
        elif char == '"':
            index += 1
            while index < len(body):
                if body[index] == "\\":
                    index += 2
                    continue
                if body[index] == '"':
                    break
                index += 1
        elif char == "'":
            index += 1
            while index < len(body) and body[index] != "'":
                index += 2 if body[index] == "\\" else 1
        elif char == "{":
            depth += 1
        elif char == "}":
            depth -= 1
        index += 1
    return depth


def copy_sources(src: Path) -> int:
    # Overwrite in place: on Windows the workspace sandbox may deny deleting
    # generated files, while writing them is allowed.  Stale files are harmless for
    # the current fixed source set and keep the build idempotent without a delete.
    GEN.mkdir(parents=True, exist_ok=True)
    count = 0
    for directory in COPY_DIRS:
        for path in sorted((src / directory).rglob("*.cs")):
            rel = path.relative_to(src).as_posix()
            if rel in EXCLUDE:
                continue
            target = GEN / rel
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(transform(read(path)), encoding="utf-8")
            count += 1
    for rel in COPY_FILES:
        target = GEN / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(transform(read(src / rel)), encoding="utf-8")
        count += 1
    return count


def target_files(src: Path, target: dict) -> dict[str, str]:
    texts: dict[str, str] = {}
    for rel in target["files"]:
        path = src / rel
        if path.exists():
            texts[rel] = read(path)
    return texts


def build_shim(src: Path, targets: list[dict]) -> tuple[str, list[str]]:
    lines = [
        "// <auto-generated> verbatim extraction from the original Axiom sources </auto-generated>",
        "using System;",
        "using System.Collections;",
        "using System.Collections.Generic;",
        "using System.Collections.ObjectModel;",
        "using System.ComponentModel;",
        "using System.Data;",
        "using System.Diagnostics;",
        "using System.Globalization;",
        "using System.IO;",
        "using System.Linq;",
        "using System.Text.RegularExpressions;",
        "using System.Text;",
        "using System.Threading.Tasks;",
        "using System.Windows;",
        "using System.Windows.Documents;",
        "using System.Windows.Forms;",
        "using System.Windows.Input;",
        "using System.Windows.Media;",
        "using Axiom;",
        "using ViewModel;",
        "using MessageBox = System.Windows.MessageBox;",
        "",
    ]
    missing: list[str] = []
    for target in targets:
        texts = target_files(src, target)
        bodies: list[tuple[str, str]] = []
        for name in target["members"]:
            for text in texts.values():
                body = extract_member(text, name)
                if body is not None:
                    bodies.append((name, body))
                    break
            else:
                if not target.get("optional"):
                    missing.append(f"{target['class']}.{name}")
        if not bodies:
            continue
        lines.append(f"namespace {target['namespace']}")
        lines.append("{")
        wrapper = target.get("wrapper", target["class"])
        kind = target.get("kind", "static class")
        if wrapper:
            partial = "partial " if kind == "class" else ""
            base = target.get("base")
            suffix = f" : {base}" if base else ""
            lines.append(f"    public {partial}{kind} {wrapper}{suffix}")
            lines.append("    {")
        for name, body in bodies:
            balance = brace_delta(body)
            if balance != 0:
                print(f"  ! unbalanced extraction: {target['class']}.{name} ({balance})")
            indent = "        " if wrapper else "    "
            lines.append(f"{indent}// >>> member: {name}")
            lines.extend(indent + line for line in body.splitlines())
            lines.append("")
        if wrapper:
            lines.append("    }")
        lines.append("}")
        lines.append("")
    return "\n".join(lines), missing


def run_build() -> tuple[bool, str]:
    import os

    environment = dict(os.environ)
    environment["DOTNET_CLI_UI_LANGUAGE"] = "en"
    environment["VSLANG"] = "1033"
    result = subprocess.run(
        [
            "dotnet",
            "build",
            "-v",
            "quiet",
            "--nologo",
            "/p:UICulture=en",
            "/p:PreferredUILang=en",
            str(HERE / "AxiomParity.csproj"),
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        cwd=str(HERE),
        env=environment,
    )
    return result.returncode == 0, (result.stdout or "") + (result.stderr or "")


ERROR_POSITION = re.compile(
    r"^(?P<file>.+?)\((?P<line>\d+),(?P<col>\d+)\): error CS(?P<code>0117|0103)\b"
)


def identifier_at(path: str, line: int, col: int) -> str | None:
    """Locale independent name recovery: read the identifier the compiler pointed at."""
    try:
        text = Path(path).read_text(encoding="utf-8-sig", errors="replace")
    except OSError:
        return None
    lines = text.splitlines()
    if line - 1 >= len(lines):
        return None
    snippet = lines[line - 1]
    index = min(max(col - 1, 0), max(len(snippet) - 1, 0))

    def is_word(char: str) -> bool:
        return char.isalnum() or char == "_"

    if not is_word(snippet[index]):
        # the column may sit on '.' or on the type; slide to the nearest identifier
        for offset in range(1, 40):
            for probe in (index + offset, index - offset):
                if 0 <= probe < len(snippet) and is_word(snippet[probe]):
                    index = probe
                    break
            else:
                continue
            break
    if not is_word(snippet[index]):
        return None
    start = index
    while start > 0 and is_word(snippet[start - 1]):
        start -= 1
    end = index
    while end + 1 < len(snippet) and is_word(snippet[end + 1]):
        end += 1
    return snippet[start : end + 1]


def discover_missing(output: str) -> set[str]:
    """Names the compiler could not resolve (any UI locale)."""
    names: set[str] = set()
    for raw in output.splitlines():
        match = ERROR_POSITION.search(raw.strip())
        if not match:
            continue
        name = identifier_at(match.group("file"), int(match.group("line")), int(match.group("col")))
        if name:
            names.add(name)
    return names


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--src", default=str(DEFAULT_SRC))
    parser.add_argument("--no-build", action="store_true")
    parser.add_argument("--max-rounds", type=int, default=10)
    args = parser.parse_args()

    src = Path(args.src)
    if not src.exists():
        print(f"source not found: {src}", file=sys.stderr)
        return 2

    config = json.loads(MEMBERS_JSON.read_text(encoding="utf-8"))
    targets = config["targets"]

    print(f"copied {copy_sources(src)} source files -> {GEN}")

    if args.no_build:
        shim, missing = build_shim(src, targets)
        (HERE / "MainWindow.Shim.cs").write_text(shim, encoding="utf-8")
        print(f"missing: {missing}")
        return 0

    for round_index in range(1, args.max_rounds + 1):
        shim, missing = build_shim(src, targets)
        (HERE / "MainWindow.Shim.cs").write_text(shim, encoding="utf-8")
        if missing:
            print(f"round {round_index}: unresolved members {missing}")
        ok, output = run_build()
        if ok:
            print(f"harness build OK (round {round_index})")
            MEMBERS_JSON.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
            return 0

        discovered = discover_missing(output)

        if not discovered:
            print(output[-6000:])
            return 1

        added = False
        unplaced: set[str] = set()
        for name in sorted(discovered):
            placed = False
            for target in targets:
                if name in target["members"]:
                    placed = True
                    continue
                texts = target_files(src, target)
                if any(extract_member(text, name) for text in texts.values()):
                    print(f"  + {target['namespace']}.{target['class']}.{name}")
                    target["members"].append(name)
                    placed = True
                    added = True
            if not placed:
                unplaced.add(name)
        MEMBERS_JSON.write_text(json.dumps(config, indent=2) + "\n", encoding="utf-8")
        if unplaced or not added:
            print(f"could not place: {sorted(unplaced)}")
            print(output[-3000:])
            return 1
    print("max rounds reached", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
