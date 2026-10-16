"""Headless entry point.

The CLI consumes the very same case files the C# parity harness consumes, which keeps
the two implementations directly comparable:

    python -m axiom.cli --case cases.json --id webm-vp8-crf-25 --print resolved
    python -m axiom.cli --case cases.json --id webm-vp8-crf-25 --print command
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Iterable, Mapping

from .state import AxiomState


def load_cases(path: Path | str) -> list[dict[str, Any]]:
    payload = json.loads(Path(path).read_text(encoding="utf-8"))
    if isinstance(payload, dict):
        return [payload]
    return list(payload)


def select_cases(cases: Iterable[Mapping[str, Any]], case_id: str | None) -> list[Mapping[str, Any]]:
    if case_id is None:
        return list(cases)
    selected = [case for case in cases if case.get("id") == case_id]
    if not selected:
        raise SystemExit(f"no case with id {case_id!r}")
    return selected


def describe(case: Mapping[str, Any]) -> dict[str, Any]:
    state = AxiomState.from_case(case)
    return {
        "id": case.get("id"),
        "state": state.to_overrides(),
        "ffprobe": state.ffprobe,
        "controls": state.controls,
    }


def generate_command(case: Mapping[str, Any]) -> str:
    from .generate import generate  # imported lazily: the port lands module by module

    return generate(AxiomState.from_case(case))


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="axiom.cli")
    parser.add_argument("--case", required=True, help="case file (JSON array or object)")
    parser.add_argument("--id", dest="case_id", default=None, help="case id to run")
    parser.add_argument(
        "--print",
        dest="what",
        choices=("command", "resolved"),
        default="command",
    )
    args = parser.parse_args(argv)

    cases = select_cases(load_cases(args.case), args.case_id)
    exit_code = 0
    for case in cases:
        if args.what == "resolved":
            print(json.dumps(describe(case), indent=2, sort_keys=True))
            continue
        try:
            print(generate_command(case))
        except NotImplementedError as error:
            print(f"generator not ported yet: {error}", file=sys.stderr)
            exit_code = 3
    return exit_code


if __name__ == "__main__":
    raise SystemExit(main())

