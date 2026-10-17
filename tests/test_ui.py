"""GUI smoke tests for the M2 shell."""

import json
import os
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from types import SimpleNamespace

from PySide6.QtCore import QPoint, QPointF, QThread, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication

import axiom.ui.main_window as main_window_module
from axiom.core.config import Settings
from axiom.core.notify import (
    BATCH_NOTIFY_BATCH_END,
    BATCH_NOTIFY_EACH_FILE,
    NOTIFY_MESSAGE_EXAMPLE,
    NotifyStore,
    render_notify,
)
from axiom.core.runner import RunOptions, RunReport
from axiom.ui.main_window import MainWindow
from axiom.ui.main_window import _RunWorker
from axiom.ui.main_window import PROGRESS_INTERVAL_KEY


def test_main_window_has_all_top_level_tabs(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    assert window.tabs.count() == 7
    assert [window.tabs.tabText(i) for i in range(7)] == [
        "Format",
        "Video",
        "Audio",
        "Subtitles",
        "Filters",
        "Notify",
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


def test_mouse_wheel_guard_covers_notify_controls(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    method = window.notify_method_combo
    timeout = window.notify_timeout_spin
    method.setCurrentIndex(1)
    timeout.setValue(20000)
    method_index = method.currentIndex()
    timeout_value = timeout.value()

    QApplication.sendEvent(method, _wheel_event())
    QApplication.sendEvent(timeout, _wheel_event())

    assert method.currentIndex() == method_index
    assert timeout.value() == timeout_value

    window.wheel_adjust_check.setChecked(True)
    QApplication.sendEvent(method, _wheel_event())
    QApplication.sendEvent(timeout, _wheel_event())

    assert method.currentIndex() != method_index
    assert timeout.value() != timeout_value


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


def test_custom_quality_starts_on_crf_and_makes_rate_controls_effective(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    quality = window.widgets["Video.Video_Quality_SelectedItem"]
    pass_mode = window.widgets["Video.Video_Pass_SelectedItem"]
    crf = window.widgets["Video.Video_CRF_Text"]
    vbr = window.widgets["Video.Video_VBR_IsChecked"]
    min_rate = window.widgets["Video.Video_MinRate_Text"]

    quality.setCurrentText("Custom")
    assert pass_mode.currentText() == "CRF"
    assert crf.isEnabled()
    assert not min_rate.isEnabled()
    assert "CRF has no minimum-bitrate target" in min_rate.toolTip()

    crf.setText("22")
    assert "-crf 22" in window._generated_text
    window.widgets["Video.Video_BitRate_Text"].setText("4000")
    assert "-b:v 4000K" in window._generated_text
    assert "-maxrate" not in window._generated_text
    assert "-bufsize" not in window._generated_text
    window.widgets["Video.Video_MaxRate_Text"].setText("3000")
    assert "-maxrate 4000K" in window._generated_text
    assert "-maxrate 3000K" not in window._generated_text
    assert "-bufsize 8000K" in window._generated_text

    pass_mode.setCurrentText("1 Pass")
    assert not crf.isEnabled()
    assert "CRF is only used by the CRF encoding pass" in crf.toolTip()
    assert vbr.isEnabled()
    assert min_rate.isEnabled()

    pass_mode.setCurrentText("CRF")
    assert crf.isEnabled()
    assert not vbr.isEnabled()
    assert "CRF is variable bitrate by definition" in vbr.toolTip()


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
    output = tmp_path / "out"
    output.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
    window.batch_check.setChecked(True)
    window.input_edit.setText(str(tmp_path))
    window.output_edit.setText(str(output) + "\\")
    window.batch_ext.setText("mp4")

    window._handle_batch_log(
        f"Input #0, mov, from '{tmp_path / 'a.mp4'}':"
    )
    assert window.batch_list.item(0, 1).text() == "Running"
    (output / "a.mp4").write_text("done", encoding="utf-8")
    window._handle_batch_log(
        f"Input #0, mov, from '{tmp_path / 'b.mp4'}':"
    )
    assert window.batch_list.item(0, 1).text() == "Completed"
    assert window.batch_list.item(1, 1).text() == "Running"
    window._handle_batch_log("Error opening input: Invalid argument")
    assert window.batch_list.item(1, 1).text() == "Failed"


def test_batch_next_file_without_output_marks_previous_failed(
    qtbot,
    tmp_path,
):
    source = tmp_path / "in"
    source.mkdir()
    (source / "a.mp4").write_text("x", encoding="utf-8")
    (source / "b.mp4").write_text("x", encoding="utf-8")
    output = tmp_path / "out"
    output.mkdir()
    window = MainWindow()
    qtbot.addWidget(window)
    window.batch_check.setChecked(True)
    window.input_edit.setText(str(source))
    window.output_edit.setText(str(output) + "\\")
    window.batch_ext.setText("mp4")

    window._handle_batch_log(
        f"Input #0, mov, from '{source / 'a.mp4'}':"
    )
    window._handle_batch_log(
        f"Input #0, mov, from '{source / 'b.mp4'}':"
    )

    assert window.batch_list.item(0, 1).text() == "Failed"
    assert "not created or updated" in window._batch_file_errors[0]


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


def test_progress_update_interval_defaults_to_500ms_and_is_configurable(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)

    assert window._run_options().progress_interval_ms == 500

    window.progress_interval_spin.setValue(250)

    assert window._run_options().progress_interval_ms == 250
    assert window._settings_values()[PROGRESS_INTERVAL_KEY] == 250


def _notify_parameter_row(window, key):
    for row in range(window.notify_parameter_table.rowCount()):
        item = window.notify_parameter_table.item(row, 1)
        if item is not None and item.text() == key:
            return row
    raise AssertionError(f"missing notify parameter {key}")


def test_notify_parameter_rename_and_disable_updates_preview(qtbot, tmp_path):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    row = _notify_parameter_row(window, "status")

    window.notify_parameter_table.item(row, 2).setText("State")

    assert "State: Test" in window.notify_preview.toPlainText()
    status = next(
        parameter
        for parameter in window._notify_config.parameters
        if parameter.key == "status"
    )
    assert status.label == "State"

    window.notify_parameter_table.item(row, 0).setCheckState(Qt.Unchecked)

    status = next(
        parameter
        for parameter in window._notify_config.parameters
        if parameter.key == "status"
    )
    assert status.enabled is False
    assert "State: Test" not in window.notify_preview.toPlainText()


def test_notify_parameter_change_is_saved_immediately(qtbot, tmp_path):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    row = _notify_parameter_row(window, "status")

    window.notify_parameter_table.item(row, 0).setCheckState(Qt.Unchecked)
    window.notify_parameter_table.item(row, 2).setText("Immediate State")

    loaded = NotifyStore(path).load_strict()
    status = next(
        parameter
        for parameter in loaded.parameters
        if parameter.key == "status"
    )
    assert status.enabled is False
    assert status.label == "Immediate State"


def test_notify_parameter_choices_follow_enabled_parameters(
    qtbot,
    tmp_path,
):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    row = _notify_parameter_row(window, "status")
    combo = window.notify_body_parameter_combo

    assert combo.findData("status") >= 0

    window.notify_parameter_table.item(row, 0).setCheckState(Qt.Unchecked)

    assert combo.findData("status") == -1
    assert window.notify_message_parameter_combo.findData("status") == -1


def test_notify_insert_enabled_parameter_into_body_and_message(
    qtbot,
    tmp_path,
):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)

    window.notify_body_edit.clear()
    body_combo = window.notify_body_parameter_combo
    body_combo.setCurrentIndex(body_combo.findData("exit_code"))
    window._insert_notify_body_parameter()
    assert window.notify_body_edit.toPlainText() == "{exit_code}"
    assert NotifyStore(path).load_strict().body == "{exit_code}"

    window.notify_message_edit.clear()
    message_combo = window.notify_message_parameter_combo
    message_combo.setCurrentIndex(message_combo.findData("output_name"))
    window._insert_notify_message_parameter()
    assert window.notify_message_edit.toPlainText() == "{output_name}"


def test_notify_repeated_ui_changes_are_all_saved(qtbot, tmp_path):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)

    window.notify_url_edit.setText("https://first.example/hook")
    assert NotifyStore(path).load_strict().url == (
        "https://first.example/hook"
    )

    window.notify_url_edit.setText("https://second.example/hook")
    assert NotifyStore(path).load_strict().url == (
        "https://second.example/hook"
    )

    row = _notify_parameter_row(window, "status")
    window.notify_parameter_table.item(row, 2).setText("Second Label")
    assert NotifyStore(path).load_strict().parameters[row].label == (
        "Second Label"
    )


def test_notify_parameter_editor_commits_when_window_closes(
    qtbot,
    tmp_path,
):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.show()
    window.tabs.setCurrentIndex(5)
    window.notify_tabs.setCurrentIndex(1)
    QApplication.processEvents()
    row = _notify_parameter_row(window, "status")
    item = window.notify_parameter_table.item(row, 2)

    window.notify_parameter_table.editItem(item)
    editor = QApplication.focusWidget()
    editor.selectAll()
    QTest.keyClicks(editor, "Saved State")
    window.close()

    loaded = NotifyStore(path).load_strict()
    status = next(
        parameter
        for parameter in loaded.parameters
        if parameter.key == "status"
    )
    assert status.label == "Saved State"


def test_notify_parameter_editor_saves_repeated_edits(qtbot, tmp_path):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.show()
    window.tabs.setCurrentIndex(5)
    window.notify_tabs.setCurrentIndex(1)
    QApplication.processEvents()
    row = _notify_parameter_row(window, "status")
    item = window.notify_parameter_table.item(row, 2)

    for value in ("First Edit", "Second Edit"):
        window.notify_parameter_table.editItem(item)
        editor = QApplication.focusWidget()
        editor.selectAll()
        QTest.keyClicks(editor, value)
        QTest.keyClick(editor, Qt.Key_Return)
        QApplication.processEvents()

        loaded = NotifyStore(path).load_strict()
        status = next(
            parameter
            for parameter in loaded.parameters
            if parameter.key == "status"
        )
        assert status.label == value


def test_disabled_input_name_is_removed_from_automatic_message(
    qtbot,
    tmp_path,
):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    window.input_edit.setText(str(tmp_path / "clip.mkv"))
    window.output_edit.setText(str(tmp_path / "out") + "\\")
    window.notify_body_edit.setPlainText(
        '{"message": {message_json}, "params": {params_json}}'
    )
    row = _notify_parameter_row(window, "input_name")

    window.notify_parameter_table.item(row, 0).setCheckState(Qt.Unchecked)

    preview = window.notify_preview.toPlainText()
    body = json.loads(preview.split("BODY\n", 1)[1])
    assert "Input Name" not in body["message"]
    assert "Input Name" not in body["params"]


def test_disabled_parameter_referenced_by_template_shows_note(
    qtbot,
    tmp_path,
):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    window.notify_message_edit.setPlainText(
        "Input: {input_name}\nStatus: {status}"
    )
    row = _notify_parameter_row(window, "input_name")

    window.notify_parameter_table.item(row, 0).setCheckState(Qt.Unchecked)

    preview = window.notify_preview.toPlainText()
    assert "TEMPLATE NOTE" in preview
    assert "input_name" in preview


def test_notify_insert_example_fills_complete_message(qtbot, tmp_path):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)

    assert window.notify_message_edit.toPlainText() == ""

    window.notify_example_button.click()

    assert window.notify_message_edit.toPlainText() == (
        NOTIFY_MESSAGE_EXAMPLE
    )
    assert window._notify_config.message_template == NOTIFY_MESSAGE_EXAMPLE
    preview = window.notify_preview.toPlainText()
    assert "MESSAGE\nTest: " in preview
    assert "Progress: 100.0%" in preview


def test_notify_seq_parameter_is_enabled_in_automatic_message(
    qtbot,
    tmp_path,
):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    row = _notify_parameter_row(window, "seq")

    assert (
        window.notify_parameter_table.item(row, 0).checkState()
        == Qt.Checked
    )
    assert "Sequence: 1" in window.notify_preview.toPlainText()


def test_notify_header_checkbox_controls_rendered_headers(
    qtbot,
    tmp_path,
):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    assert window.notify_header_table.rowCount() == 1

    window.notify_header_table.item(0, 0).setCheckState(Qt.Unchecked)

    assert window._notify_config.headers[0].enabled is False
    rendered = render_notify(
        window._notify_config,
        window._notify_test_context(),
    )
    assert rendered.headers == ()

    window.notify_header_table.item(0, 0).setCheckState(Qt.Checked)

    rendered = render_notify(
        window._notify_config,
        window._notify_test_context(),
    )
    assert rendered.headers == (("Content-Type", "application/json"),)


def test_notify_table_checkbox_clicks_toggle_bindings(
    qtbot,
    tmp_path,
):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    window.show()
    window.tabs.setCurrentIndex(5)
    window.notify_tabs.setCurrentIndex(1)
    QApplication.processEvents()

    row = _notify_parameter_row(window, "status")
    parameter_item = window.notify_parameter_table.item(row, 0)
    parameter_rect = window.notify_parameter_table.visualItemRect(
        parameter_item
    )
    QTest.mouseClick(
        window.notify_parameter_table.viewport(),
        Qt.LeftButton,
        pos=QPoint(parameter_rect.left() + 8, parameter_rect.center().y()),
    )

    assert parameter_item.checkState() == Qt.Unchecked
    assert next(
        parameter
        for parameter in window._notify_config.parameters
        if parameter.key == "status"
    ).enabled is False

    window.notify_tabs.setCurrentIndex(0)
    QApplication.processEvents()
    header_item = window.notify_header_table.item(0, 0)
    header_rect = window.notify_header_table.visualItemRect(header_item)
    QTest.mouseClick(
        window.notify_header_table.viewport(),
        Qt.LeftButton,
        pos=QPoint(header_rect.left() + 8, header_rect.center().y()),
    )

    assert header_item.checkState() == Qt.Unchecked
    assert window._notify_config.headers[0].enabled is False


def test_notify_parameter_checkbox_can_be_disabled_and_enabled(
    qtbot,
    tmp_path,
):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.show()
    window.tabs.setCurrentIndex(5)
    window.notify_tabs.setCurrentIndex(1)
    QApplication.processEvents()
    row = _notify_parameter_row(window, "status")
    item = window.notify_parameter_table.item(row, 0)
    rect = window.notify_parameter_table.visualItemRect(item)
    point = QPoint(rect.left() + 8, rect.center().y())

    QTest.mouseClick(
        window.notify_parameter_table.viewport(),
        Qt.LeftButton,
        pos=point,
    )
    assert item.checkState() == Qt.Unchecked
    assert NotifyStore(path).load_strict().parameters[row].enabled is False

    QTest.qWait(600)
    QTest.mouseClick(
        window.notify_parameter_table.viewport(),
        Qt.LeftButton,
        pos=point,
    )
    assert item.checkState() == Qt.Checked
    assert NotifyStore(path).load_strict().parameters[row].enabled is True
    assert window.notify_body_parameter_combo.findData("status") >= 0


def test_notify_test_button_uses_custom_http_config(qtbot, tmp_path, monkeypatch):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    captured = {}

    def fake_send(config, context, request_id=""):
        captured["config"] = config
        captured["context"] = context
        captured["request_id"] = request_id
        return True

    monkeypatch.setattr(
        main_window_module,
        "probe_notification_metadata",
        lambda *_args: main_window_module._empty_notify_metadata(),
    )
    monkeypatch.setattr(window._notify_client, "send", fake_send)
    window.notify_method_combo.setCurrentText("PUT")
    window.notify_url_edit.setText("https://example.test/{status}")
    window.notify_body_edit.setPlainText('{"text": "{message}"}')

    window._test_notification()
    qtbot.waitUntil(lambda: bool(captured), timeout=3000)

    rendered = render_notify(
        captured["config"],
        captured["context"],
    )
    assert rendered.method == "PUT"
    assert rendered.url == "https://example.test/Test"
    assert '"text": "Status: Test' in rendered.body
    assert "Sending test notification" in window.notify_status.text()


def test_notify_probe_does_not_block_the_gui(
    qtbot,
    tmp_path,
    monkeypatch,
):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    captured = []
    captured_threads = []

    def delayed_probe(*_args):
        time.sleep(0.25)
        return main_window_module._empty_notify_metadata()

    monkeypatch.setattr(
        main_window_module,
        "probe_notification_metadata",
        delayed_probe,
    )
    monkeypatch.setattr(
        window._notify_client,
        "send",
        lambda config, context, request_id="": (
            captured.append(context)
            or captured_threads.append(QThread.currentThread())
            or True
        ),
    )
    window.notify_url_edit.setText("https://example.test/hook")

    started = time.monotonic()
    window._test_notification()
    elapsed = time.monotonic() - started

    assert elapsed < 0.15
    qtbot.waitUntil(lambda: bool(captured), timeout=3000)
    assert captured_threads[0] is QApplication.instance().thread()


def test_notify_test_button_completes_real_http_dispatch(
    qtbot,
    tmp_path,
):
    received: dict[str, object] = {}

    class Handler(BaseHTTPRequestHandler):
        def do_POST(self) -> None:  # noqa: N802
            length = int(self.headers.get("Content-Length", "0"))
            received["body"] = self.rfile.read(length).decode("utf-8")
            self.send_response(200)
            self.end_headers()
            self.wfile.write(b"ok")

        def log_message(self, *_args) -> None:
            return

    server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    try:
        window = MainWindow(notify_path=tmp_path / "notify.json")
        qtbot.addWidget(window)
        window.notify_url_edit.setText(
            f"http://127.0.0.1:{server.server_address[1]}/hook"
        )
        window._test_notification()

        qtbot.waitUntil(
            lambda: "sent (HTTP 200)" in window.notify_status.text(),
            timeout=5000,
        )
    finally:
        server.shutdown()
        server.server_close()

    assert '"message"' in str(received["body"])
    assert "Notification [" in window.notify_status.text()


def test_notify_sends_only_when_enabled(qtbot, tmp_path, monkeypatch):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    captured = []
    monkeypatch.setattr(
        main_window_module,
        "probe_notification_metadata",
        lambda *_args: main_window_module._empty_notify_metadata(),
    )
    monkeypatch.setattr(
        window._notify_client,
        "send",
        lambda config, context, request_id="": (
            captured.append((config, context)) or True
        ),
    )
    window._notify_config.enabled = False
    window._notify_config.url = "https://example.test/hook"

    window._send_run_notification(0, False)
    assert captured == []

    window._notify_config.enabled = True
    window._send_run_notification(0, False)
    qtbot.waitUntil(lambda: len(captured) == 1, timeout=3000)
    assert len(captured) == 1
    assert captured[0][1]["status"] == "Completed"


def test_notify_hot_reload_applies_external_file_changes(qtbot, tmp_path):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.notify_enabled_check.setChecked(True)
    window.notify_url_edit.setText("https://old.example/hook")
    window._save_notify_config()

    changed = window._notify_config
    changed.url = "https://new.example/hook"
    NotifyStore(path).save(changed)
    window._notify_last_mtime = 0
    window._notify_last_size = None
    window._on_notify_file_changed()

    qtbot.waitUntil(
        lambda: window.notify_url_edit.text()
        == "https://new.example/hook",
        timeout=3000,
    )
    assert window.notify_url_edit.text() == "https://new.example/hook"
    assert "Reloaded" in window.notify_status.text()


def test_notify_hot_reload_keeps_settings_on_partial_json(
    qtbot,
    tmp_path,
):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.notify_enabled_check.setChecked(True)
    window.notify_url_edit.setText("https://old.example/hook")
    window._save_notify_config()

    path.write_text('{"enabled": ', encoding="utf-8")
    window._notify_last_mtime = 0
    window._notify_last_size = None
    window._on_notify_file_changed()

    qtbot.waitUntil(
        lambda: "Hot reload failed" in window.notify_status.text(),
        timeout=4000,
    )
    assert window._notify_config.url == "https://old.example/hook"
    assert window.notify_url_edit.text() == "https://old.example/hook"


def test_notify_hot_reload_handles_atomic_replace(qtbot, tmp_path):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.notify_enabled_check.setChecked(True)
    window.notify_url_edit.setText("https://old.example/hook")
    window._save_notify_config()

    changed = window._notify_config
    changed.url = "https://atomic.example/hook"
    replacement = tmp_path / "notify.next.json"
    NotifyStore(replacement).save(changed)
    os.replace(replacement, path)
    window._notify_last_mtime = 0
    window._notify_last_size = None
    window._on_notify_file_changed()

    qtbot.waitUntil(
        lambda: window.notify_url_edit.text()
        == "https://atomic.example/hook",
        timeout=3000,
    )
    assert window._notify_config.url == "https://atomic.example/hook"


def test_notify_watcher_applies_external_save(qtbot, tmp_path):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.notify_enabled_check.setChecked(True)
    window.notify_url_edit.setText("https://old.example/hook")
    window._save_notify_config()

    changed = window._notify_config
    changed.url = "https://watched.example/hook"
    NotifyStore(path).save(changed)

    qtbot.waitUntil(
        lambda: window.notify_url_edit.text()
        == "https://watched.example/hook",
        timeout=5000,
    )
    assert window._notify_config.url == "https://watched.example/hook"


def test_notify_disabling_hot_reload_still_persists_edits(
    qtbot,
    tmp_path,
):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)

    window.notify_hot_reload_check.setChecked(False)
    window.notify_url_edit.setText("https://saved.example/hook")

    qtbot.waitUntil(path.exists, timeout=3000)
    loaded = NotifyStore(path).load_strict()
    assert loaded.hot_reload is False
    assert loaded.url == "https://saved.example/hook"


