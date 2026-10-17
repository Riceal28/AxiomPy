"""GUI smoke tests for the M2 shell."""

import threading

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtWidgets import QApplication

from axiom.core.config import Settings
from axiom.core.runner import RunOptions
from axiom.ui.main_window import MainWindow
from axiom.ui.main_window import _RunWorker


def test_main_window_has_all_top_level_tabs(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.tabs.count() == 6
    assert [window.tabs.tabText(i) for i in range(6)] == [
        "Format",
        "Video",
        "Audio",
        "Subtitles",
        "Filters",
        "Settings",
    ]


def test_default_window_is_720p_with_separate_file_panel(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert (window.width(), window.height()) == (1280, 720)
    assert window.path_panel.title() == "Input / Output"
    assert window.path_panel.objectName() == "pathPanel"
    assert (
        window.widgets["Format.Format_Container_SelectedItem"].currentText()
        == "mp4"
    )


def test_font_size_applies_immediately(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.font_size_combo.setCurrentText("12")
    assert QApplication.instance().font().pointSize() == 12

    window._apply_font_size(9)


def test_paths_and_container_refresh_script(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\clip.mkv")
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    script = window._generated_text
    assert 'C:\\Input\\clip.mkv' in script
    assert 'C:\\Input\\clip.mp4' in script
    assert "-c:v libx264" in script


def test_preset_updates_container_and_codec(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\clip.mp4")
    window.preset_combo.setCurrentText("HTML5")
    assert window.widgets["Format.Format_Container_SelectedItem"].currentText() == "webm"
    assert window.widgets["Video.Video_Codec_SelectedItem"].currentText() == "VP8"
    assert "-c:v libvpx" in window._generated_text


def test_preset_locks_identity_controls_with_hover_reason(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.preset_combo.setCurrentText("HD High")

    container = window.widgets["Format.Format_Container_SelectedItem"]
    codec = window.widgets["Video.Video_Codec_SelectedItem"]
    hardware = window.widgets["Video.Video_HWAccel_SelectedItem"]
    for widget in (container, codec, hardware):
        assert not widget.isEnabled()
        assert "HD High" in widget.toolTip()
        assert "Unlock" in widget.toolTip()
    container_label = window.widget_labels["Format.Format_Container_SelectedItem"]
    assert not container_label.isEnabled()
    assert "HD High" in container_label.toolTip()
    assert not window.preset_hint.isHidden()
    assert "HD High" in window.preset_hint.text()
    assert "Hover" in window.preset_hint.text()

    window.preset_unlock_button.click()
    assert container.isEnabled()
    assert codec.isEnabled()
    assert container_label.isEnabled()
    assert window.preset_unlock_button.isHidden()
    assert not window.preset_hint.isHidden()
    assert "Active parameter presets" in window.preset_hint.text()

    window.preset_combo.setCurrentText("Preset")
    assert container.isEnabled()


def _wheel_event() -> QWheelEvent:
    return QWheelEvent(
        QPointF(10, 10),
        QPointF(10, 10),
        QPoint(0, 0),
        QPoint(0, 120),
        Qt.NoButton,
        Qt.NoModifier,
        Qt.NoScrollPhase,
        False,
    )


def test_mouse_wheel_adjustment_is_opt_in_and_persisted(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    combo = window.widgets["Video.Video_Quality_SelectedItem"]

    assert window.wheel_adjust_check.isChecked() is False
    combo.setCurrentIndex(2)
    before = combo.currentIndex()
    QApplication.sendEvent(combo, _wheel_event())
    assert combo.currentIndex() == before

    window.wheel_adjust_check.setChecked(True)
    QApplication.sendEvent(combo, _wheel_event())
    assert combo.currentIndex() != before

    path = tmp_path / "axiom.json"
    window._save_settings(path)
    restored = MainWindow()
    qtbot.addWidget(restored)
    restored._load_settings(path)
    assert restored.wheel_adjust_check.isChecked() is True
    assert restored._wheel_guard.enabled is True


def test_parameter_presets_gray_and_explain_dependent_controls(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")

    quality = window.widgets["Video.Video_Quality_SelectedItem"]
    crf = window.widgets["Video.Video_CRF_Text"]
    quality.setCurrentText("High")
    assert not crf.isEnabled()
    assert "video quality preset 'High'" in crf.toolTip()
    assert not window.widget_labels["Video.Video_CRF_Text"].isEnabled()
    assert "video quality 'High'" in window.preset_hint.text()

    quality.setCurrentText("Custom")
    assert crf.isEnabled()
    window.widgets["Video.Video_Optimize_SelectedItem"].setCurrentText("None")
    assert window.preset_hint.isHidden()

    optimize = window.widgets["Video.Video_Optimize_SelectedItem"]
    tune = window.widgets["Video.Video_Optimize_Tune_SelectedItem"]
    optimize.setCurrentText("PC HD")
    assert not tune.isEnabled()
    assert "optimization preset 'PC HD'" in tune.toolTip()
    assert "optimization 'PC HD'" in window.preset_hint.text()

    scale = window.widgets["Video.Video_Scale_SelectedItem"]
    width = window.widgets["Video.Video_Width_Text"]
    scale.setCurrentText("1080p")
    assert not width.isEnabled()
    assert "size preset '1080p'" in width.toolTip()
    assert "size '1080p'" in window.preset_hint.text()

    audio_quality = window.widgets["Audio.Audio_Quality_SelectedItem"]
    audio_bitrate = window.widgets["Audio.Audio_BitRate_Text"]
    audio_quality.setCurrentText("192")
    assert not audio_bitrate.isEnabled()
    assert "audio quality preset '192'" in audio_bitrate.toolTip()


def test_scale_controls_follow_custom_and_source(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    scale = window.widgets["Video.Video_Scale_SelectedItem"]
    width = window.widgets["Video.Video_Width_Text"]
    height = window.widgets["Video.Video_Height_Text"]

    scale.setCurrentText("Custom")
    assert width.isEnabled()
    assert height.isEnabled()

    scale.setCurrentText("Source")
    assert not width.isEnabled()
    assert not height.isEnabled()


def test_quality_change_keeps_selected_video_codec(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    codec = window.widgets["Video.Video_Codec_SelectedItem"]
    original = codec.currentText()

    window.widgets["Video.Video_Quality_SelectedItem"].setCurrentText("Custom")

    assert codec.currentText() == original
    assert "-c:v libx264" in window._generated_text


def test_custom_quality_clears_named_values_once_and_keeps_edits(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    quality = window.widgets["Video.Video_Quality_SelectedItem"]
    bitrate = window.widgets["Video.Video_BitRate_Text"]
    crf = window.widgets["Video.Video_CRF_Text"]
    pass_mode = window.widgets["Video.Video_Pass_SelectedItem"]

    quality.setCurrentText("High")
    assert crf.text() == "20"

    quality.setCurrentText("Custom")
    assert bitrate.text() == ""
    assert crf.text() == ""

    bitrate.setText("4500")
    pass_mode.setCurrentText("1 Pass")
    assert bitrate.text() == "4500"
    assert "-b:v 4500K" in window._generated_text


def test_batch_queue_lists_matching_files(qtbot, tmp_path):
    (tmp_path / "a.mp4").write_text("x", encoding="utf-8")
    (tmp_path / "b.mkv").write_text("x", encoding="utf-8")
    (tmp_path / "c.MP4").write_text("x", encoding="utf-8")

    window = MainWindow()
    qtbot.addWidget(window)
    window.batch_check.setChecked(True)
    window.input_edit.setText(str(tmp_path))
    window.batch_ext.setText("mp4")

    names = [
        window.batch_list.item(row, 0).text()
        for row in range(window.batch_list.rowCount())
    ]
    assert names == ["a.mp4", "c.MP4"]
    assert window.batch_status.text() == "2 file(s) queued"


def test_batch_status_tracks_input_files(qtbot, tmp_path):
    (tmp_path / "a.mp4").write_text("x", encoding="utf-8")
    (tmp_path / "b.mp4").write_text("x", encoding="utf-8")
    window = MainWindow()
    qtbot.addWidget(window)
    window.batch_check.setChecked(True)
    window.input_edit.setText(str(tmp_path))
    window.batch_ext.setText("mp4")

    window._handle_batch_log(
        f"Input #0, mov, from '{tmp_path / 'a.mp4'}':"
    )
    assert window.batch_list.item(0, 1).text() == "Running"
    window._handle_batch_log(
        f"Input #0, mov, from '{tmp_path / 'b.mp4'}':"
    )
    assert window.batch_list.item(0, 1).text() == "Completed"
    assert window.batch_list.item(1, 1).text() == "Running"
    window._handle_batch_log("Error opening input: Invalid argument")
    assert window.batch_list.item(1, 1).text() == "Failed"


def test_audio_metadata_editor_updates_script(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    window.state.set("_audio_paths", [str(tmp_path / "commentary.m4a")])
    window._populate_widgets()
    window.widgets["Audio.Audio_Stream_SelectedItem"].setCurrentText("mux")
    window.audio_list.setCurrentRow(0)

    window.audio_meta_title.setText("Commentary")
    window.audio_meta_language.setCurrentText("English")
    window.audio_meta_delay.setText("+250")

    row = window.state.get("_audio_metadata")[0]
    assert row == {
        "title": "Commentary",
        "language": "English",
        "delay": "+250",
    }
    script = " ".join(window.script_view.toPlainText().splitlines())
    assert '-metadata:s:a:0 title="Commentary"' in script
    assert '-metadata:s:a:0 language="en"' in script


def test_audio_stream_defaults_to_all(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window.state.get("Audio.Audio_Stream_SelectedItem") == "all"
    stream = window.widgets["Audio.Audio_Stream_SelectedItem"]
    assert stream.currentText() == "all"

    window.input_edit.setText("C:\\Input\\clip.mkv")
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    assert window.state.get("Audio.Audio_Stream_SelectedItem") == "all"
    assert "-map 0:a?" in window._generated_text


def test_hardware_acceleration_drives_codec_and_quality(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\clip.mkv")
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    hardware = window.widgets["Video.Video_HWAccel_SelectedItem"]
    transcode = window.widgets["Video.Video_HWAccel_Transcode_SelectedItem"]
    codec = window.widgets["Video.Video_Codec_SelectedItem"]

    hardware.setCurrentText("On")
    assert transcode.isEnabled()
    assert transcode.currentText() == "auto"
    assert "H264 NVENC" in [codec.itemText(i) for i in range(codec.count())]

    transcode.setCurrentText("NVIDIA NVENC")
    assert codec.currentText() == "H264 NVENC"
    window.widgets["Video.Video_Quality_SelectedItem"].setCurrentText("High")
    window.widgets["Video.Video_Pass_SelectedItem"].setCurrentText("CRF")
    assert "-rc:v vbr_hq -crf 20" in window._generated_text

    codec.setCurrentText("HEVC NVENC")
    assert transcode.currentText() == "NVIDIA NVENC"

    hardware.setCurrentText("Off")
    assert transcode.currentText() == "off"
    assert codec.currentText() == "x265"


def test_stream_metadata_follows_reordering(qtbot, tmp_path):
    window = MainWindow()
    qtbot.addWidget(window)
    window.state.set(
        "_audio_paths",
        [str(tmp_path / "a.m4a"), str(tmp_path / "b.m4a")],
    )
    window.state.set(
        "_audio_metadata",
        [{"title": "A"}, {"title": "B"}],
    )
    window._populate_widgets()
    window.audio_list.setCurrentRow(0)
    window._move_stream(window.audio_list, 1)

    assert [item["title"] for item in window.state.get("_audio_metadata")] == [
        "B",
        "A",
    ]
    assert [path.rsplit("\\", 1)[-1] for path in window.state.get("_audio_paths")] == [
        "b.m4a",
        "a.m4a",
    ]


def test_script_sort_and_inline_toggle(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\clip.mkv")
    generated = window._regenerate(force=True)
    inline = " ".join(generated.splitlines())
    assert window.auto_sort_check.isChecked()
    assert window.sort_button.text() == "Inline"
    assert window.script_view.toPlainText().split() == inline.split()

    window.sort_button.click()
    assert window.sort_button.text() == "Sort"
    assert not window.auto_sort_check.isChecked()
    assert window.script_view.toPlainText() == inline

    window.sort_button.click()
    assert window.sort_button.text() == "Inline"
    assert window.auto_sort_check.isChecked()
    assert len(window.script_view.toPlainText().splitlines()) > 1


def test_output_token_list_is_populated(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.token_list.count() >= 15
    assert window.token_list.item(0).text() == "HW Accel"


def test_settings_round_trip(qtbot, tmp_path):
    path = tmp_path / "axiom.json"
    window = MainWindow()
    qtbot.addWidget(window)
    window.state.set("Configure.Shell_SelectedItem", "PowerShell")
    window.state.set("Configure.Threads_SelectedItem", "4")
    window._save_settings(path)

    restored = MainWindow()
    qtbot.addWidget(restored)
    restored._load_settings(path)
    assert restored.widgets["Configure.Shell_SelectedItem"].currentText() == "PowerShell"
    assert restored.widgets["Configure.Threads_SelectedItem"].currentText() == "4"


def test_workspace_round_trip(qtbot, tmp_path):
    path = tmp_path / "axiom.json"
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\workspace.mkv")
    window.output_edit.setText("C:\\Output\\")
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    window.tabs.setCurrentIndex(1)
    window.video_tabs.setCurrentIndex(1)
    window.font_size_combo.setCurrentText("11")
    window._save_settings(path)

    restored = MainWindow()
    qtbot.addWidget(restored)
    restored._load_settings(path)

    assert restored.input_edit.text() == "C:\\Input\\workspace.mkv"
    assert restored.output_edit.text() == "C:\\Output\\"
    assert (
        restored.widgets["Format.Format_Container_SelectedItem"].currentText()
        == "mp4"
    )
    assert restored.tabs.currentIndex() == 1
    assert restored.video_tabs.currentIndex() == 1
    assert restored.font_size_combo.currentText() == "11"
    assert QApplication.instance().font().pointSize() == 11
    restored._apply_font_size(9)


def test_workspace_persistence_can_be_disabled(qtbot, tmp_path):
    path = tmp_path / "axiom.json"
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\must-not-restore.mkv")
    window.save_workspace_check.setChecked(False)
    window._save_settings(path)

    values = Settings.load(path).values
    assert values["Ui.SaveWorkspaceOnExit"] is False
    assert "Ui.Workspace" not in values

    restored = MainWindow()
    qtbot.addWidget(restored)
    restored._load_settings(path)
    assert restored.input_edit.text() == ""
    assert restored.save_workspace_check.isChecked() is False


def test_close_saves_workspace_when_enabled(qtbot, tmp_path):
    path = tmp_path / "axiom.json"
    window = MainWindow()
    qtbot.addWidget(window)
    window._settings_path = path
    window._persist_on_close = True
    window.input_edit.setText("C:\\Input\\saved-on-close.mkv")

    window.close()

    assert path.is_file()
    restored = MainWindow()
    qtbot.addWidget(restored)
    restored._load_settings(path)
    assert restored.input_edit.text() == "C:\\Input\\saved-on-close.mkv"


def test_console_title_modes(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\clip.mkv")
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    window.state.set("Configure.ShellTitle_SelectedItem", "Filename")
    assert window._console_title() == "clip.mp4"
    window.state.set("Configure.ShellTitle_SelectedItem", "Filename+Tokens")
    assert window._console_title() == "clip.mp4"
    window.state.set("Configure.ShellTitle_SelectedItem", "Disabled")
    assert window._console_title() == ""


def test_preview_launches_ffplay(qtbot, tmp_path, monkeypatch):
    source = tmp_path / "clip.mp4"
    source.write_bytes(b"x")
    calls = []
    monkeypatch.setattr(
        "axiom.ui.main_window.preview_async",
        lambda path, ffplay: calls.append((str(path), ffplay)),
    )
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText(str(source))
    window._preview()
    assert calls == [(str(source), "ffplay")]


def test_run_worker_normalizes_windows_exit_code(qtbot, monkeypatch):
    monkeypatch.setattr(
        "axiom.ui.main_window.run_script",
        lambda *args, **kwargs: 0xFFFFFFEA,
    )
    window = MainWindow()
    qtbot.addWidget(window)
    worker = _RunWorker("exit /b 4294967274", RunOptions(), threading.Event())
    completed = []
    worker.done.connect(
        lambda code, cancelled: completed.append((code, cancelled))
    )

    worker.run()

    assert completed == [(-22, False)]


def test_run_releases_worker_only_after_thread_finishes(qtbot, monkeypatch):
    monkeypatch.setattr(
        "axiom.ui.main_window.run_script",
        lambda *args, **kwargs: 0xFFFFFFEA,
    )
    window = MainWindow()
    qtbot.addWidget(window)
    window.script_view.setPlainText("exit /b 4294967274")

    window._run()

    assert window._worker is not None
    qtbot.waitUntil(lambda: window._worker is None, timeout=2000)
    assert window.status_label.text() == "Failed with exit code -22"


def test_nvenc_api_mismatch_gets_actionable_status(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    window._on_log(
        "Driver does not support the required nvenc API version. "
        "Required: 13.1 Found: 13.0"
    )
    window._on_run_done(1, False)

    assert "NVENC driver mismatch" in window.status_label.text()
    assert "Hardware Acceleration" in window.status_label.text()
