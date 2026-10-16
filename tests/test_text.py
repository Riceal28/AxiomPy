"""Behaviour of the string helpers must match the original C# exactly."""

from axiom.core.text import (
    is_valid_filename,
    is_valid_path,
    normalize_value,
    remove_line_breaks,
    replace_line_breaks_with_spaces,
    wrap_with_quotes,
)


def test_remove_line_breaks_deletes_rather_than_spaces():
    assert remove_line_breaks("\r\n\r\n-y") == "-y"
    assert remove_line_breaks("a\r\nb") == "ab"
    assert remove_line_breaks("-i \r\n\r\ninput") == "-i input"


def test_remove_line_breaks_handles_unicode_separators():
    assert remove_line_breaks("a\u2028b\u0085c") == "abc"


def test_replace_line_breaks_with_spaces_keeps_separators():
    assert replace_line_breaks_with_spaces("a\r\nb") == "a b"
    assert replace_line_breaks_with_spaces("") == ""


def test_wrap_with_quotes_cmd_and_powershell():
    assert wrap_with_quotes("C:\\path with space\\in.mkv") == '"C:\\path with space\\in.mkv"'
    assert wrap_with_quotes("x", shell="PowerShell") == '"x"'
    assert wrap_with_quotes("x", shell="PowerShell", process_priority="High") == '`"x`"'


def test_path_and_filename_validation():
    assert is_valid_path("C:\\Videos\\in.mkv")
    assert not is_valid_path("")
    assert not is_valid_path(None)
    assert is_valid_filename("my video.mkv")
    assert not is_valid_filename("bad:name.mkv")


def test_normalize_value_is_piecewise_linear_through_midpoint():
    # The original takes the upper branch at the midpoint (val < mid is strict),
    # so val == mid maps to the configured midpoint value.
    assert normalize_value(0, 0, 10, 0, 100, 50) == 0
    assert normalize_value(5, 0, 10, 0, 100, 50) == 50
    assert normalize_value(10, 0, 10, 0, 100, 50) == 100
    assert normalize_value(2.5, 0, 10, 0, 100, 50) == 25