def test_notify_hot_reload_rejects_valid_incomplete_object(
    qtbot,
    tmp_path,
):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.notify_enabled_check.setChecked(True)
    window.notify_url_edit.setText("https://old.example/hook")
    window._save_notify_config()

    path.write_text("{}", encoding="utf-8")
    window._on_notify_file_changed()

    qtbot.waitUntil(
        lambda: "Hot reload failed" in window.notify_status.text(),
        timeout=4000,
    )
    assert window._notify_config.enabled is True
    assert window._notify_config.url == "https://old.example/hook"


def test_notify_invalid_startup_file_warns_and_uses_defaults(
    qtbot,
    tmp_path,
):
    path = tmp_path / "notify.json"
    path.write_text('{"enabled": ', encoding="utf-8")

    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)

    assert "Could not load notify.json" in window.notify_status.text()
    assert window._notify_config.url == ""


def test_notify_manual_reload_keeps_settings_on_invalid_file(
    qtbot,
    tmp_path,
):
    path = tmp_path / "notify.json"
    window = MainWindow(notify_path=path)
    qtbot.addWidget(window)
    window.notify_enabled_check.setChecked(True)
    window.notify_url_edit.setText("https://old.example/hook")
    window._save_notify_config()

    path.write_text('{"enabled": ', encoding="utf-8")
    window._reload_notify_config()

    assert window._notify_config.url == "https://old.example/hook"
    assert "Reload failed" in window.notify_status.text()


