"""Main PySide6 window for AxiomPy."""

from __future__ import annotations

import os
import re
import threading
from pathlib import Path

from PySide6.QtCore import QByteArray, QEvent, QObject, Qt, QThread, Signal
from PySide6.QtGui import QAction, QCloseEvent, QColor, QGuiApplication
from PySide6.QtWidgets import (
    QAbstractSpinBox,
    QAbstractItemView,
    QApplication,
    QCheckBox,
    QComboBox,
    QDockWidget,
    QDoubleSpinBox,
    QFileDialog,
    QFormLayout,
    QGridLayout,
    QGroupBox,
    QHeaderView,
    QHBoxLayout,
    QInputDialog,
    QLabel,
    QLineEdit,
    QListWidget,
    QListWidgetItem,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSpinBox,
    QStatusBar,
    QTabWidget,
    QTableWidget,
    QTableWidgetItem,
    QTextEdit,
    QVBoxLayout,
    QWidget,
)

from axiom.core import controls
from axiom.core.batch_scan import scan_batch_files
from axiom.core.config import PresetStore, Settings
from axiom.core.generate import generate_runnable, resolve_controls
from axiom.core.generate.context import build_context
from axiom.core.generate.naming import OUTPUT_TOKEN_NAMES
from axiom.core.runner import (
    RunOptions,
    normalize_exit_code,
    preview_async,
    run as run_script,
)
from axiom.core.script import Script
from axiom.core.state import AxiomState
from axiom.core.toolpaths import resolve_tool_path

from .control_rules import enabled_key, structural_scope
from .preset_locks import (
    PARAMETER_PRESET_KEYS,
    PRESET_LOCKED_KEYS,
    active_parameter_presets,
    parameter_preset_reason,
    preset_lock_reason,
)


SELECTIVE_COLORS = (
    "Reds",
    "Yellows",
    "Greens",
    "Cyans",
    "Blues",
    "Magentas",
    "Whites",
    "Neutrals",
    "Blacks",
)

BATCH_INPUT_PATTERN = re.compile(r"Input #\d+.*? from '(.+?)'")
DEFAULT_FONT_SIZE = 9
FONT_SIZE_OPTIONS = tuple(range(8, 17))
FONT_SIZE_KEY = "Ui.FontSize"
SAVE_WORKSPACE_KEY = "Ui.SaveWorkspaceOnExit"
MOUSE_WHEEL_KEY = "Ui.MouseWheelAdjust"
WORKSPACE_KEY = "Ui.Workspace"
WORKSPACE_SCHEMA = 1

SETTINGS_KEYS = (
    "Configure.FFmpegPath_Text",
    "Configure.FFprobePath_Text",
    "Configure.FFplayPath_Text",
    "Configure.Shell_SelectedItem",
    "Configure.ProcessPriority_SelectedItem",
    "Configure.Threads_SelectedItem",
    "Configure.OutputOverwrite_SelectedItem",
    "Configure.OutputFileNameSpacing_SelectedItem",
    "Configure.InputFileNameTokens_SelectedItem",
    "Configure.InputFileNameTokensCustom_Text",
    "Configure.OutputNaming_ListView_SelectedItems",
    "Configure.LogCheckBox_IsChecked",
    "Configure.LogPath_Text",
    "Main.CMDWindowKeep_IsChecked",
    "Main.ExternalConsole_IsChecked",
    "Main.AutoSortScript_IsChecked",
    MOUSE_WHEEL_KEY,
)


def _names(items) -> list[str]:
    return controls.item_names(items or [])


def _inline_text(text: str) -> str:
    return " ".join(text.splitlines()).strip()


class PathDropEdit(QLineEdit):
    """Line edit that accepts a local file or folder dragged from Explorer."""

    def dragEnterEvent(self, event) -> None:
        if event.mimeData().hasUrls():
            event.acceptProposedAction()
        else:
            super().dragEnterEvent(event)

    def dropEvent(self, event) -> None:
        paths = [
            url.toLocalFile()
            for url in event.mimeData().urls()
            if url.isLocalFile()
        ]
        if not paths:
            super().dropEvent(event)
            return
        self.setText(paths[0])
        event.acceptProposedAction()


class _RunWorker(QThread):
    log = Signal(str)
    progress = Signal(float, str)
    done = Signal(int, bool)

    def __init__(
        self,
        script: str,
        options: RunOptions,
        cancel: threading.Event,
    ) -> None:
        super().__init__()
        self.script = script
        self.options = options
        self.cancel = cancel

    def run(self) -> None:
        try:
            code = run_script(
                self.script,
                self.options,
                on_log=self.log.emit,
                on_progress=self.progress.emit,
                cancel=self.cancel,
            )
        except Exception as error:
            self.log.emit(f"Failed to run process: {type(error).__name__}: {error}")
            code = 1
        code = normalize_exit_code(code)
        self.done.emit(code, self.cancel.is_set())


class _WheelGuard(QObject):
    """Block wheel events on value controls unless the user opted in."""

    def __init__(self, parent: QObject | None = None) -> None:
        super().__init__(parent)
        self.enabled = False

    def eventFilter(self, obj: QObject, event: QEvent) -> bool:  # type: ignore[override]
        if (
            not self.enabled
            and event.type() == QEvent.Wheel
            and isinstance(obj, (QComboBox, QAbstractSpinBox))
        ):
            return True
        return False


