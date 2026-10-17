"""Output path normalization for single and batch notifications."""

from axiom.core.generate.context import batch_output_path, build_context
from axiom.core.state import AxiomState


def test_single_output_directory_with_trailing_separator_is_normalized():
    state = AxiomState(
        {
            "Main.Input_Text": r"I:\in\KumaSteam\kikyou0.mkv",
            "Main.Output_Text": "I:/out/KumaSteam\\",
            "Format.Format_Container_SelectedItem": "mp4",
        }
    )

    context = build_context(state)

    assert context.output_dir == "I:\\out\\KumaSteam\\"
    assert context.output_path == "I:\\out\\KumaSteam\\kikyou0.mp4"


def test_batch_output_path_is_resolved_for_each_input_file():
    state = AxiomState(
        {
            "Main.Batch_IsChecked": True,
            "Main.BatchExtension_Text": "mkv",
            "Main.Input_Text": "I:/in/KumaSteam\\",
            "Main.Output_Text": "I:/out/KumaSteam\\",
            "Format.Format_Container_SelectedItem": "mp4",
        }
    )

    assert batch_output_path(
        state,
        r"I:\in\KumaSteam\kikyou1.mkv",
    ) == r"I:\out\KumaSteam\kikyou1.mp4"
    assert "%~n" not in batch_output_path(
        state,
        r"I:\in\KumaSteam\kikyou1.mkv",
    )
