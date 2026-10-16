"""Control-layer parity against the oracle's resolved-state dump.

``tools/parity_harness`` writes both the golden command line *and* the resolved control
state for every case, so the control layer can be verified field by field while it is
being ported - each key below belongs to a module that has already landed.

Currently covered: the codec layer (``Controls.<Kind>.CodecControls``: codec string, item
sources, pass state machine, enabled/selected overrides).

Still owned by modules that have not been ported yet (their keys are excluded on
purpose): ``FormatControls``/``MediaTypeControls`` (container driven item lists and
enable flags), ``QualityControls``/``VideoBitRateDisplay`` (CRF/bitrate text),
``OptimizeControls`` (``Video_Optimize_Level_Items`` and the tune/profile/level
selections), ``PixelFormatControls``, ``CutControls``, ``AudioStreamControls``.
"""

import json
from pathlib import Path

import pytest

from axiom.core import controls, dump
from axiom.core.state import AxiomState

GOLDEN_DIR = Path(__file__).parent / "golden"
CASE_FILE = Path(__file__).parent.parent / "tools" / "parity_harness" / "smoke_cases.json"

CODEC_LAYER_KEYS = [
    "Video.Video_Codec",
    "Video.Video_Codec_IsEnabled",
    "Video.Video_EncodeSpeed_IsEnabled",
    "Video.Video_EncodeSpeed_Items",
    "Video.Video_EncodeSpeed_SelectedItem",
    "Video.Video_PixelFormat_Items",
    "Video.Video_Quality_Items",
    "Video.Video_Pass_Items",
    "Video.Video_Pass_SelectedItem",
    "Video.Video_Pass_IsEnabled",
    "Video.Video_CRF_IsEnabled",
    "Video.Video_BitRate_Text",
    "Video.Video_MinRate_Text",
    "Video.Video_MaxRate_Text",
    "Video.Video_BufSize_Text",
    "Video.Video_Optimize_Items",
    "Video.Video_Optimize_Tune_Items",
    "Video.Video_Optimize_Profile_Items",
    "Video.Video_Optimize_Level_Items",
    "Video.Video_Optimize_Tune_SelectedItem",
    "Video.Video_Optimize_Tune_IsEnabled",
    "Video.Video_Optimize_Profile_IsEnabled",
    "Video.Video_Optimize_Level_IsEnabled",
    "Video.Video_Optimize_IsExpanded",
    "Video.Video_VBR_IsChecked",
    "Video.Video_VBR_IsEnabled",
    "Video.Video_Pass_IsEnabled",
    "Video.Video_CRF_IsEnabled",
    "Video.Video_BitRate_IsEnabled",
    "Video.Video_MinRate_IsEnabled",
    "Video.Video_MaxRate_IsEnabled",
    "Video.Video_BufSize_IsEnabled",
    "Video.Video_Scale_IsEnabled",
    "Audio.Audio_Codec",
]

# Owned by FormatControls/MediaTypeControls (container driven), ported next:
#   Video_Optimize_SelectedItem, Video_Optimize_Profile_SelectedItem,
#   Video_Optimize_Level_SelectedItem, Video_Codec_Items, Video_*_Items


def cases():
    if not CASE_FILE.exists():
        return []
    return json.loads(CASE_FILE.read_text(encoding="utf-8"))


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
        for key in CODEC_LAYER_KEYS
        if actual.get(key) != expected.get(key)
    }
    assert not mismatches, f"control layer differs from the oracle: {mismatches}"