class MainWindow(QMainWindow):
    """Operational shell around the parity-tested core engine."""

    def __init__(self) -> None:
        super().__init__()
        self.state = AxiomState()
        self.state.set("Main.ExternalConsole_IsChecked", False)
        self.presets = PresetStore()
        self.widgets: dict[str, QWidget] = {}
        self.widget_labels: dict[str, QWidget] = {}
        self.path_auto_labels: dict[str, QLabel] = {}
        self.path_browse_buttons: dict[str, QPushButton] = {}
        self.path_auto_buttons: dict[str, QPushButton] = {}
        self.path_tools: dict[str, str] = {}
        self.combo_items: dict[str, str] = {}
        self._loading = False
        self._updating_script = False
        self._script_sorted = bool(
            self.state.get("Main.AutoSortScript_IsChecked")
        )
        self._script_dirty = False
        self._generated_text = ""
        self._worker: _RunWorker | None = None
        self._cancel_event = threading.Event()
        self._metadata_loading = False
        self._batch_current_row = -1
        self._last_error_hint = ""
        self._font_size = DEFAULT_FONT_SIZE
        self._save_workspace_on_exit = True
        self._mouse_wheel_adjust = False
        self._preset_locked = False
        self._initial_parameter_presets: frozenset[str] = frozenset()
        self._initial_parameter_values: dict[str, object] = {}
        self._settings_path: Path | None = None
        self._persist_on_close = False
        self._wheel_guard = _WheelGuard(self)
        self._base_tooltips: dict[str, str] = {}

        self.setWindowTitle("AxiomPy")
        self.resize(1280, 720)
        # New installations open on MP4, the most common share/encode container.
        # The core DEFAULTS table keeps the original webm values for parity tests.
        self.state.set("Format.Format_Container_SelectedItem", "mp4")
        self.state.set("Format.Format_Container_SelectedIndex", 2)
        self._build_ui()
        self._load_presets()
        self._refresh_controls(full=True)
        self.state.set("Audio.Audio_Stream_SelectedItem", "all")
        self._populate_widgets()
        self._initial_parameter_presets = frozenset(
            active_parameter_presets(self.state)
        )
        self._initial_parameter_values = {
            key: self.state.get(key) for key in PARAMETER_PRESET_KEYS
        }
        self._apply_preset_locks()
        self._regenerate(force=True)

    # -- construction -----------------------------------------------------
    def _build_ui(self) -> None:
        central = QWidget(self)
        layout = QVBoxLayout(central)
        layout.addWidget(self._build_paths())

        self.tabs = QTabWidget(central)
        self.tabs.addTab(self._build_format_tab(), "Format")
        self.tabs.addTab(self._build_video_tab(), "Video")
        self.tabs.addTab(self._build_audio_tab(), "Audio")
        self.tabs.addTab(self._build_subtitles_tab(), "Subtitles")
        self.tabs.addTab(self._build_filters_tab(), "Filters")
        self.tabs.addTab(self._build_settings_tab(), "Settings")
        layout.addWidget(self.tabs, 1)
        self.setCentralWidget(central)
        self._build_docks()
        self._build_status()
        self._install_wheel_guard()
        self._base_tooltips = {
            key: widget.toolTip() for key, widget in self.widgets.items()
        }
        self._refresh_auto_path_labels()

        refresh = QAction("Regenerate Script", self)
        refresh.setShortcut("F5")
        refresh.triggered.connect(lambda: self._regenerate(force=True))
        self.addAction(refresh)
        run_action = QAction("Run", self)
        run_action.setShortcut("Ctrl+Enter")
        run_action.triggered.connect(self._run)
        self.addAction(run_action)

    def _build_paths(self) -> QWidget:
        holder = QGroupBox("Input / Output", self)
        holder.setObjectName("pathPanel")
        self.path_panel = holder
        grid = QGridLayout(holder)
        grid.setContentsMargins(12, 18, 12, 10)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(8)

        self.preset_combo = QComboBox(self)
        self.preset_combo.setMinimumWidth(190)
        self.preset_combo.setToolTip(
            "Choose a built-in or user preset. Preset-owned values are locked "
            "until you click Unlock or select 'Preset'."
        )
        self.preset_combo.currentTextChanged.connect(self._on_preset)
        self.preset_unlock_button = QPushButton("Unlock", self)
        self.preset_unlock_button.setToolTip(
            "Allow editing values supplied by the selected preset."
        )
        self.preset_unlock_button.clicked.connect(self._unlock_preset_values)
        self.preset_unlock_button.hide()
        preset_row = QHBoxLayout()
        preset_row.setContentsMargins(0, 0, 0, 0)
        preset_row.addWidget(self.preset_combo, 1)
        preset_row.addWidget(self.preset_unlock_button)
        grid.addWidget(QLabel("Preset", self), 0, 0)
        grid.addLayout(preset_row, 0, 1)

        self.input_edit = PathDropEdit(self)
        self.input_edit.setPlaceholderText("Input file or batch directory")
        self.input_edit.textChanged.connect(self._on_paths)
        grid.addWidget(QLabel("Input", self), 0, 2)
        grid.addWidget(self.input_edit, 0, 3)
        input_buttons = QHBoxLayout()
        browse_in = QPushButton("Browse…", self)
        browse_in.clicked.connect(self._browse_input)
        self.input_clear_button = QPushButton("Clear", self)
        self.input_clear_button.clicked.connect(self._clear_input)
        self.input_location_button = QPushButton("Open", self)
        self.input_location_button.clicked.connect(
            lambda: self._open_location(self.input_edit.text(), False)
        )
        for button in (
            browse_in,
            self.input_clear_button,
            self.input_location_button,
        ):
            input_buttons.addWidget(button)
        grid.addLayout(input_buttons, 0, 4)

        self.batch_check = QCheckBox("Batch", self)
        self.batch_check.toggled.connect(self._on_batch)
        grid.addWidget(self.batch_check, 0, 5)
        self.batch_ext = QLineEdit("extension", self)
        self.batch_ext.setMaximumWidth(110)
        self.batch_ext.setToolTip("Batch input extension, for example mp4 or .mkv")
        self.batch_ext.textChanged.connect(self._on_paths)
        grid.addWidget(self.batch_ext, 0, 6)

        self.output_edit = PathDropEdit(self)
        self.output_edit.setPlaceholderText("Output directory (optional)")
        self.output_edit.textChanged.connect(self._on_paths)
        grid.addWidget(QLabel("Output", self), 1, 2)
        grid.addWidget(self.output_edit, 1, 3)
        output_buttons = QHBoxLayout()
        browse_out = QPushButton("Browse…", self)
        browse_out.clicked.connect(self._browse_output)
        self.output_clear_button = QPushButton("Clear", self)
        self.output_clear_button.clicked.connect(self._clear_output)
        self.output_location_button = QPushButton("Open", self)
        self.output_location_button.clicked.connect(
            lambda: self._open_location(self.output_edit.text(), True)
        )
        for button in (
            browse_out,
            self.output_clear_button,
            self.output_location_button,
        ):
            output_buttons.addWidget(button)
        grid.addLayout(output_buttons, 1, 4)

        self.preset_hint = QLabel("", self)
        self.preset_hint.setObjectName("presetHint")
        self.preset_hint.setWordWrap(True)
        self.preset_hint.hide()
        grid.addWidget(self.preset_hint, 2, 0, 1, 7)

        grid.setColumnStretch(1, 1)
        grid.setColumnStretch(3, 5)
        return holder

    def _build_docks(self) -> None:
        self.script_view = QTextEdit(self)
        self.script_view.setLineWrapMode(QTextEdit.NoWrap)
        self.script_view.setPlaceholderText("The generated FFmpeg command appears here.")
        self.script_view.textChanged.connect(self._on_script_text_changed)

        script_widget = QWidget(self)
        script_layout = QVBoxLayout(script_widget)
        script_layout.setContentsMargins(0, 0, 0, 0)
        script_buttons = QHBoxLayout()
        self.sort_button = QPushButton("Sort", self)
        self.sort_button.clicked.connect(self._toggle_script_sort)
        script_buttons.addWidget(self.sort_button)
        self.auto_sort_check = QCheckBox("Auto Sort", self)
        self.auto_sort_check.blockSignals(True)
        self.auto_sort_check.setChecked(self._script_sorted)
        self.auto_sort_check.blockSignals(False)
        self.auto_sort_check.toggled.connect(self._on_auto_sort)
        script_buttons.addWidget(self.auto_sort_check)
        self.sort_button.setText("Inline" if self._script_sorted else "Sort")
        for label, slot in (
            ("Regenerate", lambda: self._regenerate(force=True)),
            ("Copy", self._copy_script),
            ("Load…", self._load_script),
            ("Save…", self._save_script),
            ("Clear", self._clear_script),
        ):
            button = QPushButton(label, self)
            button.clicked.connect(slot)
            script_buttons.addWidget(button)
        script_buttons.addStretch(1)
        self.script_info = QLabel("Generated", self)
        script_buttons.addWidget(self.script_info)
        script_layout.addLayout(script_buttons)
        script_layout.addWidget(self.script_view, 1)

        self.script_dock = QDockWidget("Script", self)
        self.script_dock.setObjectName("scriptDock")
        self.script_dock.setWidget(script_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.script_dock)

        self.log_view = QTextEdit(self)
        self.log_view.setReadOnly(True)
        log_widget = QWidget(self)
        log_layout = QVBoxLayout(log_widget)
        log_layout.setContentsMargins(0, 0, 0, 0)
        clear_log = QPushButton("Clear Log", self)
        clear_log.clicked.connect(self.log_view.clear)
        log_layout.addWidget(clear_log)
        log_layout.addWidget(self.log_view, 1)
        self.log_dock = QDockWidget("Log", self)
        self.log_dock.setObjectName("logDock")
        self.log_dock.setWidget(log_widget)
        self.addDockWidget(Qt.RightDockWidgetArea, self.log_dock)
        self.resizeDocks(
            [self.script_dock, self.log_dock],
            [320, 380],
            Qt.Horizontal,
        )

        self.batch_list = QTableWidget(0, 2, self)
        self.batch_list.setHorizontalHeaderLabels(["File", "Status"])
        self.batch_list.verticalHeader().setVisible(False)
        self.batch_list.setEditTriggers(QAbstractItemView.NoEditTriggers)
        self.batch_list.setSelectionBehavior(QAbstractItemView.SelectRows)
        self.batch_list.horizontalHeader().setStretchLastSection(False)
        self.batch_list.horizontalHeader().setSectionResizeMode(0, QHeaderView.Stretch)
        self.batch_list.setColumnWidth(1, 90)
        self.batch_list.setToolTip("Files the batch command will visit")
        batch_widget = QWidget(self)
        batch_layout = QVBoxLayout(batch_widget)
        batch_layout.setContentsMargins(0, 0, 0, 0)
        self.batch_status = QLabel("Batch queue is empty", self)
        batch_layout.addWidget(self.batch_status)
        batch_layout.addWidget(self.batch_list, 1)
        batch_buttons = QHBoxLayout()
        refresh = QPushButton("Refresh", self)
        refresh.clicked.connect(self._refresh_batch_queue)
        reveal = QPushButton("Reveal", self)
        reveal.clicked.connect(self._reveal_batch_item)
        batch_buttons.addWidget(refresh)
        batch_buttons.addWidget(reveal)
        batch_layout.addLayout(batch_buttons)
        self.batch_dock = QDockWidget("Batch Queue", self)
        self.batch_dock.setObjectName("batchDock")
        self.batch_dock.setWidget(batch_widget)
        self.addDockWidget(Qt.BottomDockWidgetArea, self.batch_dock)
        self.tabifyDockWidget(self.script_dock, self.batch_dock)
        self.resizeDocks([self.script_dock], [260], Qt.Vertical)
        self.batch_dock.hide()

    def _build_status(self) -> None:
        status = QStatusBar(self)
        self.setStatusBar(status)
        self.status_label = QLabel("Ready", self)
        status.addWidget(self.status_label, 1)
        self.progress_bar = QProgressBar(self)
        self.progress_bar.setRange(0, 1000)
        self.progress_bar.setValue(0)
        self.progress_bar.setFormat("%p%")
        self.progress_bar.setFixedWidth(220)
        status.addPermanentWidget(self.progress_bar)
        self.cancel_button = QPushButton("Cancel", self)
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel_run)
        status.addPermanentWidget(self.cancel_button)
        self.run_button = QPushButton("Run", self)
        self.run_button.clicked.connect(self._run)
        status.addPermanentWidget(self.run_button)
        self.preview_button = QPushButton("Preview", self)
        self.preview_button.clicked.connect(self._preview)
        status.addPermanentWidget(self.preview_button)

    def _install_wheel_guard(self) -> None:
        """Install the opt-in wheel filter on every value-editing control."""

        candidates = [self.font_size_combo, *self.widgets.values()]
        for widget in candidates:
            if isinstance(widget, (QComboBox, QAbstractSpinBox)):
                widget.installEventFilter(self._wheel_guard)

    def _page(self) -> tuple[QWidget, QFormLayout]:
        page = QWidget(self)
        form = QFormLayout(page)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        return page, form

    def _scroll_form(self) -> tuple[QScrollArea, QFormLayout]:
        content = QWidget(self)
        form = QFormLayout(content)
        form.setFieldGrowthPolicy(QFormLayout.AllNonFixedFieldsGrow)
        scroll = QScrollArea(self)
        scroll.setWidgetResizable(True)
        scroll.setWidget(content)
        return scroll, form

    def _add_combo(
        self,
        form: QFormLayout,
        label: str,
        key: str,
        items_key: str,
        *,
        editable: bool = False,
        structural: bool = False,
    ) -> QComboBox:
        combo = QComboBox(self)
        combo.setEditable(editable)
        combo.addItems(_names(self.state.get(items_key)))
        self.combo_items[key] = items_key
        combo.currentTextChanged.connect(
            lambda value, k=key, s=structural: self._on_state_value(k, value, s)
        )
        form.addRow(label, combo)
        self.widgets[key] = combo
        label_widget = form.labelForField(combo)
        if label_widget is not None:
            self.widget_labels[key] = label_widget
        return combo

    def _add_edit(
        self,
        form: QFormLayout,
        label: str,
        key: str,
        *,
        structural: bool = False,
    ) -> QLineEdit:
        edit = QLineEdit(self)
        edit.textChanged.connect(
            lambda value, k=key, s=structural: self._on_state_value(k, value, s)
        )
        form.addRow(label, edit)
        self.widgets[key] = edit
        label_widget = form.labelForField(edit)
        if label_widget is not None:
            self.widget_labels[key] = label_widget
        return edit

    def _add_check(
        self,
        form: QFormLayout,
        label: str,
        key: str,
        *,
        structural: bool = False,
    ) -> QCheckBox:
        check = QCheckBox(self)
        check.toggled.connect(
            lambda checked, k=key, s=structural: self._on_state_value(k, checked, s)
        )
        form.addRow(label, check)
        self.widgets[key] = check
        label_widget = form.labelForField(check)
        if label_widget is not None:
            self.widget_labels[key] = label_widget
        return check

    def _add_spin(
        self,
        form: QFormLayout,
        label: str,
        key: str,
        minimum: int,
        maximum: int,
    ) -> QSpinBox:
        spin = QSpinBox(self)
        spin.setRange(minimum, maximum)
        spin.valueChanged.connect(lambda value, k=key: self._on_state_value(k, value))
        form.addRow(label, spin)
        self.widgets[key] = spin
        label_widget = form.labelForField(spin)
        if label_widget is not None:
            self.widget_labels[key] = label_widget
        return spin

    def _add_double_spin(
        self,
        form: QFormLayout,
        label: str,
        key: str,
        minimum: float,
        maximum: float,
    ) -> QDoubleSpinBox:
        spin = QDoubleSpinBox(self)
        spin.setRange(minimum, maximum)
        spin.setDecimals(2)
        spin.setSingleStep(0.5)
        spin.valueChanged.connect(lambda value, k=key: self._on_state_value(k, value))
        form.addRow(label, spin)
        self.widgets[key] = spin
        label_widget = form.labelForField(spin)
        if label_widget is not None:
            self.widget_labels[key] = label_widget
        return spin

    def _add_path_setting(
        self,
        form: QFormLayout,
        label: str,
        key: str,
        *,
        tool: str,
        auto: bool = True,
        save: bool = False,
    ) -> QLineEdit:
        holder = QWidget(self)
        holder_layout = QVBoxLayout(holder)
        holder_layout.setContentsMargins(0, 0, 0, 0)
        holder_layout.setSpacing(2)

        row = QHBoxLayout()
        row.setContentsMargins(0, 0, 0, 0)
        edit = QLineEdit(self)
        edit.textChanged.connect(
            lambda value, k=key: self._on_state_value(k, value)
        )
        row.addWidget(edit, 1)

        browse = QPushButton("Browse…", self)
        browse.setToolTip(
            "Select a log file" if save else f"Select the {label} executable"
        )
        browse.clicked.connect(
            lambda: self._browse_setting_path(key, tool, save)
        )
        row.addWidget(browse)

        auto_button = None
        auto_label = None
        if auto:
            auto_button = QPushButton("Auto", self)
            auto_button.setToolTip(
                "Use the bundled installation, AXIOM_FFMPEG_BIN, or PATH."
            )
            auto_button.clicked.connect(
                lambda _checked=False, k=key: self.widgets[k].setText("<auto>")
            )
            row.addWidget(auto_button)

        holder_layout.addLayout(row)
        if auto:
            auto_label = QLabel("", self)
            auto_label.setObjectName("autoPathHint")
            auto_label.setTextInteractionFlags(Qt.TextSelectableByMouse)
            auto_label.hide()
            holder_layout.addWidget(auto_label)

        form.addRow(label, holder)
        self.widgets[key] = edit
        self.path_browse_buttons[key] = browse
        self.path_tools[key] = tool
        if auto_button is not None:
            self.path_auto_buttons[key] = auto_button
        if auto_label is not None:
            self.path_auto_labels[key] = auto_label
        label_widget = form.labelForField(holder)
        if label_widget is not None:
            self.widget_labels[key] = label_widget
        return edit

    def _browse_setting_path(
        self,
        key: str,
        tool: str,
        save: bool,
    ) -> None:
        edit = self.widgets[key]
        current = edit.text().strip()
        if save:
            start = current if current and current != "<auto>" else ""
            path, _ = QFileDialog.getSaveFileName(
                self,
                "Select Log File",
                start,
                "Log files (*.log *.txt);;All files (*)",
            )
        else:
            start = ""
            if current and current != "<auto>":
                start = str(Path(current).parent)
            path, _ = QFileDialog.getOpenFileName(
                self,
                f"Select {tool or 'file'}",
                start,
                "Executables (*.exe);;All files (*)",
            )
        if path:
            edit.setText(path)

    def _refresh_auto_path_labels(self) -> None:
        for key, label in self.path_auto_labels.items():
            value = str(self.state.get(key) or "")
            edit = self.widgets.get(key)
            if value.strip() not in ("", "<auto>"):
                label.hide()
                if edit is not None:
                    edit.setToolTip("")
                continue

            resolved = resolve_tool_path(value or "<auto>", self.path_tools[key])
            text = (
                f"Auto: {resolved}"
                if resolved is not None
                else "Auto: not found (set AXIOM_FFMPEG_BIN or add it to PATH)"
            )
            label.setText(text)
            label.setToolTip(text)
            label.show()
            if edit is not None:
                edit.setToolTip(text)

    def _build_format_tab(self) -> QWidget:
        page, form = self._page()
        self._add_combo(
            form,
            "Container",
            "Format.Format_Container_SelectedItem",
            "Format.Format_Container_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Media Type",
            "Format.Format_MediaType_SelectedItem",
            "Format.Format_MediaType_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Cut",
            "Format.Format_Cut_SelectedItem",
            "Format.Format_Cut_Items",
            structural=True,
        )

        times = QGroupBox("Cut Range", self)
        time_grid = QGridLayout(times)
        time_grid.addWidget(QLabel("Start", self), 1, 0)
        time_grid.addWidget(QLabel("End", self), 2, 0)
        for column, unit in enumerate(
            ("Hours", "Minutes", "Seconds", "Milliseconds"),
            start=1,
        ):
            time_grid.addWidget(QLabel(unit, self), 0, column)
            for row, prefix in ((1, "Format_CutStart"), (2, "Format_CutEnd")):
                edit = self._add_edit(
                    QFormLayout(),
                    "",
                    f"Format.Format_{prefix}_{unit}_Text",
                )
                edit.setMaximumWidth(75)
                time_grid.addWidget(edit, row, column)
        form.addRow(times)
        self._add_edit(form, "Frame Start", "Format.Format_FrameStart_Text")
        self._add_edit(form, "Frame End", "Format.Format_FrameEnd_Text")
        return page

    def _build_video_tab(self) -> QWidget:
        tabs = QTabWidget(self)
        self.video_tabs = tabs

        encoding, form = self._scroll_form()
        self._add_combo(
            form,
            "Hardware Acceleration",
            "Video.Video_HWAccel_SelectedItem",
            "Video.Video_HWAccel_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "HW Decode",
            "Video.Video_HWAccel_Decode_SelectedItem",
            "Video.Video_HWAccel_Decode_Items",
        )
        self._add_combo(
            form,
            "HW Transcode",
            "Video.Video_HWAccel_Transcode_SelectedItem",
            "Video.Video_HWAccel_Transcode_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Codec",
            "Video.Video_Codec_SelectedItem",
            "Video.Video_Codec_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Encode Speed",
            "Video.Video_EncodeSpeed_SelectedItem",
            "Video.Video_EncodeSpeed_Items",
        )
        self._add_combo(
            form,
            "Quality",
            "Video.Video_Quality_SelectedItem",
            "Video.Video_Quality_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Pass",
            "Video.Video_Pass_SelectedItem",
            "Video.Video_Pass_Items",
            structural=True,
        )
        self._add_check(
            form,
            "VBR",
            "Video.Video_VBR_IsChecked",
            structural=True,
        )
        self._add_edit(form, "Bitrate", "Video.Video_BitRate_Text")
        self._add_edit(form, "CRF", "Video.Video_CRF_Text")
        self._add_edit(form, "Min Rate", "Video.Video_MinRate_Text")
        self._add_edit(form, "Max Rate", "Video.Video_MaxRate_Text")
        self._add_edit(form, "Buffer Size", "Video.Video_BufSize_Text")
        self._add_combo(
            form,
            "Pixel Format",
            "Video.Video_PixelFormat_SelectedItem",
            "Video.Video_PixelFormat_Items",
        )
        self._add_combo(
            form,
            "Optimize",
            "Video.Video_Optimize_SelectedItem",
            "Video.Video_Optimize_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Tune",
            "Video.Video_Optimize_Tune_SelectedItem",
            "Video.Video_Optimize_Tune_Items",
        )
        self._add_combo(
            form,
            "Profile",
            "Video.Video_Optimize_Profile_SelectedItem",
            "Video.Video_Optimize_Profile_Items",
        )
        self._add_combo(
            form,
            "Level",
            "Video.Video_Optimize_Level_SelectedItem",
            "Video.Video_Optimize_Level_Items",
        )
        tabs.addTab(encoding, "Encoding")

        size, form = self._scroll_form()
        self._add_combo(
            form,
            "Scale",
            "Video.Video_Scale_SelectedItem",
            "Video.Video_Scale_Items",
            structural=True,
        )
        self._add_edit(form, "Width", "Video.Video_Width_Text")
        self._add_edit(form, "Height", "Video.Video_Height_Text")
        self._add_combo(
            form,
            "Screen Format",
            "Video.Video_ScreenFormat_SelectedItem",
            "Video.Video_ScreenFormat_Items",
        )
        self._add_combo(
            form,
            "Aspect Ratio",
            "Video.Video_AspectRatio_SelectedItem",
            "Video.Video_AspectRatio_Items",
        )
        self._add_combo(
            form,
            "Scaling Algorithm",
            "Video.Video_ScalingAlgorithm_SelectedItem",
            "Video.Video_ScalingAlgorithm_Items",
        )
        self._add_combo(
            form,
            "Frame Rate",
            "Video.Video_FPS_SelectedItem",
            "Video.Video_FPS_Items",
            editable=True,
        )
        self._add_combo(
            form,
            "Vsync",
            "Video.Video_Vsync_SelectedItem",
            "Video.Video_Vsync_Items",
        )
        speed = self._add_combo(
            form,
            "Speed",
            "Video.Video_Speed_SelectedItem",
            "Video.Video_Speed_Items",
            editable=True,
        )
        speed.currentTextChanged.connect(self._sync_speed_text)
        self._add_edit(form, "Crop Width", "Video.Video_Crop_Width_Text")
        self._add_edit(form, "Crop Height", "Video.Video_Crop_Height_Text")
        self._add_edit(form, "Crop X", "Video.Video_Crop_X_Text")
        self._add_edit(form, "Crop Y", "Video.Video_Crop_Y_Text")
        crop_buttons = QHBoxLayout()
        self.apply_crop_button = QPushButton("Apply Crop", self)
        self.apply_crop_button.clicked.connect(self._apply_manual_crop)
        self.clear_crop_button = QPushButton("Clear Crop", self)
        self.clear_crop_button.clicked.connect(self._clear_manual_crop)
        crop_buttons.addWidget(self.apply_crop_button)
        crop_buttons.addWidget(self.clear_crop_button)
        form.addRow("Manual Crop", crop_buttons)
        tabs.addTab(size, "Size")

        color, form = self._scroll_form()
        for label, key, items_key in (
            (
                "Range",
                "Video.Video_Color_Range_SelectedItem",
                "Video.Video_Color_Range_Items",
            ),
            (
                "Space",
                "Video.Video_Color_Space_SelectedItem",
                "Video.Video_Color_Space_Items",
            ),
            (
                "Primaries",
                "Video.Video_Color_Primaries_SelectedItem",
                "Video.Video_Color_Primaries_Items",
            ),
            (
                "Transfer",
                "Video.Video_Color_TransferCharacteristics_SelectedItem",
                "Video.Video_Color_TransferCharacteristics_Items",
            ),
            (
                "Matrix",
                "Video.Video_Color_Matrix_SelectedItem",
                "Video.Video_Color_Matrix_Items",
            ),
        ):
            self._add_combo(form, label, key, items_key)
        tabs.addTab(color, "Color")
        return tabs

    def _build_audio_tab(self) -> QWidget:
        tabs = QTabWidget(self)
        self.audio_tabs = tabs
        page, form = self._scroll_form()
        self._add_combo(
            form,
            "Codec",
            "Audio.Audio_Codec_SelectedItem",
            "Audio.Audio_Codec_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Stream",
            "Audio.Audio_Stream_SelectedItem",
            "Audio.Audio_Stream_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Quality",
            "Audio.Audio_Quality_SelectedItem",
            "Audio.Audio_Quality_Items",
            structural=True,
        )
        self._add_edit(form, "Bitrate", "Audio.Audio_BitRate_Text")
        self._add_check(
            form,
            "VBR",
            "Audio.Audio_VBR_IsChecked",
            structural=True,
        )
        self._add_combo(
            form,
            "Channel",
            "Audio.Audio_Channel_SelectedItem",
            "Audio.Audio_Channel_Items",
        )
        self._add_combo(
            form,
            "Compression",
            "Audio.Audio_CompressionLevel_SelectedItem",
            "Audio.Audio_CompressionLevel_Items",
        )
        self._add_combo(
            form,
            "Sample Rate",
            "Audio.Audio_SampleRate_SelectedItem",
            "Audio.Audio_SampleRate_Items",
        )
        self._add_combo(
            form,
            "Bit Depth",
            "Audio.Audio_BitDepth_SelectedItem",
            "Audio.Audio_BitDepth_Items",
        )
        self._add_edit(form, "Volume %", "Audio.Audio_Volume_Text")
        self._add_double_spin(
            form,
            "Hard Limiter",
            "Audio.Audio_HardLimiter_Value",
            -24.0,
            0.0,
        )
        tabs.addTab(page, "Encoding")

        mux, mux_form = self._scroll_form()
        self.audio_list = QListWidget(self)
        self.audio_list.setMinimumHeight(180)
        self.audio_list.currentRowChanged.connect(self._load_audio_metadata)
        mux_form.addRow("External Audio", self.audio_list)
        self.audio_buttons = self._stream_buttons(
            mux_form,
            self.audio_list,
            self._add_audio,
            self._remove_audio,
            clear=self._clear_audio,
        )
        self._add_metadata_editor(mux_form, "audio")
        tabs.addTab(mux, "External Audio")
        return tabs

    def _build_subtitles_tab(self) -> QWidget:
        page, form = self._scroll_form()
        self._add_combo(
            form,
            "Codec",
            "Subtitle.Subtitle_Codec_SelectedItem",
            "Subtitle.Subtitle_Codec_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Stream",
            "Subtitle.Subtitle_Stream_SelectedItem",
            "Subtitle.Subtitle_Stream_Items",
        )
        self.subtitle_list = QListWidget(self)
        self.subtitle_list.setMinimumHeight(220)
        self.subtitle_list.currentRowChanged.connect(self._load_subtitle_metadata)
        form.addRow("External Files", self.subtitle_list)
        self.subtitle_buttons = self._stream_buttons(
            form,
            self.subtitle_list,
            self._add_subtitles,
            self._remove_subtitles,
            clear=self._clear_subtitles,
        )
        self._add_metadata_editor(form, "subtitle")
        return page

    def _stream_buttons(
        self,
        form: QFormLayout,
        widget: QListWidget,
        add_slot,
        remove_slot,
        *,
        clear=None,
    ) -> list[QPushButton]:
        row = QHBoxLayout()
        add = QPushButton("Add…", self)
        add.clicked.connect(add_slot)
        remove = QPushButton("Remove", self)
        remove.clicked.connect(remove_slot)
        up = QPushButton("Up", self)
        up.clicked.connect(lambda: self._move_stream(widget, -1))
        down = QPushButton("Down", self)
        down.clicked.connect(lambda: self._move_stream(widget, 1))
        buttons = [add, remove, up, down]
        for button in buttons:
            row.addWidget(button)
        if clear is not None:
            clear_button = QPushButton("Clear", self)
            clear_button.clicked.connect(clear)
            row.addWidget(clear_button)
            buttons.append(clear_button)
        form.addRow("", row)
        return buttons

    def _add_metadata_editor(self, form: QFormLayout, kind: str) -> None:
        group = "Audio" if kind == "audio" else "Subtitle"
        box = QGroupBox("Selected Track Metadata", self)
        meta_form = QFormLayout(box)
        title = QLineEdit(self)
        language = QComboBox(self)
        language.addItems(_names(self.state.get(f"{group}.{group}_Metadata_Language_Items")))
        language.setCurrentText("none")
        delay = QLineEdit(self)
        delay.setPlaceholderText("Stored per file, for example +250 or -120")
        title.textChanged.connect(lambda _value: self._save_metadata(kind))
        language.currentTextChanged.connect(lambda _value: self._save_metadata(kind))
        delay.textChanged.connect(lambda _value: self._save_metadata(kind))
        meta_form.addRow("Title", title)
        meta_form.addRow("Language", language)
        meta_form.addRow("Delay (ms)", delay)
        form.addRow(box)
        setattr(self, f"{kind}_meta_title", title)
        setattr(self, f"{kind}_meta_language", language)
        setattr(self, f"{kind}_meta_delay", delay)

    def _build_filters_tab(self) -> QWidget:
        tabs = QTabWidget(self)
        self.filter_tabs = tabs
        video, form = self._scroll_form()
        for label, key in (
            ("Drop Frames", "FilterVideo.FilterVideo_DropFrames_SelectedItem"),
            ("Deinterlace", "FilterVideo.FilterVideo_Deinterlace_SelectedItem"),
            ("Deblock", "FilterVideo.FilterVideo_Deblock_SelectedItem"),
            ("Deflicker", "FilterVideo.FilterVideo_Deflicker_SelectedItem"),
            ("Denoise", "FilterVideo.FilterVideo_Denoise_SelectedItem"),
            ("Deband", "FilterVideo.FilterVideo_Deband_SelectedItem"),
            ("Deshake", "FilterVideo.FilterVideo_Deshake_SelectedItem"),
            ("Dejudder", "FilterVideo.FilterVideo_Dejudder_SelectedItem"),
            ("Flip", "FilterVideo.FilterVideo_Flip_SelectedItem"),
            ("Rotate", "FilterVideo.FilterVideo_Rotate_SelectedItem"),
        ):
            items_key = key.replace("_SelectedItem", "_Items")
            self._add_combo(form, label, key, items_key)
        for label, key in (
            ("Brightness", "FilterVideo.FilterVideo_EQ_Brightness_Value"),
            ("Contrast", "FilterVideo.FilterVideo_EQ_Contrast_Value"),
            ("Saturation", "FilterVideo.FilterVideo_EQ_Saturation_Value"),
            ("Gamma", "FilterVideo.FilterVideo_EQ_Gamma_Value"),
        ):
            self._add_spin(form, label, key, -100, 100)

        selective = QGroupBox("Selective Color", self)
        grid = QGridLayout(selective)
        self._add_combo(
            form,
            "Selective Color",
            "FilterVideo.FilterVideo_SelectiveColor_SelectedItem",
            "FilterVideo.FilterVideo_SelectiveColor_Items",
        )
        self._add_combo(
            form,
            "Correction",
            "FilterVideo.FilterVideo_SelectiveColor_Correction_Method_SelectedItem",
            "FilterVideo.FilterVideo_SelectiveColor_Correction_Method_Items",
        )
        for row, color in enumerate(SELECTIVE_COLORS, start=1):
            grid.addWidget(QLabel(color, self), row, 0)
            for column, channel in enumerate(("Cyan", "Magenta", "Yellow"), start=1):
                if row == 1:
                    grid.addWidget(QLabel(channel, self), 0, column)
                key = (
                    "FilterVideo.FilterVideo_SelectiveColor_"
                    f"{color}_{channel}_Value"
                )
                spin = QSpinBox(self)
                spin.setRange(-100, 100)
                spin.valueChanged.connect(
                    lambda value, k=key: self._on_state_value(k, value)
                )
                self.widgets[key] = spin
                grid.addWidget(spin, row, column)
        form.addRow(selective)
        tabs.addTab(video, "Video")

        audio, form = self._scroll_form()
        for label, key in (
            ("Lowpass", "FilterAudio.FilterAudio_Lowpass_SelectedItem"),
            ("Highpass", "FilterAudio.FilterAudio_Highpass_SelectedItem"),
            ("Headphones", "FilterAudio.FilterAudio_Headphones_SelectedItem"),
        ):
            items_key = key.replace("_SelectedItem", "_Items")
            self._add_combo(form, label, key, items_key)
        self._add_spin(
            form,
            "Contrast",
            "FilterAudio.FilterAudio_Contrast_Value",
            -100,
            100,
        )
        self._add_spin(
            form,
            "Extra Stereo",
            "FilterAudio.FilterAudio_ExtraStereo_Value",
            0,
            100,
        )
        self._add_spin(
            form,
            "Tempo",
            "FilterAudio.FilterAudio_Tempo_Value",
            1,
            500,
        )
        tabs.addTab(audio, "Audio")
        return tabs

    def _build_settings_tab(self) -> QWidget:
        tabs = QTabWidget(self)
        self.settings_tabs = tabs

        config, form = self._scroll_form()
        self._add_path_setting(
            form, "FFmpeg", "Configure.FFmpegPath_Text", tool="ffmpeg"
        )
        self._add_path_setting(
            form, "FFprobe", "Configure.FFprobePath_Text", tool="ffprobe"
        )
        self._add_path_setting(
            form, "FFplay", "Configure.FFplayPath_Text", tool="ffplay"
        )
        self._add_combo(
            form,
            "Shell",
            "Configure.Shell_SelectedItem",
            "Configure.Shell_Items",
            structural=True,
        )
        self._add_combo(
            form,
            "Priority",
            "Configure.ProcessPriority_SelectedItem",
            "Configure.ProcessPriority_Items",
        )
        self._add_combo(
            form,
            "Threads",
            "Configure.Threads_SelectedItem",
            "Configure.Threads_Items",
        )
        self._add_combo(
            form,
            "Console Title",
            "Configure.ShellTitle_SelectedItem",
            "Configure.ShellTitle_Items",
        )
        self._add_check(
            form,
            "Keep Console",
            "Main.CMDWindowKeep_IsChecked",
        )
        self._add_check(
            form,
            "External Console",
            "Main.ExternalConsole_IsChecked",
        )
        self._add_check(
            form,
            "Write Log",
            "Configure.LogCheckBox_IsChecked",
        )
        self._add_path_setting(
            form,
            "Log File",
            "Configure.LogPath_Text",
            tool="",
            auto=False,
            save=True,
        )
        tabs.addTab(config, "Config")

        files, form = self._scroll_form()
        self._add_combo(
            form,
            "Overwrite",
            "Configure.OutputOverwrite_SelectedItem",
            "Configure.OutputOverwrite_Items",
        )
        self._add_combo(
            form,
            "Filename Spacing",
            "Configure.OutputFileNameSpacing_SelectedItem",
            "Configure.OutputFileNameSpacing_Items",
        )
        self._add_combo(
            form,
            "Input Name Tokens",
            "Configure.InputFileNameTokens_SelectedItem",
            "Configure.InputFileNameTokens_Items",
        )
        self._add_edit(
            form,
            "Custom Tokens",
            "Configure.InputFileNameTokensCustom_Text",
        )
        self.token_list = QListWidget(self)
        self.token_list.setMinimumHeight(260)
        for name in OUTPUT_TOKEN_NAMES:
            item = QListWidgetItem(name)
            item.setFlags(item.flags() | Qt.ItemIsUserCheckable)
            item.setCheckState(Qt.Unchecked)
            self.token_list.addItem(item)
        self.token_list.itemChanged.connect(self._on_tokens)
        form.addRow("Output Tokens", self.token_list)
        tabs.addTab(files, "File")

        system, form = self._scroll_form()
        interface = QGroupBox("Interface", self)
        interface_form = QFormLayout(interface)
        self.font_size_combo = QComboBox(self)
        self.font_size_combo.addItems([str(value) for value in FONT_SIZE_OPTIONS])
        self.font_size_combo.setCurrentText(str(self._font_size))
        self.font_size_combo.currentTextChanged.connect(self._on_font_size)
        interface_form.addRow("Font Size", self.font_size_combo)
        self.save_workspace_check = QCheckBox("Save workspace on exit", self)
        self.save_workspace_check.setChecked(self._save_workspace_on_exit)
        self.save_workspace_check.toggled.connect(self._on_save_workspace)
        interface_form.addRow(self.save_workspace_check)
        self.wheel_adjust_check = QCheckBox(
            "Mouse wheel adjusts values", self
        )
        self.wheel_adjust_check.setToolTip(
            "Allow the mouse wheel to change combo boxes and spin boxes. "
            "Disabled by default to prevent accidental parameter changes."
        )
        self.wheel_adjust_check.setChecked(self._mouse_wheel_adjust)
        self.wheel_adjust_check.toggled.connect(
            self._on_mouse_wheel_adjust
        )
        interface_form.addRow(self.wheel_adjust_check)
        form.addRow(interface)

        save_preset = QPushButton("Save User Preset…", self)
        save_preset.clicked.connect(self._save_preset)
        delete_preset = QPushButton("Delete User Preset…", self)
        delete_preset.clicked.connect(self._delete_preset)
        save_settings = QPushButton("Save Settings", self)
        save_settings.clicked.connect(lambda: self._save_settings())
        load_settings = QPushButton("Load Settings", self)
        load_settings.clicked.connect(lambda: self._load_settings())
        form.addRow(save_preset)
        form.addRow(delete_preset)
        form.addRow(save_settings)
        form.addRow(load_settings)
        tabs.addTab(system, "System")
        return tabs

    # -- state binding ----------------------------------------------------
    def _load_presets(self) -> None:
        self.preset_combo.blockSignals(True)
        self.preset_combo.clear()
        self.preset_combo.addItems(self.presets.names())
        self.preset_combo.setCurrentText("Preset")
        self.preset_combo.blockSignals(False)

    def _populate_widgets(self) -> None:
        self._loading = True
        try:
            for key, widget in self.widgets.items():
                value = self.state.get(key)
                if isinstance(widget, QComboBox):
                    items = _names(self.state.get(self.combo_items[key]))
                    if [widget.itemText(i) for i in range(widget.count())] != items:
                        widget.clear()
                        widget.addItems(items)
                    widget.setCurrentText("" if value is None else str(value))
                elif isinstance(widget, QLineEdit):
                    widget.setText("" if value is None else str(value))
                elif isinstance(widget, QCheckBox):
                    widget.setChecked(bool(value))
                elif isinstance(widget, QDoubleSpinBox):
                    widget.setValue(float(value or 0.0))
                elif isinstance(widget, QSpinBox):
                    widget.setValue(int(value or 0))
            self.input_edit.setText(str(self.state.get("Main.Input_Text") or ""))
            self.output_edit.setText(str(self.state.get("Main.Output_Text") or ""))
            self.batch_check.setChecked(bool(self.state.get("Main.Batch_IsChecked")))
            self.batch_ext.setText(str(self.state.get("Main.BatchExtension_Text") or ""))
            self._metadata_loading = True
            try:
                self._populate_path_list(
                    self.audio_list,
                    self.state.values.get("_audio_paths") or [],
                )
                self._populate_path_list(
                    self.subtitle_list,
                    self.state.values.get("_subtitle_paths") or [],
                )
            finally:
                self._metadata_loading = False
            if self.audio_list.count():
                self.audio_list.setCurrentRow(0)
            if self.subtitle_list.count():
                self.subtitle_list.setCurrentRow(0)
            self._load_audio_metadata()
            self._load_subtitle_metadata()
            selected = set(
                self.state.get("Configure.OutputNaming_ListView_SelectedItems") or []
            )
            for index in range(self.token_list.count()):
                item = self.token_list.item(index)
                item.setCheckState(
                    Qt.Checked if item.text() in selected else Qt.Unchecked
                )
            self._refresh_auto_path_labels()
            self._sync_widget_states()
        finally:
            self._loading = False

    def _populate_path_list(self, widget: QListWidget, paths) -> None:
        widget.clear()
        for path in paths:
            item = QListWidgetItem(Path(str(path)).name)
            item.setToolTip(str(path))
            item.setData(Qt.UserRole, str(path))
            widget.addItem(item)

    def _sync_widget_states(self) -> None:
        # Preset locking disables widgets outside the normal ViewModel flags.
        # Re-enable first so every call starts from a clean baseline, then the
        # rules below (and the preset overlay) decide the final state.
        for widget in self.widgets.values():
            widget.setEnabled(True)
        for label in self.widget_labels.values():
            label.setEnabled(True)
        auto_sort = bool(self.state.get("Main.AutoSortScript_IsChecked"))
        if self.auto_sort_check.isChecked() != auto_sort:
            self.auto_sort_check.blockSignals(True)
            self.auto_sort_check.setChecked(auto_sort)
            self.auto_sort_check.blockSignals(False)
        for key, widget in self.widgets.items():
            flag = enabled_key(key)
            if flag and flag in self.state.values:
                widget.setEnabled(bool(self.state.get(flag)))
            if key.startswith("Format.Format_CutStart_"):
                widget.setEnabled(
                    bool(self.state.get("Format.Format_CutStart_IsEnabled"))
                )
            elif key.startswith("Format.Format_CutEnd_"):
                widget.setEnabled(
                    bool(self.state.get("Format.Format_CutEnd_IsEnabled"))
                )

        self.batch_ext.setEnabled(
            bool(self.state.get("Main.BatchExtension_IsEnabled"))
        )
        self.batch_dock.setVisible(self.batch_check.isChecked())

        audio_codec = self.state.get("Audio.Audio_Codec_SelectedItem")
        audio_mux = self.state.get("Audio.Audio_Stream_SelectedItem") == "mux"
        audio_enabled = audio_mux and audio_codec not in (None, "None", "Copy")
        for widget in [self.audio_list, *self.audio_buttons]:
            widget.setEnabled(audio_enabled)
        for widget in (
            self.audio_meta_title,
            self.audio_meta_language,
            self.audio_meta_delay,
        ):
            widget.setEnabled(audio_enabled and self.audio_list.currentRow() >= 0)

        subtitle_codec = self.state.get("Subtitle.Subtitle_Codec_SelectedItem")
        subtitle_enabled = subtitle_codec not in (None, "None", "Copy")
        for widget in [self.subtitle_list, *self.subtitle_buttons]:
            widget.setEnabled(subtitle_enabled)
        for widget in (
            self.subtitle_meta_title,
            self.subtitle_meta_language,
            self.subtitle_meta_delay,
        ):
            widget.setEnabled(
                subtitle_enabled and self.subtitle_list.currentRow() >= 0
            )

        self.token_list.setEnabled(
            bool(self.state.get("Configure.OutputNaming_ListView_IsEnabled"))
        )
        self.input_clear_button.setEnabled(
            bool(self.state.get("Main.Input_Clear_IsEnabled"))
        )
        self.input_location_button.setEnabled(
            bool(self.state.get("Main.Input_Location_IsEnabled"))
        )
        self.output_clear_button.setEnabled(
            bool(self.state.get("Main.Output_Clear_IsEnabled"))
        )
        self.output_location_button.setEnabled(
            bool(self.state.get("Main.Output_Location_IsEnabled"))
        )
        self.apply_crop_button.setEnabled(
            bool(self.state.get("Video.Video_Crop_IsEnabled"))
        )
        self.clear_crop_button.setEnabled(
            bool(self.state.get("Video.Video_Crop_IsEnabled"))
        )
        self._apply_preset_locks()

    def _apply_preset_locks(self) -> None:
        """Gray preset-owned controls and explain them on hover."""

        preset_name = str(self.state.get("Main.Preset_SelectedItem") or "Preset")
        locked = (
            self._preset_locked
            and preset_name not in ("", "Preset")
        )
        parameter_presets = active_parameter_presets(self.state)
        self.preset_unlock_button.setVisible(locked)
        if locked:
            self.preset_hint.setText(
                f"Preset '{preset_name}' fixes the grayed values. "
                "Hover over a grayed control for the reason, or click Unlock "
                "to edit the current values."
                + (
                    " Active parameter presets: "
                    + ", ".join(parameter_presets)
                    + "."
                    if parameter_presets
                    else ""
                )
            )
            self.preset_hint.show()
        elif (
            parameter_presets
            and any(
                self.state.get(key) != self._initial_parameter_values.get(key)
                for key in PARAMETER_PRESET_KEYS
            )
        ):
            self.preset_hint.setText(
                "Active parameter presets: "
                + ", ".join(parameter_presets)
                + ". Grayed fields show the reason on hover."
            )
            self.preset_hint.show()
        else:
            self.preset_hint.hide()
        for key, widget in self.widgets.items():
            base = self._base_tooltips.get(key, "")
            label = self.widget_labels.get(key)
            reason = None
            if locked and key in PRESET_LOCKED_KEYS:
                reason = preset_lock_reason(key, preset_name)
                widget.setEnabled(False)
                widget.setProperty("presetLocked", True)
            elif not widget.isEnabled():
                reason = parameter_preset_reason(self.state, key)

            if reason:
                widget.setToolTip(reason)
                widget.setProperty("axiomHint", True)
                if label is not None:
                    label.setEnabled(False)
                    label.setToolTip(reason)
            elif widget.property("axiomHint") or widget.property("presetLocked"):
                widget.setToolTip(base)
                widget.setProperty("presetLocked", False)
                widget.setProperty("axiomHint", False)
                if label is not None:
                    label.setEnabled(True)
                    label.setToolTip("")

    def _list_paths(self, widget: QListWidget) -> list[str]:
        return [
            str(widget.item(index).data(Qt.UserRole))
            for index in range(widget.count())
        ]

    def _on_state_value(self, key: str, value, structural: bool = False) -> None:
        if self._loading:
            return
        previous = self.state.get(key)
        self.state.set(key, value)
        if key in self.path_tools:
            self._refresh_auto_path_labels()
        entering_custom = (
            key == "Video.Video_Quality_SelectedItem"
            and value == "Custom"
            and previous != "Custom"
        )
        if entering_custom:
            # Entering Custom from a named quality should not inherit that
            # quality's generated rates.  Preset/workspace application bypasses
            # this path and keeps its explicit values.
            for field in ("CRF", "BitRate", "MinRate", "MaxRate", "BufSize"):
                self.state.set(f"Video.Video_{field}_Text", "")
        if structural:
            self._apply_structural_change(key)
            if entering_custom:
                # Match the original Axiom flow: Custom quality starts on the
                # CRF pass so the CRF field is usable immediately.  The pass
                # list is rebuilt by the structural change above.
                if "CRF" in _names(self.state.get("Video.Video_Pass_Items")):
                    self.state.set("Video.Video_Pass_SelectedItem", "CRF")
                    controls.encoding_pass_controls(self.state)
                    controls.video_quality_controls(self.state)
                    controls.video_bitrate_display(self.state)
            self._populate_widgets()
        self._regenerate()

    def _on_paths(self) -> None:
        if self._loading:
            return
        input_text = self.input_edit.text()
        output_text = self.output_edit.text()
        self.state.set("Main.Input_Text", input_text)
        self.state.set("Main.Output_Text", output_text)
        self.state.set("Main.BatchExtension_Text", self.batch_ext.text())
        self.state.set("Main.Input_Clear_IsEnabled", bool(input_text.strip()))
        input_dir = Path(input_text) if self.batch_check.isChecked() else Path(input_text).parent
        self.state.set(
            "Main.Input_Location_IsEnabled",
            bool(input_text.strip()) and input_dir.exists(),
        )
        self.state.set("Main.Output_Clear_IsEnabled", bool(output_text.strip()))
        self.state.set(
            "Main.Output_Location_IsEnabled",
            bool(output_text.strip()) and Path(output_text).exists(),
        )
        self._sync_widget_states()
        if self.batch_check.isChecked():
            self._refresh_batch_queue()
        self._regenerate()

    def _sync_speed_text(self, value: str) -> None:
        if self._loading:
            return
        self.state.set(
            "Video.Video_Speed_Text",
            "" if value in ("", "auto") else value,
        )
        self._regenerate()

    def _on_batch(self, checked: bool) -> None:
        if self._loading:
            return
        self.state.set("Main.Batch_IsChecked", checked)
        self.state.set("Main.BatchExtension_IsEnabled", checked)
        self._refresh_batch_queue()
        self._sync_widget_states()
        if checked:
            self.batch_dock.raise_()
        self._regenerate()

    def _on_preset(self, name: str) -> None:
        if self._loading or not name:
            return
        try:
            self.presets.apply(name, self.state)
            self.state.set("Main.Preset_SelectedItem", name)
        except KeyError:
            return
        self._preset_locked = name not in ("", "Preset")
        self._refresh_controls(full=True)
        self._populate_widgets()
        self._regenerate(force=True)
        if self._preset_locked:
            self.status_label.setText(
                f"Preset '{name}' applied. Grayed values are fixed by the "
                "preset; click Unlock to edit them."
            )
        else:
            self.status_label.setText("Preset defaults applied")

    def _unlock_preset_values(self) -> None:
        """Keep the current preset values but allow the user to edit them."""

        self._preset_locked = False
        self.preset_unlock_button.hide()
        self._sync_widget_states()
        self._regenerate()
        self.status_label.setText(
            "Preset values unlocked; edits do not modify the preset file."
        )

    def _on_tokens(self, *_args) -> None:
        if self._loading:
            return
        selected = [
            self.token_list.item(index).text()
            for index in range(self.token_list.count())
            if self.token_list.item(index).checkState() == Qt.Checked
        ]
        self.state.set("Configure.OutputNaming_ListView_SelectedItems", selected)
        self._regenerate()

    # -- control resolution ----------------------------------------------
    def _refresh_controls(self, full: bool = False) -> None:
        if full:
            resolve_controls(self.state)
            controls.hwaccel_mode_controls(self.state)
        else:
            controls.media_type_controls(self.state)
            controls.media_type_controls_selected_items(self.state)
        self._apply_scale_rules()
        self.state.flags["controlsResolved"] = True

    def _apply_structural_change(self, key: str) -> None:
        scope = structural_scope(key)
        state = self.state
        if scope == "container":
            resolve_controls(state)
            controls.hwaccel_mode_controls(state)
        elif scope == "media_type":
            controls.media_type_controls(state)
            controls.media_type_controls_selected_items(state)
            controls.cut_controls(state)
            controls.audio_stream_controls(state)
            controls.hwaccel_mode_controls(state)
        elif scope == "cut":
            controls.cut_controls(state)
        elif scope in ("video_codec", "hardware_mode", "hardware_transcode"):
            if scope == "video_codec":
                controls.change_hwaccel_transcode(state)
            elif scope == "hardware_mode":
                controls.hwaccel_mode_controls(state)
            else:
                controls.select_hwaccel_video_codec(state)
            codec = state.get("Video.Video_Codec_SelectedItem")
            if codec:
                controls.codec_controls(state, "video", str(codec))
            controls.media_type_controls(state)
            controls.encoding_pass_controls(state)
            controls.pixel_format_controls(state)
            controls.video_optimize_controls(state)
            controls.video_quality_controls(state)
            controls.video_bitrate_display(state)
        elif scope == "video_quality":
            controls.encoding_pass_controls(state)
            controls.video_quality_controls(state)
            controls.video_bitrate_display(state)
        elif scope == "video_optimize":
            controls.video_optimize_controls(state)
        elif scope == "audio_codec":
            codec = state.get("Audio.Audio_Codec_SelectedItem")
            if codec:
                controls.audio_codec_controls(state, str(codec))
            controls.media_type_controls(state)
            controls.audio_stream_controls(state)
            controls.audio_quality_controls(state)
            controls.audio_bitrate_display(state)
        elif scope == "audio_quality":
            controls.audio_quality_controls(state)
            controls.audio_bitrate_display(state)
        elif scope == "subtitle":
            codec = state.get("Subtitle.Subtitle_Codec_SelectedItem")
            if codec:
                controls.subtitle_codec_controls(state, str(codec))
            controls.media_type_controls(state)

        self._apply_scale_rules()
        state.flags["controlsResolved"] = True

    def _apply_scale_rules(self) -> None:
        scale = self.state.get("Video.Video_Scale_SelectedItem")
        custom = scale == "Custom"
        source = scale == "Source"
        self.state.set("Video.Video_Width_IsEnabled", custom)
        self.state.set("Video.Video_Height_IsEnabled", custom)
        self.state.set("Video.Video_ScalingAlgorithm_IsEnabled", not source)

    def _apply_manual_crop(self) -> None:
        if self.state.get("Video.Video_Scale_SelectedItem") != "Custom":
            QMessageBox.warning(
                self,
                "Manual Crop",
                "Set Scale to Custom before applying a manual crop.",
            )
            return
        values = []
        for key in (
            "Video.Video_Crop_Width_Text",
            "Video.Video_Crop_Height_Text",
            "Video.Video_Crop_X_Text",
            "Video.Video_Crop_Y_Text",
        ):
            text = str(self.state.get(key) or "").strip()
            try:
                values.append(int(text))
            except ValueError:
                QMessageBox.warning(
                    self,
                    "Manual Crop",
                    "Crop width, height, X and Y must all be whole numbers.",
                )
                return
        width, height, x, y = values
        if width <= 0 or height <= 0 or x < 0 or y < 0:
            QMessageBox.warning(
                self,
                "Manual Crop",
                "Width and height must be positive; X and Y cannot be negative.",
            )
            return
        width -= width % 2
        height -= height % 2
        self.state.set("_crop", f"crop={width}:{height}:{x}:{y}")
        self.state.set("Video.Video_CropClear_Text", "Clear*")
        self._regenerate()
        self.status_label.setText("Manual crop applied")

    def _clear_manual_crop(self) -> None:
        self.state.set("_crop", "")
        self.state.set("Video.Video_CropClear_Text", "Clear")
        for key in (
            "Video.Video_Crop_Width_Text",
            "Video.Video_Crop_Height_Text",
            "Video.Video_Crop_X_Text",
            "Video.Video_Crop_Y_Text",
        ):
            self.state.set(key, "")
        self._populate_widgets()
        self._regenerate()
        self.status_label.setText("Manual crop cleared")

    # -- script panel -----------------------------------------------------
    def _display_script(self, text: str) -> str:
        if not self._script_sorted:
            return text
        script = Script(
            text,
            shell=str(self.state.get("Configure.Shell_SelectedItem") or "CMD"),
        )
        return script.sorted_text

    def _set_script_text(self, text: str) -> None:
        self._updating_script = True
        try:
            self.script_view.setPlainText(text)
        finally:
            self._updating_script = False

    def _on_script_text_changed(self) -> None:
        if self._updating_script:
            return
        expected = self._display_script(self._generated_text)
        self._script_dirty = self.script_view.toPlainText() != expected
        self.script_info.setText("Edited" if self._script_dirty else "Generated")

    def _regenerate(self, force: bool = False) -> str:
        self.state.set("Main.Input_Text", self.input_edit.text())
        self.state.set("Main.Output_Text", self.output_edit.text())
        self.state.set("Main.BatchExtension_Text", self.batch_ext.text())
        try:
            generated = generate_runnable(self.state)
        except Exception as error:  # keep the shell usable while editing
            generated = f"# {type(error).__name__}: {error}"
        self._generated_text = generated
        if self._script_dirty and not force and self.script_view.toPlainText().strip():
            self.script_info.setText("Custom script kept")
            return self.script_view.toPlainText()
        self._set_script_text(self._display_script(generated))
        self._script_dirty = False
        self.script_info.setText("Generated")
        return generated

    def _toggle_script_sort(self) -> None:
        if not self._script_sorted and self._script_dirty:
            QMessageBox.information(
                self,
                "Edited Script",
                "Regenerate the script before switching to Sort, or use Clear.",
            )
            return
        if self._script_sorted:
            text = _inline_text(self.script_view.toPlainText())
        else:
            script = Script(
                self.script_view.toPlainText(),
                shell=str(self.state.get("Configure.Shell_SelectedItem") or "CMD"),
            )
            text = script.sorted_text
        self._script_sorted = not self._script_sorted
        self.sort_button.setText("Inline" if self._script_sorted else "Sort")
        self._set_auto_sort_control(self._script_sorted)
        self._set_script_text(text)
        self._script_dirty = False
        self.script_info.setText("Generated")

    def _set_auto_sort_control(self, checked: bool) -> None:
        self.state.set("Main.AutoSortScript_IsChecked", checked)
        self.auto_sort_check.blockSignals(True)
        self.auto_sort_check.setChecked(checked)
        self.auto_sort_check.blockSignals(False)

    def _on_auto_sort(self, checked: bool) -> None:
        if self._loading:
            return
        self._script_sorted = checked
        self.sort_button.setText("Inline" if checked else "Sort")
        self.state.set("Main.AutoSortScript_IsChecked", checked)
        self._regenerate(force=True)

    def _copy_script(self) -> None:
        clipboard = QGuiApplication.clipboard()
        if clipboard is not None:
            clipboard.setText(self.script_view.toPlainText())
            self.status_label.setText("Script copied to the clipboard")

    def _load_script(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Load Script",
            filter="Text files (*.txt *.cmd *.ps1);;All files (*)",
        )
        if not path:
            return
        try:
            text = Path(path).read_text(encoding="utf-8")
        except OSError as error:
            QMessageBox.critical(self, "Load Script", str(error))
            return
        self._script_sorted = False
        self.sort_button.setText("Sort")
        self._set_script_text(text)
        self._script_dirty = True
        self.script_info.setText("Loaded")

    def _save_script(self) -> None:
        path, _ = QFileDialog.getSaveFileName(
            self,
            "Save Script",
            "Script.txt",
            "Text files (*.txt *.cmd *.ps1);;All files (*)",
        )
        if not path:
            return
        try:
            Path(path).write_text(
                self.script_view.toPlainText(),
                encoding="utf-8",
            )
        except OSError as error:
            QMessageBox.critical(self, "Save Script", str(error))

    def _clear_script(self) -> None:
        self._set_script_text("")
        self._script_dirty = True
        self.script_info.setText("Cleared")

    # -- external streams -------------------------------------------------
    def _refresh_batch_queue(self) -> None:
        self.batch_list.setRowCount(0)
        self._batch_current_row = -1
        if not self.batch_check.isChecked():
            self.batch_status.setText("Batch queue is empty")
            return
        files = scan_batch_files(self.input_edit.text(), self.batch_ext.text())
        self.batch_list.setRowCount(len(files))
        for row, path in enumerate(files):
            file_item = QTableWidgetItem(path.name)
            file_item.setToolTip(str(path))
            file_item.setData(Qt.UserRole, str(path))
            status_item = QTableWidgetItem("Pending")
            self.batch_list.setItem(row, 0, file_item)
            self.batch_list.setItem(row, 1, status_item)
        self.batch_status.setText(f"{len(files)} file(s) queued")

    def _set_batch_row_status(self, row: int, status: str) -> None:
        item = self.batch_list.item(row, 1)
        if item is None:
            return
        item.setText(status)
        colors = {
            "Pending": "#9aa0a6",
            "Running": "#5aa9e6",
            "Completed": "#65c18c",
            "Failed": "#e06c75",
            "Cancelled": "#d6a84b",
        }
        item.setForeground(QColor(colors.get(status, "#e6e6e6")))
        self._update_batch_summary()

    def _update_batch_summary(self) -> None:
        counts: dict[str, int] = {}
        for row in range(self.batch_list.rowCount()):
            item = self.batch_list.item(row, 1)
            status = item.text() if item is not None else "Pending"
            counts[status] = counts.get(status, 0) + 1
        if not counts:
            self.batch_status.setText("Batch queue is empty")
            return
        parts = [
            f"{status} {counts[status]}"
            for status in ("Completed", "Running", "Failed", "Cancelled", "Pending")
            if counts.get(status)
        ]
        self.batch_status.setText(" · ".join(parts))

    def _reset_batch_status(self) -> None:
        self._batch_current_row = -1
        for row in range(self.batch_list.rowCount()):
            self._set_batch_row_status(row, "Pending")

    def _batch_row_for_name(self, name: str) -> int:
        wanted = Path(name).name.casefold()
        for row in range(self.batch_list.rowCount()):
            item = self.batch_list.item(row, 0)
            if item is not None and Path(item.text()).name.casefold() == wanted:
                return row
        return -1

    def _handle_batch_log(self, line: str) -> None:
        match = BATCH_INPUT_PATTERN.search(line)
        if match:
            row = self._batch_row_for_name(match.group(1))
            if row >= 0:
                if (
                    self._batch_current_row >= 0
                    and self._batch_current_row != row
                    and self.batch_list.item(self._batch_current_row, 1).text()
                    == "Running"
                ):
                    self._set_batch_row_status(self._batch_current_row, "Completed")
                self._batch_current_row = row
                self._set_batch_row_status(row, "Running")
            return
        if self._batch_current_row < 0:
            return
        lowered = line.lower()
        if "error opening" in lowered or "conversion failed" in lowered:
            self._set_batch_row_status(self._batch_current_row, "Failed")

    def _reveal_batch_item(self) -> None:
        row = self.batch_list.currentRow()
        if row < 0 or self.batch_list.item(row, 0) is None:
            return
        path = Path(str(self.batch_list.item(row, 0).data(Qt.UserRole)))
        try:
            os.startfile(str(path.parent))  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            self.status_label.setText(str(path.parent))

    def _metadata_rows(self, kind: str, count: int) -> list[dict]:
        key = f"_{kind}_metadata"
        rows = [
            dict(row) if isinstance(row, dict) else {}
            for row in (self.state.values.get(key) or [])
        ]
        while len(rows) < count:
            rows.append({"title": "", "language": "none", "delay": ""})
        del rows[count:]
        self.state.set(key, rows)
        return rows

    def _metadata_editor(self, kind: str):
        return (
            getattr(self, f"{kind}_meta_title"),
            getattr(self, f"{kind}_meta_language"),
            getattr(self, f"{kind}_meta_delay"),
        )

    def _load_audio_metadata(self, row: int | None = None) -> None:
        self._load_metadata("audio", row)

    def _load_subtitle_metadata(self, row: int | None = None) -> None:
        self._load_metadata("subtitle", row)

    def _load_metadata(self, kind: str, row: int | None = None) -> None:
        if self._metadata_loading:
            return
        widget = self.audio_list if kind == "audio" else self.subtitle_list
        if row is None:
            row = widget.currentRow()
        rows = self._metadata_rows(kind, widget.count())
        data = rows[row] if 0 <= row < len(rows) else {}
        title, language, delay = self._metadata_editor(kind)
        self._metadata_loading = True
        try:
            title.setText(str(data.get("title") or ""))
            language.setCurrentText(str(data.get("language") or "none"))
            delay.setText(str(data.get("delay") or ""))
        finally:
            self._metadata_loading = False
        self._sync_widget_states()

    def _save_metadata(self, kind: str) -> None:
        if self._metadata_loading:
            return
        widget = self.audio_list if kind == "audio" else self.subtitle_list
        row = widget.currentRow()
        if row < 0:
            return
        rows = self._metadata_rows(kind, widget.count())
        title, language, delay = self._metadata_editor(kind)
        rows[row] = {
            "title": title.text(),
            "language": language.currentText(),
            "delay": delay.text(),
        }
        self.state.set(f"_{kind}_metadata", rows)
        self._regenerate()

    def _drop_metadata_rows(
        self,
        kind: str,
        rows_to_drop: list[int],
        count: int,
    ) -> None:
        key = f"_{kind}_metadata"
        rows = self._metadata_rows(kind, count)
        for row in sorted(rows_to_drop, reverse=True):
            if 0 <= row < len(rows):
                del rows[row]
        self.state.set(key, rows)

    def _add_audio(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "External Audio",
            filter="Audio files (*.aac *.ac3 *.flac *.m4a *.mp3 *.ogg *.opus *.wav);;All files (*)",
        )
        if not paths:
            return
        first_new = self.audio_list.count()
        current = list(self.state.values.get("_audio_paths") or [])
        current.extend(paths)
        self.state.set("_audio_paths", current)
        self._metadata_rows("audio", len(current))
        self._populate_widgets()
        self.audio_list.setCurrentRow(first_new)
        self._regenerate()

    def _remove_audio(self) -> None:
        count = self.audio_list.count()
        self._metadata_loading = True
        try:
            rows = self._remove_stream_rows(self.audio_list)
        finally:
            self._metadata_loading = False
        self._drop_metadata_rows("audio", rows, count)
        self.state.set("_audio_paths", self._list_paths(self.audio_list))
        self._populate_widgets()
        self._regenerate()

    def _clear_audio(self) -> None:
        self.state.set("_audio_paths", [])
        self.state.set("_audio_metadata", [])
        self._populate_widgets()
        self._regenerate()

    def _add_subtitles(self) -> None:
        paths, _ = QFileDialog.getOpenFileNames(
            self,
            "Subtitle Files",
            filter="Subtitles (*.srt *.ass *.ssa *.vtt);;All files (*)",
        )
        if not paths:
            return
        first_new = self.subtitle_list.count()
        current = list(self.state.values.get("_subtitle_paths") or [])
        current.extend(paths)
        self.state.set("_subtitle_paths", current)
        self._metadata_rows("subtitle", len(current))
        self._populate_widgets()
        self.subtitle_list.setCurrentRow(first_new)
        self._regenerate()

    def _remove_subtitles(self) -> None:
        count = self.subtitle_list.count()
        self._metadata_loading = True
        try:
            rows = self._remove_stream_rows(self.subtitle_list)
        finally:
            self._metadata_loading = False
        self._drop_metadata_rows("subtitle", rows, count)
        self.state.set("_subtitle_paths", self._list_paths(self.subtitle_list))
        self._populate_widgets()
        self._regenerate()

    def _clear_subtitles(self) -> None:
        self.state.set("_subtitle_paths", [])
        self.state.set("_subtitle_metadata", [])
        self._populate_widgets()
        self._regenerate()

    def _remove_stream_rows(self, widget: QListWidget) -> list[int]:
        rows = sorted(
            (index.row() for index in widget.selectedIndexes()),
            reverse=True,
        )
        if not rows and widget.currentRow() >= 0:
            rows = [widget.currentRow()]
        for row in rows:
            widget.takeItem(row)
        return rows

    def _move_stream(self, widget: QListWidget, offset: int) -> None:
        row = widget.currentRow()
        target = row + offset
        if row < 0 or target < 0 or target >= widget.count():
            return
        self._metadata_loading = True
        try:
            item = widget.takeItem(row)
            widget.insertItem(target, item)
        finally:
            self._metadata_loading = False
        widget.setCurrentRow(target)
        kind = "audio" if widget is self.audio_list else "subtitle"
        metadata = self._metadata_rows(kind, widget.count())
        moved = metadata.pop(row)
        metadata.insert(target, moved)
        self.state.set(f"_{kind}_metadata", metadata)
        if widget is self.audio_list:
            self.state.set("_audio_paths", self._list_paths(widget))
        else:
            self.state.set("_subtitle_paths", self._list_paths(widget))
        self._load_metadata(kind, target)
        self._regenerate()

    # -- presets ----------------------------------------------------------
    def _save_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Save Preset", "Preset name:")
        if not ok or not name.strip():
            return
        self.presets.save(name.strip(), self.state.to_overrides())
        self._load_presets()
        self.preset_combo.setCurrentText(name.strip())
        self.status_label.setText(f"Saved preset {name.strip()}")

    def _delete_preset(self) -> None:
        name, ok = QInputDialog.getText(self, "Delete Preset", "Preset name:")
        if not ok or not name.strip():
            return
        if self.presets.delete(name.strip()):
            self._load_presets()
            self.status_label.setText(f"Deleted preset {name.strip()}")

    # -- workspace / interface settings -----------------------------------
    def _on_font_size(self, value: str) -> None:
        if self._loading:
            return
        try:
            size = int(value)
        except (TypeError, ValueError):
            return
        self._apply_font_size(size)

    def _apply_font_size(self, size: int) -> None:
        size = max(min(int(size), max(FONT_SIZE_OPTIONS)), min(FONT_SIZE_OPTIONS))
        self._font_size = size
        app = QApplication.instance()
        if app is not None:
            font = app.font()
            font.setPointSize(size)
            app.setFont(font)
            stylesheet = app.styleSheet()
            if stylesheet:
                updated = re.sub(
                    r"font-size:\s*\d+(?:\.\d+)?pt;",
                    f"font-size: {size}pt;",
                    stylesheet,
                )
                if updated != stylesheet:
                    app.setStyleSheet(updated)
        combo = getattr(self, "font_size_combo", None)
        if combo is not None:
            combo.blockSignals(True)
            combo.setCurrentText(str(size))
            combo.blockSignals(False)

    def _on_save_workspace(self, checked: bool) -> None:
        if not self._loading:
            self._save_workspace_on_exit = checked

    def _on_mouse_wheel_adjust(self, checked: bool) -> None:
        if self._loading:
            return
        self._mouse_wheel_adjust = checked
        self._wheel_guard.enabled = checked
        self.status_label.setText(
            "Mouse-wheel value adjustment enabled"
            if checked
            else "Mouse-wheel value adjustment disabled"
        )

    def _workspace_payload(self) -> dict:
        return {
            "schema": WORKSPACE_SCHEMA,
            "geometry": bytes(self.saveGeometry().toBase64()).decode("ascii"),
            "window_state": bytes(self.saveState().toBase64()).decode("ascii"),
            "state": self.state.to_overrides(),
            "tabs": {
                "top": self.tabs.currentIndex(),
                "video": self.video_tabs.currentIndex(),
                "audio": self.audio_tabs.currentIndex(),
                "filters": self.filter_tabs.currentIndex(),
                "settings": self.settings_tabs.currentIndex(),
            },
            "script_text": self.script_view.toPlainText(),
            "script_dirty": bool(self._script_dirty),
            "script_sorted": bool(self._script_sorted),
        }

    def _restore_workspace(self, payload: object) -> bool:
        if not isinstance(payload, dict) or payload.get("schema") != WORKSPACE_SCHEMA:
            return False

        state_values = payload.get("state")
        if isinstance(state_values, dict):
            self.state = AxiomState()
            self.state.update(state_values)
            try:
                resolve_controls(self.state)
            except Exception:
                pass
            self.state.update(state_values)
            self.state.flags["controlsResolved"] = True

        self._script_sorted = bool(
            payload.get("script_sorted", self.state.get("Main.AutoSortScript_IsChecked"))
        )
        self._set_auto_sort_control(self._script_sorted)
        self.sort_button.setText("Inline" if self._script_sorted else "Sort")
        self._populate_widgets()

        preset = str(self.state.get("Main.Preset_SelectedItem") or "Preset")
        self.preset_combo.blockSignals(True)
        self.preset_combo.setCurrentText(preset)
        self.preset_combo.blockSignals(False)
        self._preset_locked = preset not in ("", "Preset")
        self._sync_widget_states()

        tabs = payload.get("tabs")
        if isinstance(tabs, dict):
            for key, widget in (
                ("top", self.tabs),
                ("video", self.video_tabs),
                ("audio", self.audio_tabs),
                ("filters", self.filter_tabs),
                ("settings", self.settings_tabs),
            ):
                try:
                    index = int(tabs.get(key, 0))
                except (TypeError, ValueError):
                    continue
                if 0 <= index < widget.count():
                    widget.setCurrentIndex(index)

        geometry = payload.get("geometry")
        if isinstance(geometry, str) and geometry:
            self.restoreGeometry(QByteArray.fromBase64(geometry.encode("ascii")))
        window_state = payload.get("window_state")
        if isinstance(window_state, str) and window_state:
            self.restoreState(QByteArray.fromBase64(window_state.encode("ascii")))

        self._regenerate(force=True)
        script_text = payload.get("script_text")
        if payload.get("script_dirty") and isinstance(script_text, str) and script_text:
            self._set_script_text(script_text)
            self._script_dirty = True
            self.script_info.setText("Edited")
        return True

    def _settings_values(self) -> dict:
        values = {key: self.state.get(key) for key in SETTINGS_KEYS}
        values[FONT_SIZE_KEY] = self._font_size
        values[SAVE_WORKSPACE_KEY] = bool(self._save_workspace_on_exit)
        values[MOUSE_WHEEL_KEY] = bool(self._mouse_wheel_adjust)
        if self._save_workspace_on_exit:
            values[WORKSPACE_KEY] = self._workspace_payload()
        return values

    def _save_settings(self, path: Path | None = None) -> Path | None:
        target_path = Path(path) if path is not None else self._settings_path
        try:
            target = Settings(self._settings_values()).save(target_path)
        except OSError as error:
            self.status_label.setText(f"Could not save settings: {error}")
            return None
        self._settings_path = target_path
        self._persist_on_close = True
        self.status_label.setText(f"Settings saved to {target}")
        return target

    def _load_settings(self, path: Path | None = None) -> Settings | None:
        target_path = Path(path) if path is not None else self._settings_path
        try:
            settings = Settings.load(target_path)
        except (OSError, ValueError) as error:
            self.status_label.setText(f"Could not load settings: {error}")
            return None
        self._settings_path = target_path
        self._persist_on_close = True
        try:
            font_size = int(settings.get(FONT_SIZE_KEY, DEFAULT_FONT_SIZE))
        except (TypeError, ValueError):
            font_size = DEFAULT_FONT_SIZE
        self._apply_font_size(font_size)
        self._mouse_wheel_adjust = bool(
            settings.get(MOUSE_WHEEL_KEY, False)
        )
        self._wheel_guard.enabled = self._mouse_wheel_adjust
        self.wheel_adjust_check.blockSignals(True)
        self.wheel_adjust_check.setChecked(self._mouse_wheel_adjust)
        self.wheel_adjust_check.blockSignals(False)
        self._save_workspace_on_exit = bool(
            settings.get(SAVE_WORKSPACE_KEY, True)
        )
        self.save_workspace_check.blockSignals(True)
        self.save_workspace_check.setChecked(self._save_workspace_on_exit)
        self.save_workspace_check.blockSignals(False)

        for key, value in settings.values.items():
            if key in self.state.values:
                self.state.set(key, value)
        self._refresh_auto_path_labels()
        self._script_sorted = bool(
            self.state.get("Main.AutoSortScript_IsChecked")
        )
        self.sort_button.setText("Inline" if self._script_sorted else "Sort")
        restored = False
        if self._save_workspace_on_exit:
            restored = self._restore_workspace(settings.get(WORKSPACE_KEY))
        if not restored:
            self._populate_widgets()
            self._regenerate(force=True)
        self.status_label.setText("Settings loaded")
        return settings

    # -- actions ----------------------------------------------------------
    def _browse_input(self) -> None:
        if self.batch_check.isChecked():
            path = QFileDialog.getExistingDirectory(self, "Input Directory")
        else:
            path, _ = QFileDialog.getOpenFileName(self, "Input File")
        if path:
            self.input_edit.setText(path)

    def _browse_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, "Output Directory")
        if path:
            self.output_edit.setText(path + os.sep)

    def _clear_input(self) -> None:
        self.input_edit.clear()

    def _clear_output(self) -> None:
        self.output_edit.clear()

    def _open_location(self, text: str, directory: bool) -> None:
        target = Path(text) if directory else Path(text).parent
        try:
            os.startfile(str(target))  # type: ignore[attr-defined]
        except (AttributeError, OSError):
            self.status_label.setText(str(target))

    def _preview(self) -> None:
        if self.batch_check.isChecked():
            QMessageBox.information(self, "Preview", "Cannot preview a batch queue.")
            return
        source = Path(self.input_edit.text())
        if not source.is_file():
            QMessageBox.warning(self, "Preview", "Choose an existing input file.")
            return
        ffplay = str(self.state.get("Configure.FFplayPath_Text") or "<auto>")
        if ffplay == "<auto>":
            ffplay = "ffplay"
        try:
            preview_async(source, ffplay)
        except OSError as error:
            QMessageBox.critical(self, "Preview", str(error))
            return
        self.status_label.setText(f"Previewing {source.name}")

    def _run_options(self) -> RunOptions:
        log_path = None
        if bool(self.state.get("Configure.LogCheckBox_IsChecked")):
            text = str(self.state.get("Configure.LogPath_Text") or "").strip()
            if text:
                log_path = Path(text)
        return RunOptions(
            shell=str(self.state.get("Configure.Shell_SelectedItem") or "CMD"),
            keep_window=bool(self.state.get("Main.CMDWindowKeep_IsChecked")),
            process_priority=str(
                self.state.get("Configure.ProcessPriority_SelectedItem") or "Default"
            ),
            window_title=self._console_title(),
            log_path=log_path,
            show_console=bool(
                self.state.get("Main.ExternalConsole_IsChecked")
            ),
        )

    def _console_title(self) -> str:
        mode = str(
            self.state.get("Configure.ShellTitle_SelectedItem") or "Disabled"
        )
        if mode in ("", "Disabled", "Custom"):
            return ""
        context = build_context(self.state)
        if mode == "Filename":
            return f"{context.input_filename}{context.output_ext}"
        if mode == "Filename+Tokens":
            return Path(context.output_path).name
        if mode == "Tokens":
            return Path(context.output_path).stem
        return ""

    def _run(self) -> None:
        if self._worker and self._worker.isRunning():
            return
        script = _inline_text(self.script_view.toPlainText())
        if not script:
            self.status_label.setText("Nothing to run")
            return

        self.log_view.clear()
        self._last_error_hint = ""
        self._cancel_event.clear()
        if self.batch_check.isChecked():
            self._reset_batch_status()
        self.progress_bar.setValue(0)
        self.run_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.status_label.setText("Running…")
        self._worker = _RunWorker(script, self._run_options(), self._cancel_event)
        self._worker.log.connect(self._on_log)
        self._worker.progress.connect(self._on_progress)
        self._worker.done.connect(self._on_run_done)
        self._worker.finished.connect(self._on_worker_finished)
        self._worker.start()

    def _on_log(self, line: str) -> None:
        self.log_view.append(line)
        if (
            "Driver does not support the required nvenc API version" in line
            or "minimum required Nvidia driver for nvenc" in line
        ):
            self._last_error_hint = (
                "NVENC driver mismatch: update the NVIDIA driver, or set "
                "Hardware Acceleration to Off and use x264/x265."
            )
        if self.batch_check.isChecked():
            self._handle_batch_log(line)

    def _on_progress(self, fraction: float, _line: str) -> None:
        self.progress_bar.setValue(max(0, min(1000, round(fraction * 1000))))

    def _cancel_run(self) -> None:
        if self._worker and self._worker.isRunning():
            self._cancel_event.set()
            self.cancel_button.setEnabled(False)
            self.status_label.setText("Cancelling…")

    def _on_run_done(self, code: int, cancelled: bool) -> None:
        self.run_button.setEnabled(True)
        self.cancel_button.setEnabled(False)
        if self.batch_check.isChecked() and self._batch_current_row >= 0:
            item = self.batch_list.item(self._batch_current_row, 1)
            if item is not None and item.text() == "Running":
                if cancelled:
                    self._set_batch_row_status(self._batch_current_row, "Cancelled")
                elif code == 0:
                    self._set_batch_row_status(self._batch_current_row, "Completed")
                else:
                    self._set_batch_row_status(self._batch_current_row, "Failed")
        if cancelled:
            self.status_label.setText("Cancelled")
        elif code == 0:
            self.progress_bar.setValue(1000)
            self.status_label.setText("Completed")
        else:
            self.status_label.setText(
                self._last_error_hint
                or f"Failed with exit code {code}"
            )
        self.log_view.append(f"\nProcess exited with code {code}")

    def _on_worker_finished(self) -> None:
        worker = self._worker
        self._worker = None
        if worker is not None:
            worker.deleteLater()

    def closeEvent(self, event: QCloseEvent) -> None:
        if self._worker and self._worker.isRunning():
            self._cancel_event.set()
            self._worker.wait(2000)
        if self._persist_on_close:
            self._save_settings(self._settings_path)
        event.accept()
