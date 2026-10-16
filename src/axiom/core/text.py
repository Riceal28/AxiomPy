"""String helpers ported one-to-one from the original Axiom sources.

Each function keeps the exact semantics (including quirks) of its C# counterpart so
that generated command lines stay byte identical:

* ``MainWindow.RemoveLineBreaks`` / ``ReplaceLineBreaksWithSpaces``
* ``MainWindow.WrapWithQuotes``
* ``MainWindow.IsValidPath`` / ``IsValidFilename``
* ``MainWindow.NormalizeValue``
"""

from __future__ import annotations

import os
import re

# Line separators the original strips (and replaces) - see MainWindow.xaml.cs.
LINE_BREAKS = ("\r\n", "\n", "\u2028", "\u000a", "\u000b", "\u000c", "\u000d", "\u0085", "\u2029")

_INVALID_PATH_CHARS = re.compile("[" + re.escape("".join(sorted(set('\x00<>|"')))) + "]")
_INVALID_FILENAME_CHARS = re.compile("[" + re.escape("".join(sorted(set('<>:"/\\|?*\x00')))) + "]")


def remove_line_breaks(lines: str | None) -> str:
    """Port of MainWindow.RemoveLineBreaks: line breaks are *removed*, not spaced."""
    if lines is None:
        return ""
    for token in LINE_BREAKS:
        lines = lines.replace(token, "")
    return lines


def replace_line_breaks_with_spaces(lines: str | None) -> str:
    """Port of MainWindow.ReplaceLineBreaksWithSpaces."""
    if lines is None or lines.strip() == "":
        return lines or ""
    for token in LINE_BREAKS:
        lines = lines.replace(token, " ")
    return lines


def wrap_with_quotes(value: str, shell: str = "CMD", process_priority: str = "Default") -> str:
    """Port of MainWindow.WrapWithQuotes (CMD vs PowerShell, process-priority escaping)."""
    if shell == "CMD":
        return '"' + value + '"'
    if shell == "PowerShell":
        if process_priority == "Default":
            return '"' + value + '"'
        return '`"' + value + '`"'
    return value


def is_valid_path(path: str | None) -> bool:
    """Port of MainWindow.IsValidPath."""
    if path is None or path.strip() == "":
        return False
    return _INVALID_PATH_CHARS.search(path) is None


def is_valid_filename(filename: str | None) -> bool:
    """Port of MainWindow.IsValidFilename."""
    if filename is None:
        return False
    return _INVALID_FILENAME_CHARS.search(filename) is None


def normalize_value(
    value: float,
    value_min: float,
    value_max: float,
    minimum: float,
    maximum: float,
    midpoint: float,
) -> float:
    """Port of MainWindow.NormalizeValue (piecewise linear map through a midpoint)."""
    mid = (value_min + value_max) / 2.0
    if value < mid:
        return (value - value_min) / (mid - value_min) * (midpoint - minimum) + minimum
    return (value - mid) / (value_max - mid) * (maximum - midpoint) + midpoint


def trim_end_separators(path: str, separator: str = os.sep) -> str:
    """Port of the ``TrimEnd('\\\\') + @\"\\\\\"`` idiom used all over Axiom."""
    return path.rstrip(separator) + separator