def test_run_notify_context_contains_ffmpeg_result_fields(qtbot, tmp_path):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    report = RunReport(
        exit_code=1,
        last_file="second.mp4",
        last_progress={
            "frame": "120",
            "fps": "30",
            "bitrate": "800kbits/s",
            "total_size": "4096",
            "out_time": "00:00:04.000000",
            "speed": "2.5x",
            "progress": "end",
        },
    )
    window._worker = SimpleNamespace(
        report=report,
        log_lines=["Error opening input file"],
        script="ffmpeg -i broken.mp4 out.mp4",
        options=SimpleNamespace(shell="CMD"),
    )

    context = window._run_notify_context(1, False)

    assert context["status"] == "Failed"
    assert context["success"] == "false"
    assert context["exit_code"] == "1"
    assert context["current_file"] == "second.mp4"
    assert context["frame"] == "120"
    assert context["fps"] == "30"
    assert context["speed"] == "2.5x"
    assert context["ffmpeg_progress"] == "end"
    assert context["command"] == "ffmpeg -i broken.mp4 out.mp4"
    assert "Error opening" in context["error"]
    window._worker = None


def _batch_notify_window(
    qtbot,
    tmp_path,
    monkeypatch,
    mode,
):
    source = tmp_path / "in"
    source.mkdir()
    (source / "one.mp4").write_bytes(b"x")
    (source / "two.mp4").write_bytes(b"x")
    output = tmp_path / "out"
    output.mkdir()
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    window.input_edit.setText(str(source))
    window.output_edit.setText(str(output) + "\\")
    window.batch_ext.setText("mp4")
    window.state.set("Main.Input_Text", str(source))
    window.state.set("Main.Output_Text", str(output) + "\\")
    window.state.set("Main.BatchExtension_Text", "mp4")
    window.batch_check.setChecked(True)
    window._refresh_batch_queue()
    window._notify_config.enabled = True
    window._notify_config.url = "https://example.test/hook"
    window._notify_config.batch_mode = mode
    metadata = {
        "duration_seconds": "12.500",
        "file_size_bytes": "1234",
        "video_codec": "h264",
        "width": "1920",
        "height": "1080",
        "overall_bitrate": "900000",
        "duration": "12.500",
        "size": "1234",
        "bitrate": "900000",
    }
    monkeypatch.setattr(
        window,
        "_notify_metadata",
        lambda *_args: dict(metadata),
    )
    monkeypatch.setattr(
        main_window_module,
        "probe_notification_metadata",
        lambda *_args: dict(metadata),
    )
    captured = []
    monkeypatch.setattr(
        window._notify_client,
        "send",
        lambda config, context, request_id="": (
            captured.append(context) or True
        ),
    )
    return window, captured, output


