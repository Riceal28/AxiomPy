"""Settings path rows: automatic path display and manual Browse."""

from pathlib import Path

from axiom.ui.main_window import MainWindow


def test_auto_tool_path_displays_resolved_executable(qtbot, monkeypatch):
    monkeypatch.delenv("AXIOM_FFMPEG_BIN", raising=False)
    monkeypatch.setattr(
        "axiom.core.toolpaths.shutil.which",
        lambda name: r"C:\Tools\ffmpeg.exe",
    )

    window = MainWindow()
    qtbot.addWidget(window)

    label = window.path_auto_labels["Configure.FFmpegPath_Text"]
    assert not label.isHidden()
    shown = label.text().removeprefix("Auto: ")
    assert Path(shown) == Path(r"C:\Tools\ffmpeg.exe")
    assert window.widgets["Configure.FFmpegPath_Text"].text() == "<auto>"


def test_manual_tool_path_browse_and_auto_reset(qtbot, monkeypatch):
    monkeypatch.setattr(
        "axiom.ui.main_window.QFileDialog.getOpenFileName",
        lambda *args, **kwargs: (
            r"C:\Custom\ffmpeg.exe",
            "Executables (*.exe)",
        ),
    )
    window = MainWindow()
    qtbot.addWidget(window)

    window.path_browse_buttons["Configure.FFmpegPath_Text"].click()
    edit = window.widgets["Configure.FFmpegPath_Text"]
    assert edit.text() == r"C:\Custom\ffmpeg.exe"
    assert window.path_auto_labels["Configure.FFmpegPath_Text"].isHidden()

    window.path_auto_buttons["Configure.FFmpegPath_Text"].click()
    assert edit.text() == "<auto>"
    assert not window.path_auto_labels["Configure.FFmpegPath_Text"].isHidden()


def test_log_path_has_browse_button(qtbot, monkeypatch):
    monkeypatch.setattr(
        "axiom.ui.main_window.QFileDialog.getSaveFileName",
        lambda *args, **kwargs: (
            r"C:\Logs\axiom.log",
            "Log files (*.log *.txt)",
        ),
    )
    window = MainWindow()
    qtbot.addWidget(window)

    window.path_browse_buttons["Configure.LogPath_Text"].click()
    assert (
        window.widgets["Configure.LogPath_Text"].text()
        == r"C:\Logs\axiom.log"
    )
