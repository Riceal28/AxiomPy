"""The assembly step must reproduce the original join-then-strip semantics."""

from axiom.core.assembly import concat_sections, join_fragments


def test_fragments_are_joined_with_single_spaces():
    assert join_fragments(["\r\n\r\n-y", "\r\n\r\n-i \"in.mkv\"", "\r\n\r\n-out.mp4"]) == (
        '-y -i "in.mkv" -out.mp4'
    )


def test_empty_and_whitespace_fragments_are_dropped():
    assert join_fragments(["", None, "   ", "\r\n", "\r\n\r\n", "-y"]) == "-y"


def test_sections_are_concatenated_in_order():
    options = ["\r\n\r\n-y"]
    inputs = ["\r\n\r\n-i \"in.mkv\""]
    outputs = ["\r\n\r\n\"out.mp4\""]
    assert concat_sections(options, inputs, outputs) == '-y -i "in.mkv" "out.mp4"'