def test_notify_batch_mode_controls(qtbot, tmp_path):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)

    assert window.notify_enabled_check.text() == "Enable notifications"
    assert window.notify_batch_mode_combo.count() == 2
    assert (
        window.notify_batch_mode_combo.itemData(0)
        == BATCH_NOTIFY_EACH_FILE
    )
    assert (
        window.notify_batch_mode_combo.itemData(1)
        == BATCH_NOTIFY_BATCH_END
    )
    assert window.notify_batch_mode_combo.isEnabled() is False

    window.batch_check.setChecked(True)

    assert window.notify_batch_mode_combo.isEnabled() is True


def test_batch_each_file_notification_uses_real_path(
    qtbot,
    tmp_path,
    monkeypatch,
):
    window, captured, output = _batch_notify_window(
        qtbot,
        tmp_path,
        monkeypatch,
        BATCH_NOTIFY_EACH_FILE,
    )

    window._track_batch_progress_file("one.mp4")
    window._set_batch_row_status(0, "Completed")
    qtbot.waitUntil(lambda: len(captured) == 1, timeout=3000)

    assert len(captured) == 1
    context = captured[0]
    assert context["job_id"].endswith("-001")
    assert context["seq"] == "1"
    assert context["batch"] == "true"
    assert context["batch_completed"] == "1"
    assert context["batch_count"] == "2"
    assert context["current_file"] == "one.mp4"
    assert context["output"] == str(output / "one.mp4")
    assert "%~n" not in context["output"]
    assert context["duration_seconds"] == "12.500"
    assert context["file_size_bytes"] == "1234"
    assert context["video_codec"] == "h264"
    assert context["width"] == "1920"
    assert context["height"] == "1080"
    assert context["overall_bitrate"] == "900000"

    window._on_run_done(0, False)

    assert len(captured) == 1


