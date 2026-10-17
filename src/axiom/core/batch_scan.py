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
    wildcard batch behaviour.
    """
    folder = Path(directory)
    if not folder.is_dir():
        return []
    wanted = normalize_batch_extension(extension)
    files = [
        path
        for path in folder.iterdir()
        if path.is_file() and (not wanted or path.suffix.lower() == wanted)
    ]
    return sorted(files, key=lambda path: path.name.casefold())
