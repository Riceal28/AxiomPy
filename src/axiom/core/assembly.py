"""Argument list assembly, mirroring ``Generate.FFmpeg._1_Pass`` and friends.

The original builds ``List<string>`` fragments (many prefixed with ``"\\r\\n\\r\\n"``),
joins them with a single space, then *removes* every line break.  Replicating that
sequence - rather than joining cleanly - is what keeps the output byte identical, so the
quirk is preserved deliberately.
"""

from __future__ import annotations

from typing import Iterable, Sequence

from .text import remove_line_breaks

# Fragments that the original filters out before joining.
# Note: every one of them is whitespace-only, so `str.strip()` covers the intent while
# keeping the list documented.
DROPPED_FRAGMENTS = {
    "\r\n\r\n",
    "\r\n",
    "\n",
    "\u2028",
    "\u000a",
    "\u000b",
    "\u000c",
    "\u000d",
    "\u0085",
    "\u2029",
}


def join_fragments(parts: Iterable[str | None]) -> str:
    """``string.Join(" ", parts.Where(not empty))`` followed by ``RemoveLineBreaks``."""
    kept = [
        part
        for part in parts
        if part is not None and part.strip() != "" and part not in DROPPED_FRAGMENTS
    ]
    return remove_line_breaks(" ".join(kept))


def concat_sections(*sections: Sequence[str | None]) -> str:
    """Join the per-section fragment lists of a pass assembly."""
    flattened: list[str | None] = []
    for section in sections:
        flattened.extend(section)
    return join_fragments(flattened)