def test_batch_end_notification_sends_once(
    qtbot,
    tmp_path,
    monkeypatch,
):
    window, captured, output = _batch_notify_window(
        qtbot,
        tmp_path,
        monkeypatch,
        BATCH_NOTIFY_BATCH_END,
    )

    window._track_batch_progress_file("one.mp4")
    (output / "one.mp4").write_bytes(b"done")
    window._on_run_done(0, False)
    qtbot.waitUntil(lambda: len(captured) == 1, timeout=3000)

    assert len(captured) == 1
    context = captured[0]
    assert context["batch"] == "true"
    assert context["batch_completed"] == "1"
    assert context["output"] == str(output / "one.mp4")


def test_batch_end_notification_reports_mixed_failure(
    qtbot,
    tmp_path,
    monkeypatch,
):
    window, captured, _output = _batch_notify_window(
        qtbot,
        tmp_path,
        monkeypatch,
        BATCH_NOTIFY_BATCH_END,
    )
    window._set_batch_row_status(0, "Failed")
    window._set_batch_row_status(1, "Completed")
    window._batch_current_row = 1
    window._worker = SimpleNamespace(
        report=RunReport(
            started_at=time.time() - 5,
            finished_at=time.time(),
        ),
        script="batch",
        options=SimpleNamespace(shell="PowerShell"),
        log_lines=[],
    )

    window._send_run_notification(0, False)
    qtbot.waitUntil(lambda: bool(captured), timeout=3000)

    assert captured[0]["status"] == "Failed"
    assert captured[0]["success"] == "false"
    assert captured[0]["batch_failed"] == "1"
    window._worker = None


