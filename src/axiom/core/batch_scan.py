"""Directory queue inspection for the batch workflow."""

from __future__ import annotations

from pathlib import Path


def normalize_batch_extension(value: str | None) -> str:
    text = str(value or "").strip()
    if not text or text.lower() == "extension" or text == ".":
        return ""
    if not text.startswith("."):
        text = "." + text
    return text.lower()


def scan_batch_files(directory: Path | str, extension: str | None) -> list[Path]:
    """Return regular files in ``directory`` matching the batch extension.

    An empty/placeholder extension means "all files", matching the original
    wildcard batch behaviour.  A file path is treated as its containing
    directory so enabling Batch after picking a file still builds a queue.
    """
    folder = Path(directory)
    if folder.is_file():
        folder = folder.parent
    if not folder.is_dir():
        return []
    wanted = normalize_batch_extension(extension)
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and (not wanted or path.suffix.lower() == wanted)
    ]
    return sorted(files, key=lambda path: path.name.casefold())
