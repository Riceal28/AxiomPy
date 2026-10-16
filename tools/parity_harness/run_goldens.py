"""Run the C# oracle over a case file and store the golden command lines.

    python tools/parity_harness/run_goldens.py [--cases FILE ...] [--out-dir DIR]

The results are written as one JSON file per case under ``tests/golden/`` and are
consumed by ``tests/test_parity.py``.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
REPO = HERE.parent.parent
EXE = HERE / "bin" / "Debug" / "net471" / "AxiomParity.exe"
DEFAULT_OUT = REPO / "tests" / "golden"


def run_case_file(exe: Path, cases: Path, out: Path) -> list[dict]:
    subprocess.run([str(exe), "--cases", str(cases), "--out", str(out)], check=True)
    return json.loads(out.read_text(encoding="utf-8"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--cases", nargs="*", default=[str(HERE / "smoke_cases.json")])
    parser.add_argument("--out-dir", default=str(DEFAULT_OUT))
    parser.add_argument("--exe", default=str(EXE))
    args = parser.parse_args()

    exe = Path(args.exe)
    if not exe.exists():
        print(f"harness not built: {exe}\nrun: python tools/parity_harness/build_harness.py", file=sys.stderr)
        return 2

    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    total = 0
    for case_file in args.cases:
        result = run_case_file(exe, Path(case_file), out_dir / "_raw.json")
        for entry in result:
            target = out_dir / f"{entry['id']}.json"
            target.write_text(json.dumps(entry, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            total += 1
    (out_dir / "_raw.json").unlink(missing_ok=True)
    print(f"wrote {total} golden files to {out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