def test_batch_file_notification_uses_per_file_progress_fields(
    qtbot,
    tmp_path,
    monkeypatch,
):
    window, _captured, _output = _batch_notify_window(
        qtbot,
        tmp_path,
        monkeypatch,
        BATCH_NOTIFY_EACH_FILE,
    )
    window._batch_file_progress[0] = {
        "frame": "240",
        "fps": "24",
        "speed": "1.5x",
        "out_time": "00:00:10.000000",
        "progress": "end",
    }
    window._worker = SimpleNamespace(
        report=RunReport(),
        script="batch",
        options=SimpleNamespace(shell="CMD"),
        log_lines=[],
    )

    context = window._batch_file_notify_context(0, "Completed")

    assert context["frame"] == "240"
    assert context["fps"] == "24"
    assert context["speed"] == "1.5x"
    assert context["ffmpeg_progress"] == "end"
    window._worker = None


def test_batch_finish_resolves_rows_from_output_files(
    qtbot,
    tmp_path,
    monkeypatch,
):
    window, captured, output = _batch_notify_window(
        qtbot,
        tmp_path,
        monkeypatch,
        BATCH_NOTIFY_EACH_FILE,
    )
    (output / "one.mp4").write_bytes(b"x")
    (output / "two.mp4").write_bytes(b"x")
    window._worker = SimpleNamespace(
        report=RunReport(started_at=time.time() - 5),
        script="batch",
        options=SimpleNamespace(shell="CMD"),
        log_lines=[],
    )

    window._on_run_done(0, False)
    qtbot.waitUntil(lambda: len(captured) == 2, timeout=3000)

    assert [
        window.batch_list.item(row, 1).text()
        for row in range(window.batch_list.rowCount())
    ] == ["Completed", "Completed"]
    assert len(captured) == 2
    assert captured[1]["seq"] == "2"
    assert captured[1]["batch_completed"] == "2"
    window._worker = None


