"""Golden comparison against the C# oracle.

``tests/golden/*.json`` is produced by ``tools/parity_harness/run_goldens.py`` from the
*original* Axiom generator sources.  Until the Python generator is ported these tests
skip; as modules land they turn green without any change to the fixtures.
"""

import json
import re
from pathlib import Path

import pytest

from axiom.core.cli import generate_command, load_cases
from axiom.core.generate import PENDING_MODULES

GOLDEN_DIR = Path(__file__).parent / "golden"
CUSTOM_RATE_GOLDENS = json.loads(
    (Path(__file__).parent / "custom_rate_goldens.json").read_text(
        encoding="utf-8"
    )
)
CASE_FILES = [
    Path(__file__).parent.parent / "tools" / "parity_harness" / "smoke_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "control_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "filter_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "batch_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "preset_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "output_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "external_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "hardware_cases.json",
]


def golden_cases():
    cases: list[dict] = []
    for case_file in CASE_FILES:
        if case_file.exists():
            cases.extend(load_cases(case_file))
    return cases


@pytest.mark.parametrize("case", golden_cases(), ids=lambda case: case.get("id", "?"))
def test_python_matches_csharp_oracle(case):
    golden_file = GOLDEN_DIR / f"{case['id']}.json"
    if not golden_file.exists():
        pytest.skip(f"no golden captured yet: run tools/parity_harness/run_goldens.py")
    expected = json.loads(golden_file.read_text(encoding="utf-8"))
    if "error" in expected:
        pytest.fail(f"oracle failed for {case['id']}: {expected['error']}")
    try:
        actual = generate_command(case)
    except NotImplementedError:
        pytest.skip("generator still being ported: " + ", ".join(PENDING_MODULES))
    expected_args = expected["args"]
    if case.get("expectedOverride") == "custom-rate-control":
        expected_args = CUSTOM_RATE_GOLDENS[case["id"]]
    if case.get("expectedOverride") == "amf-qvbr":
        # Deliberate correction: generic -crf is not an AMF encoder option.
        # The C# oracle still emits it, so transform the captured expectation.
        expected_args = re.sub(
            r"-crf\s+(\d+)",
            r"-rc qvbr -qvbr_quality_level \1",
            expected_args,
            count=1,
        )
    assert actual == expected_args

