"""GUI smoke tests for the M2 shell."""

from axiom.ui.main_window import MainWindow


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


def test_paths_and_container_refresh_script(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\clip.mkv")
    window.widgets["Format.Format_Container_SelectedItem"].setCurrentText("mp4")
    script = window.script_view.toPlainText()
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
    assert "-c:v libvpx" in window.script_view.toPlainText()


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
    assert "-c:v libx264" in window.script_view.toPlainText()


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
        window.batch_list.item(index).text()
        for index in range(window.batch_list.count())
    ]
    assert names == ["a.mp4", "c.MP4"]
    assert window.batch_status.text() == "2 file(s) queued"


def test_script_sort_and_inline_toggle(qtbot):
    window = MainWindow()
    qtbot.addWidget(window)
    window.input_edit.setText("C:\\Input\\clip.mkv")
    generated = window._regenerate(force=True)
    inline = " ".join(generated.splitlines())

    window.sort_button.click()
    assert window.sort_button.text() == "Inline"
    assert len(window.script_view.toPlainText().splitlines()) > 1
    assert window.script_view.toPlainText().split() == inline.split()

    window.sort_button.click()
    assert window.sort_button.text() == "Sort"
    assert window.script_view.toPlainText() == inline


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