def test_notify_test_context_uses_real_batch_output(
    qtbot,
    tmp_path,
    monkeypatch,
):
    window, _captured, output = _batch_notify_window(
        qtbot,
        tmp_path,
        monkeypatch,
        BATCH_NOTIFY_EACH_FILE,
    )

    context = window._notify_test_context()

    assert context["seq"] == "1"
    assert context["batch"] == "true"
    assert context["current_file"] == "one.mp4"
    assert context["output"] == str(output / "one.mp4")
    assert "%~n" not in context["output"]


def test_batch_toggle_refreshes_notify_preview(qtbot, tmp_path):
    source = tmp_path / "in"
    source.mkdir()
    (source / "one.mp4").write_bytes(b"x")
    output = tmp_path / "out"
    output.mkdir()
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    window.notify_body_edit.setPlainText(
        '{"seq": {seq}, "output": "{output}"}'
    )
    window.input_edit.setText(str(source))
    window.output_edit.setText(str(output) + "\\")
    window.batch_ext.setText("mp4")
    output_row = _notify_parameter_row(window, "output")
    window.notify_parameter_table.item(
        output_row, 0
    ).setCheckState(Qt.Checked)

    window.batch_check.setChecked(True)

    preview = window.notify_preview.toPlainText()
    body_text = preview.split("BODY\n", 1)[1].split(
        "\n\nTEMPLATE NOTE",
        1,
    )[0]
    body = json.loads(body_text)
    assert body["seq"] == 1
    assert body["output"] == str(output / "one.mp4")
    assert "%~n" not in preview


