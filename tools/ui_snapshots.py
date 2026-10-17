"""Capture deterministic screenshots of every main Qt page."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path


PROJECT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT / "src"))


def _capture(window, output: Path, name: str) -> None:
    window.grab().save(str(output / f"{name}.png"))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--output",
        type=Path,
        default=PROJECT / "artifacts" / "ui-current",
    )
    parser.add_argument(
        "--platform",
        choices=("native", "offscreen"),
        default="native",
    )
    parser.add_argument("--width", type=int, default=1280)
    parser.add_argument("--height", type=int, default=720)
    args = parser.parse_args()

    if args.platform == "offscreen":
        os.environ["QT_QPA_PLATFORM"] = "offscreen"

    from PySide6.QtWidgets import QApplication

    from axiom.ui.app import _stylesheet
    from axiom.ui.main_window import MainWindow

    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication.instance() or QApplication([])
    app.setStyleSheet(_stylesheet())
    window = MainWindow()
    window.resize(args.width, args.height)
    window.show()
    app.processEvents()

    pages = [
        (0, None, "format"),
        (1, 0, "video-encoding"),
        (1, 1, "video-size"),
        (1, 2, "video-color"),
        (2, 0, "audio-encoding"),
        (2, 1, "audio-external"),
        (3, None, "subtitles"),
        (4, 0, "filters-video"),
        (4, 1, "filters-audio"),
        (5, 0, "notify-http"),
        (5, 1, "notify-message"),
        (6, 0, "settings-config"),
        (6, 1, "settings-file"),
        (6, 2, "settings-system"),
    ]
    for top_index, sub_index, name in pages:
        window.tabs.setCurrentIndex(top_index)
        if sub_index is not None:
            active = {
                1: window.video_tabs,
                2: window.audio_tabs,
                4: window.filter_tabs,
                5: window.notify_tabs,
                6: window.settings_tabs,
            }[top_index]
            active.setCurrentIndex(sub_index)
        app.processEvents()
        _capture(window, args.output, name)

    from PySide6.QtWidgets import QTableWidgetItem

    window.tabs.setCurrentIndex(0)
    window.batch_check.setChecked(True)
    window.batch_list.setRowCount(2)
    for row, (name, status) in enumerate(
        (("example-one.mp4", "Completed"), ("example-two.mp4", "Running"))
    ):
        window.batch_list.setItem(row, 0, QTableWidgetItem(name))
        window.batch_list.setItem(row, 1, QTableWidgetItem(status))
    window.batch_status.setText("Completed 1 · Running 1")
    window.progress_bar.setFormat("File %p%")
    window.progress_bar.setValue(450)
    window.total_progress_bar.show()
    window.total_progress_bar.setValue(300)
    app.processEvents()
    _capture(window, args.output, "batch-queue")

    window.close()
    app.processEvents()
    print(f"Captured {len(pages) + 1} screenshots in {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
