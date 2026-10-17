"""AxiomPy desktop entry point."""

from __future__ import annotations

import os
import sys
from pathlib import Path

from PySide6.QtWidgets import QApplication

from axiom.core.config import migrate_legacy_config

from .main_window import MainWindow


def _prepare_runtime() -> None:
    """Make bundled ffmpeg tools and portable config visible to the frozen app."""
    if not getattr(sys, "frozen", False):
        return
    roots = {
        Path(sys.executable).resolve().parent,
        Path(getattr(sys, "_MEIPASS", Path(sys.executable).parent)),
    }
    path_parts = [str(path) for path in roots]
    path_parts.append(os.environ.get("PATH", ""))
    os.environ["PATH"] = os.pathsep.join(path_parts)
    os.environ.setdefault("AXIOM_PORTABLE_ROOT", str(Path(sys.executable).parent))


def _stylesheet() -> str:
    root = Path(getattr(sys, "_MEIPASS", Path(__file__).parent.parent))
    path = root / "axiom" / "ui" / "theme" / "axiom_dark.qss"
    if not path.exists():
        path = Path(__file__).with_name("theme") / "axiom_dark.qss"
    return path.read_text(encoding="utf-8") if path.exists() else ""


def main() -> int:
    _prepare_runtime()
    migrate_legacy_config()
    app = QApplication(sys.argv)
    app.setApplicationName("AxiomPy")
    app.setStyleSheet(_stylesheet())
    window = MainWindow()
    window._load_settings()
    window.show()
    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