def test_batch_run_shows_two_progress_bars(qtbot, tmp_path, monkeypatch):
    source = tmp_path / "input"
    source.mkdir()
    (source / "one.mp4").write_bytes(b"x")
    (source / "two.mp4").write_bytes(b"x")
    monkeypatch.setattr(
        "axiom.ui.main_window.run_script",
        lambda *args, **kwargs: 0,
    )
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    window.input_edit.setText(str(source))
    window.batch_ext.setText("mp4")
    window.batch_check.setChecked(True)
    window.script_view.setPlainText("ffmpeg -version")

    window._run()

    assert not window.total_progress_bar.isHidden()
    assert window.progress_bar.format() == "File %p%"
    qtbot.waitUntil(lambda: window._worker is None, timeout=2000)

    window.batch_check.setChecked(False)
    window.script_view.setPlainText("ffmpeg -version")
    window._run()
    assert window.total_progress_bar.isHidden()
    assert window.progress_bar.format() == "%p%"
    qtbot.waitUntil(lambda: window._worker is None, timeout=2000)


def test_batch_queue_restores_from_a_selected_file(
    qtbot,
    tmp_path,
    monkeypatch,
):
    source = tmp_path / "input"
    source.mkdir()
    for name in ("one.mp4", "two.mp4"):
        (source / name).write_bytes(b"x")
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)
    window.input_edit.setText(str(source / "one.mp4"))
    window.batch_ext.setText("mp4")
    window.batch_check.setChecked(True)

    assert [
        window.batch_list.item(row, 0).text()
        for row in range(window.batch_list.rowCount())
    ] == ["one.mp4", "two.mp4"]

    settings_path = tmp_path / "axiom.json"
    window._save_settings(settings_path)
    restored = MainWindow(notify_path=tmp_path / "restored.json")
    qtbot.addWidget(restored)
    restored._load_settings(settings_path)

    assert restored.batch_check.isChecked() is True
    assert restored.batch_list.rowCount() == 2
    assert restored.batch_status.text() == "2 file(s) queued"

    captured = {}

    def fake_run(script, options, **kwargs):
        captured["files"] = list(options.batch_files)
        return 0

    monkeypatch.setattr(
        "axiom.ui.main_window.run_script",
        fake_run,
    )
    restored.script_view.setPlainText("ffmpeg -version")
    restored._run()

    qtbot.waitUntil(lambda: "files" in captured, timeout=2000)
    assert len(captured["files"]) == 2
    qtbot.waitUntil(lambda: restored._worker is None, timeout=2000)


def test_total_progress_bar_accepts_fraction_updates(qtbot, tmp_path):
    window = MainWindow(notify_path=tmp_path / "notify.json")
    qtbot.addWidget(window)

    window._on_total_progress(0.625, "two.mp4")

    assert window.total_progress_bar.value() == 625


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
