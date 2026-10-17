"""Control-layer parity against the oracle's resolved-state dump.

``tools/parity_harness`` writes both the golden command line and the resolved
ViewModel state for every case.  The control layer is verified field by field over the
whole state dump, using the container/media-type/codec/cut/quality matrix in
``control_cases.json``.

Three ``Configure`` values are runtime paths/list construction owned by the settings
layer (they depend on ``%LOCALAPPDATA%`` and ``MainWindow.outputNaming_Defaults``), not
by the control event chain, so they are excluded here and covered by the settings
tests instead.
"""

import json
from pathlib import Path

import pytest

from axiom.core import controls, dump
from axiom.core.state import AxiomState

GOLDEN_DIR = Path(__file__).parent / "golden"
CASE_FILES = [
    Path(__file__).parent.parent / "tools" / "parity_harness" / "smoke_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "control_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "filter_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "batch_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "preset_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "output_cases.json",
    Path(__file__).parent.parent / "tools" / "parity_harness" / "external_cases.json",
]

SETTINGS_RUNTIME_KEYS = {
    "Configure.CustomPresetsPath_Text",
    "Configure.LogPath_Text",
    "Configure.OutputNaming_ListView_Items",
}


def cases():
    result: list[dict] = []
    for path in CASE_FILES:
        if path.exists():
            result.extend(json.loads(path.read_text(encoding="utf-8")))
    return result


@pytest.mark.parametrize("case", cases(), ids=lambda case: case.get("id", "?"))
def test_codec_layer_state_matches_oracle(case):
    golden_file = GOLDEN_DIR / f"{case['id']}.json"
    if not golden_file.exists():
        pytest.skip("no golden captured: run tools/parity_harness/run_goldens.py")
    expected = json.loads(golden_file.read_text(encoding="utf-8")).get("state") or {}
    if not expected:
        pytest.skip("golden has no state dump: rebuild the harness")

    state = AxiomState.from_case(case)
    controls.resolve(state)
    actual = dump.dump_state(state)

    mismatches = {
        key: (expected.get(key), actual.get(key))
        for key in expected
        if key not in SETTINGS_RUNTIME_KEYS and actual.get(key) != expected.get(key)
    }
    assert not mismatches, f"control layer differs from the oracle: {mismatches}"

