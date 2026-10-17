"""External audio/subtitle metadata formatting."""

import json
from pathlib import Path

from axiom.core.generate import generate, generate_runnable
from axiom.core.generate.audio import audio_metadata
from axiom.core.generate.subtitles import subtitle_metadata
from axiom.core.state import AxiomState


def test_audio_metadata_title_and_language():
    state = AxiomState(
        {
            "Audio.Audio_Stream_SelectedItem": "mux",
            "_audio_metadata": [
                {"title": "Commentary", "language": "English", "delay": "+250"}
            ],
        }
    )
    assert audio_metadata(state) == (
        '-metadata:s:a:0 title="Commentary" '
        '-metadata:s:a:0 language="en"'
    )


def test_subtitle_metadata_skips_empty_and_none():
    state = AxiomState(
        {
            "Subtitle.Subtitle_Stream_SelectedItem": "mux",
            "_subtitle_metadata": [
                {"title": "", "language": "none"},
                {"title": "Signs", "language": "Japanese"},
            ],
        }
    )
    assert subtitle_metadata(state) == (
        '-metadata:s:s:1 title="Signs" '
        '-metadata:s:s:1 language="jp"'
    )


def test_metadata_is_only_emitted_for_mux():
    state = AxiomState(
        {
            "Audio.Audio_Stream_SelectedItem": "all",
            "_audio_metadata": [{"title": "Ignored"}],
        }
    )
    assert audio_metadata(state) == ""


def test_runnable_generation_separates_external_stream_maps():
    case_path = (
        Path(__file__).parent.parent
        / "tools"
        / "parity_harness"
        / "external_cases.json"
    )
    cases = json.loads(case_path.read_text(encoding="utf-8"))
    case = next(item for item in cases if item["id"] == "ext-audio-mux")
    parity = generate(AxiomState.from_case(case))
    runnable = generate_runnable(AxiomState.from_case(case))

    assert "-map 1:a?-map 2:a?" in parity
    assert "-map 1:a? -map 2:a?" in runnable
    assert "0-map_metadata" not in runnable
