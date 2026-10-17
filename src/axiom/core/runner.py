"""Process execution for ffmpeg/ffplay, including the external console behaviour."""

from __future__ import annotations

import re
import subprocess
import threading
import base64
import os
import shutil
import tempfile
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

TIME_PATTERN = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
OUT_TIME_US_PATTERN = re.compile(r"^out_time_us=(\d+)\s*$", re.MULTILINE)
OUT_TIME_PATTERN = re.compile(
    r"^out_time=(\d+):(\d+):(\d+(?:\.\d+)?)\s*$",
    re.MULTILINE,
)
PROGRESS_END_PATTERN = re.compile(r"^progress=end\s*$", re.MULTILINE)

# Match both a bare ``ffmpeg`` command and a quoted full path such as
# ``"C:\Tools\ffmpeg\bin\ffmpeg.exe"``.  ``ffprobe`` is intentionally excluded.
FFMPEG_EXE_PATTERN = re.compile(
    r"(?i)(?P<exe>"
    r'(?:"[^"\r\n]*[\\/])?ffmpeg(?:\.exe)?"'
    r'|`"[^`"\r\n]*[\\/]ffmpeg(?:\.exe)?`"'
    r"|(?<![\w\\/.-])ffmpeg(?:\.exe)?\b"
    r")"
)

DEFAULT_PROGRESS_INTERVAL_MS = 500
MIN_PROGRESS_INTERVAL_MS = 100


def normalize_exit_code(code: int) -> int:
    """Return a Windows process exit code as a signed 32-bit integer.

    ``subprocess`` exposes Windows DWORD exit codes as unsigned Python ints.
    Values such as ``0xFFFFFFEA`` therefore arrive as ``4294967274`` and
    overflow Qt's C++ ``int`` signal parameters.
    """
    if 0x80000000 <= code <= 0xFFFFFFFF:
        return code - 0x100000000
    return code


@dataclass
class RunOptions:
    """Everything the shell/console layer needs to launch a command."""

    shell: str = "CMD"  # CMD | PowerShell
    keep_window: bool = False
    process_priority: str = "Default"
    window_title: str = ""
    working_directory: Path | None = None
    log_path: Path | None = None
    extra_environment: dict[str, str] = field(default_factory=dict)
    show_console: bool = False
    progress_interval_ms: int = DEFAULT_PROGRESS_INTERVAL_MS
    batch_files: list[Path] = field(default_factory=list)
    ffprobe: str = "ffprobe"


@dataclass
class ProgressPlan:
    """Where FFmpeg writes progress for this run."""

    directory: Path
    static_paths: list[Path] = field(default_factory=list)
    batch: bool = False
    pass_count: int = 0


@dataclass
class RunReport:
    """Structured result data used by notification templates."""

    exit_code: int = -1
    cancelled: bool = False
    started_at: float = 0.0
    finished_at: float = 0.0
    duration: float | None = None
    last_file: str = ""
    last_progress: dict[str, str] = field(default_factory=dict)


def build_console_command(script: str, options: RunOptions, executable: str = "") -> list[str]:
    """Wrap a script the way the original Axiom UI opens a console window.

    ``CMD``   -> ``cmd.exe /k <script>`` (keep) or ``/c <script>``
    ``POWER`` -> ``powershell.exe -NoExit -Command <script>``
    """
    if options.shell == "PowerShell":
        args = ["powershell.exe"]
        if options.keep_window:
            args.append("-NoExit")
        args.extend(["-Command", script])
        return args
    flag = "/k" if options.keep_window else "/c"
    return ["cmd.exe", flag, script]


def parse_progress(line: str, duration: float | None = None) -> tuple[float, float | None] | None:
    """Parse one FFmpeg progress line.

    Returns ``(fraction, detected_duration)``.  FFmpeg prints the input duration
    near the start of its log, so the runner can display progress even when the
    caller did not probe the file first.
    """
    detected = duration
    if detected is None:
        match = DURATION_PATTERN.search(line)
        if match:
            detected = (
                int(match.group(1)) * 3600
                + int(match.group(2)) * 60
                + float(match.group(3))
            )

    match = TIME_PATTERN.search(line)
    if not match or not detected or detected <= 0:
        if detected is not None:
            return None, detected
        return None

    seconds = (
        int(match.group(1)) * 3600
        + int(match.group(2)) * 60
        + float(match.group(3))
    )
    return min(seconds / detected, 1.0), detected


def parse_progress_file(
    text: str,
    duration: float | None = None,
) -> tuple[float | None, bool]:
    """Read one FFmpeg ``-progress`` report.

    Returns ``(fraction, ended)``.  ``fraction`` is ``None`` until both the
    report timestamp and a positive duration are available.  ``ended`` is true
    once FFmpeg wrote its final ``progress=end`` block.
    """
    ended = bool(PROGRESS_END_PATTERN.search(text))
    seconds: float | None = None
    timestamps = list(OUT_TIME_US_PATTERN.finditer(text))
    if timestamps:
        seconds = int(timestamps[-1].group(1)) / 1_000_000.0
    else:
        clock = list(OUT_TIME_PATTERN.finditer(text))
        if clock:
            match = clock[-1]
            seconds = (
                int(match.group(1)) * 3600
                + int(match.group(2)) * 60
                + float(match.group(3))
            )
    if seconds is None or not duration or duration <= 0:
        return None, ended
    return min(seconds / duration, 1.0), ended


def parse_progress_fields(text: str) -> dict[str, str]:
    """Return the final key/value block written by FFmpeg ``-progress``."""
    fields: dict[str, str] = {}
    for line in text.splitlines():
        key, separator, value = line.partition("=")
        if separator and key.strip():
            fields[key.strip()] = value.strip()
    return fields


def inject_progress_arguments(
    script: str,
    shell: str,
    directory: Path,
    interval_ms: int = DEFAULT_PROGRESS_INTERVAL_MS,
    *,
    batch: bool = False,
) -> tuple[str, ProgressPlan]:
    """Add machine-readable progress options to every FFmpeg invocation.

    The visible console and the application log keep receiving FFmpeg's normal
    output.  The progress files only hold key/value updates, which lets the UI
    follow encoding progress even when stdout is not captured.
    """
    interval_ms = max(MIN_PROGRESS_INTERVAL_MS, int(interval_ms))
    period = interval_ms / 1000.0
    paths: list[Path] = []
    occurrences = 0

    if "-progress" in script:
        return script, ProgressPlan(directory=directory)

    def replace(match: re.Match[str]) -> str:
        nonlocal occurrences
        index = occurrences
        occurrences += 1
        if batch and shell == "PowerShell":
            path_text = (
                f"{directory.as_posix()}/progress-$inputName-p{index + 1}.txt"
            )
        elif batch:
            path_text = (
                f"{directory}\\progress-%~nxf-p{index + 1}.txt"
            )
        else:
            path = directory / f"progress-{index + 1}.txt"
            paths.append(path)
            path_text = str(path)
        return (
            match.group("exe")
            + f' -progress "{path_text}" -stats_period {period:g}'
        )

    injected = FFMPEG_EXE_PATTERN.sub(replace, script)
    if batch:
        return injected, ProgressPlan(
            directory=directory,
            batch=True,
            pass_count=occurrences,
        )
    return injected, ProgressPlan(
        directory=directory,
        static_paths=paths,
    )


def probe_duration(
    input_path: Path | str,
    ffprobe: str = "ffprobe",
) -> float | None:
    """Return the container duration in seconds, or ``None`` when unavailable."""
    try:
        completed = subprocess.run(
            [
                str(ffprobe),
                "-v",
                "error",
                "-show_entries",
                "format=duration",
                "-of",
                "default=noprint_wrappers=1:nokey=1",
                str(input_path),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=20,
            check=False,
        )
        return float(completed.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        return None


class _ProgressMonitor(threading.Thread):
    """Poll FFmpeg progress files without blocking the process reader."""

    def __init__(
        self,
        plan: ProgressPlan,
        duration: float | None,
        callback: Callable[[float, str], None] | None,
        total_callback: Callable[[float, str], None] | None,
        interval_ms: int,
        batch_files: Sequence[Path] = (),
        ffprobe: str = "ffprobe",
    ) -> None:
        super().__init__(name="axiom-progress", daemon=True)
        self.plan = plan
        self.duration = duration
        self.callback = callback
        self.total_callback = total_callback
        self.interval = max(MIN_PROGRESS_INTERVAL_MS, int(interval_ms)) / 1000.0
        self.batch_files = [Path(path) for path in batch_files]
        self.ffprobe = ffprobe
        self._stop_event = threading.Event()
        self._finished = threading.Event()
        self._last: float | None = None
        self._last_total: float | None = None
        self._last_file = ""
        self._last_total_file = ""
        self._durations: dict[str, float | None] = {}
        self._probed: set[str] = set()
        self.last_fields: dict[str, str] = {}
        self.last_file = ""
        self.last_duration: float | None = duration

    @property
    def paths(self) -> list[Path]:
        """Static single-run progress files (kept for callers and tests)."""
        return self.plan.static_paths

    @property
    def finished(self) -> bool:
        return self._finished.is_set()

    def set_duration(self, duration: float | None) -> None:
        if duration and duration > 0:
            self.duration = duration
            self.last_duration = duration

    def stop(self) -> None:
        self._stop_event.set()

    def run(self) -> None:
        while not self._stop_event.wait(self.interval):
            try:
                self.poll()
            except Exception:
                # A progress report must never take the encode down.
                continue

    def poll(self) -> float | None:
        if self.plan.batch:
            return self._poll_batch()
        return self._poll_single()

    def _poll_single(self) -> float | None:
        if not self.plan.static_paths:
            return None
        reports: list[tuple[float | None, bool]] = []
        for path in self.plan.static_paths:
            try:
                text = path.read_text(encoding="utf-8", errors="replace")
            except OSError:
                continue
            self.last_fields = parse_progress_fields(text)
            reports.append(parse_progress_file(text, self.duration))

        if not reports:
            return None

        ended = sum(1 for _, is_ended in reports if is_ended)
        if ended == len(self.plan.static_paths):
            self._finished.set()

        # Multi-pass scripts have one report per pass.  A completed pass counts
        # as a full unit while the newest active pass contributes its fraction.
        active = next(
            (
                fraction
                for fraction, is_ended in reversed(reports)
                if not is_ended and fraction is not None
            ),
            None,
        )
        if len(self.plan.static_paths) > 1:
            overall = (
                ended + (active or 0.0)
            ) / len(self.plan.static_paths)
        elif reports:
            overall = active if active is not None else (1.0 if ended else 0.0)
        else:
            return None
        overall = min(1.0, max(0.0, overall))
        if self.callback is not None and overall != self._last:
            self._last = overall
            self.callback(overall, "")
        return overall

    def _batch_progress_files(self, batch_file: Path) -> list[Path]:
        count = max(1, self.plan.pass_count)
        return [
            self.plan.directory
            / f"progress-{batch_file.name}-p{index + 1}.txt"
            for index in range(count)
        ]

    def _duration_for(self, batch_file: Path) -> float | None:
        key = str(batch_file)
        if key not in self._probed:
            self._probed.add(key)
            self._durations[key] = probe_duration(
                batch_file,
                self.ffprobe,
            )
        return self._durations.get(key) or self.duration

    def _poll_batch(self) -> float | None:
        if not self.batch_files:
            return None

        fractions: list[float] = []
        reports_for_file: list[bool] = []
        for batch_file in self.batch_files:
            texts: list[str] = []
            for path in self._batch_progress_files(batch_file):
                try:
                    texts.append(
                        path.read_text(encoding="utf-8", errors="replace")
                    )
                except OSError:
                    continue
            duration = (
                self._duration_for(batch_file) if texts else None
            )
            pass_reports: list[tuple[float | None, bool]] = []
            for text in texts:
                self.last_fields = parse_progress_fields(text)
                pass_reports.append(parse_progress_file(text, duration))

            has_report = bool(pass_reports)
            reports_for_file.append(has_report)
            pass_count = max(1, self.plan.pass_count)
            if pass_reports:
                ended = sum(1 for _, is_ended in pass_reports if is_ended)
                if ended == pass_count:
                    fraction = 1.0
                else:
                    fraction = sum(
                        value or 0.0
                        for value, _ in pass_reports
                    ) / pass_count
            else:
                fraction = 0.0
            fractions.append(min(1.0, max(0.0, fraction)))

            if has_report:
                self.last_file = batch_file.name

        if not any(reports_for_file):
            return None

        # Prefer the first file that has started but not completed; batch
        # commands visit files in queue order.  If everything finished, keep
        # the last file as the current label.
        current_index = -1
        for index, fraction in enumerate(fractions):
            if reports_for_file[index]:
                current_index = index
                current_fraction = fraction
                if fraction < 1.0:
                    break
        if current_index < 0:
            return None
        current_name = self.batch_files[current_index].name
        self.last_file = current_name
        self.last_duration = self._duration_for(
            self.batch_files[current_index]
        )
        total = sum(fractions) / len(fractions)
        if all(
            reports_for_file[index] and fractions[index] >= 1.0
            for index in range(len(fractions))
        ):
            self._finished.set()

        if (
            self.callback is not None
            and (
                current_fraction != self._last
                or current_name != self._last_file
            )
        ):
            self._last = current_fraction
            self._last_file = current_name
            self.callback(current_fraction, current_name)
        if self.total_callback is not None and (
            total != self._last_total
            or current_name != self._last_total_file
        ):
            self._last_total = total
            self._last_total_file = current_name
            self.total_callback(total, current_name)
        return total


def _terminate_process_tree(process: subprocess.Popen) -> None:
    """Stop the shell we launched and any ffmpeg child it owns."""
    if process.poll() is not None:
        return
    try:
        if __import__("os").name == "nt":
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
                check=False,
            )
        else:
            process.terminate()
    except OSError:
        process.terminate()


def run(
    script: str,
    options: RunOptions | None = None,
    on_log: Callable[[str], None] | None = None,
    on_progress: Callable[[float, str], None] | None = None,
    on_total_progress: Callable[[float, str], None] | None = None,
    cancel: threading.Event | None = None,
    duration: float | None = None,
    report: RunReport | None = None,
) -> int:
    """Run a generated command line, streaming output and parsing ffmpeg's progress."""
    options = options or RunOptions()
    started_at = time.time()
    progress_directory = Path(tempfile.mkdtemp(prefix="axiom-run-"))
    progress_script, plan = inject_progress_arguments(
        script,
        options.shell,
        progress_directory,
        options.progress_interval_ms,
        batch=bool(options.batch_files),
    )
    monitor = _ProgressMonitor(
        plan,
        duration,
        on_progress,
        on_total_progress,
        options.progress_interval_ms,
        options.batch_files,
        options.ffprobe,
    )
    if plan.static_paths or (plan.batch and options.batch_files):
        monitor.start()
    code = -1
    try:
        if options.show_console:
            code = _run_external(
                progress_script,
                options,
                on_log,
                cancel,
                progress_directory,
                monitor,
            )
        else:
            code = _run_internal(
                progress_script,
                options,
                on_log,
                on_progress,
                cancel,
                duration,
                monitor,
            )
    finally:
        try:
            monitor.poll()
        except Exception:
            pass
        monitor.stop()
        if plan.static_paths or (plan.batch and options.batch_files):
            monitor.join(timeout=1.0)
        shutil.rmtree(progress_directory, ignore_errors=True)
    if report is not None:
        report.exit_code = code
        report.cancelled = bool(cancel is not None and cancel.is_set())
        report.started_at = started_at
        report.finished_at = time.time()
        report.duration = monitor.last_duration or monitor.duration
        report.last_file = monitor.last_file
        report.last_progress = dict(monitor.last_fields)
    return code


def _run_internal(
    script: str,
    options: RunOptions,
    on_log: Callable[[str], None] | None,
    on_progress: Callable[[float, str], None] | None,
    cancel: threading.Event | None,
    duration: float | None,
    monitor: _ProgressMonitor,
) -> int:
    """Run with stdout/stderr captured for the in-app log viewer."""

    popen_kwargs = dict(
        cwd=str(options.working_directory) if options.working_directory else None,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        text=True,
        encoding="utf-8",
        errors="replace",
        bufsize=1,
        env={**__import__("os").environ, **options.extra_environment},
        creationflags=subprocess.CREATE_NO_WINDOW if hasattr(subprocess, "CREATE_NO_WINDOW") else 0,
    )
    if options.shell == "PowerShell":
        source = script
        if options.window_title:
            escaped = options.window_title.replace("'", "''")
            source = (
                f"$Host.UI.RawUI.WindowTitle = '{escaped}'; " + source
            )
        encoded = base64.b64encode(source.encode("utf-16-le")).decode("ascii")
        process = subprocess.Popen(
            [
                "powershell.exe",
                "-NoProfile",
                "-ExecutionPolicy",
                "Bypass",
                "-EncodedCommand",
                encoded,
            ],
            **popen_kwargs,
        )
    else:
        # ``cmd.exe /c`` with a list argument re-quotes embedded filter strings,
        # which corrupts commands such as ``-vf "scale=trunc(iw/2)*2:..."``.
        # Let cmd parse the original command line exactly as the script view shows.
        process = subprocess.Popen(
            script,
            shell=True,
            executable=__import__("os").environ.get("COMSPEC", "cmd.exe"),
            **popen_kwargs,
        )

    log_handle = options.log_path.open("a", encoding="utf-8") if options.log_path else None
    detected_duration = duration
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if on_log:
                on_log(line.rstrip("\n"))
            if log_handle:
                log_handle.write(line)
            if on_progress:
                parsed = parse_progress(line, detected_duration)
                if parsed:
                    fraction, found = parsed
                    if found is not None:
                        detected_duration = found
                        monitor.set_duration(found)
                    if (
                        fraction is not None
                        and not monitor.paths
                        and not monitor.plan.batch
                    ):
                        on_progress(fraction, line.rstrip("\n"))
            if cancel is not None and cancel.is_set():
                _terminate_process_tree(process)
                break
    finally:
        if log_handle:
            log_handle.close()
    return normalize_exit_code(process.wait())


def _run_external(
    script: str,
    options: RunOptions,
    on_log: Callable[[str], None] | None,
    cancel: threading.Event | None,
    work_directory: Path,
    monitor: _ProgressMonitor,
) -> int:
    """Launch a visible console window and report completion independently.

    ``cmd /k`` and ``powershell -NoExit`` intentionally stay alive after FFmpeg
    exits.  Waiting for that shell to close made the Run button hang forever, so
    the launched command writes a small exit-code file as soon as the encoding
    command finishes.  The console can remain open for inspection.
    """
    if on_log:
        on_log("Started external console")
    marker = work_directory / "exit-code.txt"
    creationflags = (
        subprocess.CREATE_NEW_CONSOLE
        if hasattr(subprocess, "CREATE_NEW_CONSOLE")
        else 0
    )
    popen_kwargs = dict(
        cwd=str(options.working_directory) if options.working_directory else None,
        env={**__import__("os").environ, **options.extra_environment},
        creationflags=creationflags,
    )
    if options.shell == "PowerShell":
        marker_text = str(marker).replace("'", "''")
        script += (
            "\n; $axiomCode = if ($null -ne $LASTEXITCODE) "
            "{ [int]$LASTEXITCODE } else { 0 }; "
            f"[System.IO.File]::WriteAllText('{marker_text}', "
            "[string]$axiomCode)"
        )
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"]
        if options.keep_window:
            command.append("-NoExit")
        command.extend(["-EncodedCommand", encoded])
        process = subprocess.Popen(command, **popen_kwargs)
    else:
        command_line = script
        if options.window_title:
            title = options.window_title.replace('"', '""')
            command_line = f'title "{title}" & {command_line}'
        command_line = (
            f"({command_line}) & "
            f'call echo %^errorlevel%>"{marker}"'
        )
        if os.name == "nt":
            comspec = os.environ.get("COMSPEC", "cmd.exe")
            flag = "/k" if options.keep_window else "/c"
            process = subprocess.Popen(
                f'"{comspec}" /d {flag} "{command_line}"',
                **popen_kwargs,
            )
        else:
            process = subprocess.Popen(
                command_line,
                shell=True,
                executable=os.environ.get("COMSPEC", "cmd.exe"),
                **popen_kwargs,
            )

    poll_interval = min(
        0.2,
        max(MIN_PROGRESS_INTERVAL_MS, options.progress_interval_ms) / 1000.0,
    )
    progress_finished_at: float | None = None
    while process.poll() is None:
        if cancel is not None and cancel.is_set():
            _terminate_process_tree(process)
            return normalize_exit_code(process.wait())
        code = _read_exit_marker(marker)
        if code is not None:
            return code
        if monitor.finished:
            # The exit marker normally follows ``progress=end`` immediately.
            # Keep this fallback for scripts that terminate the shell itself.
            if progress_finished_at is None:
                progress_finished_at = time.monotonic()
            elif time.monotonic() - progress_finished_at >= 1.0:
                return 0
        time.sleep(poll_interval)
    code = _read_exit_marker(marker)
    if code is not None:
        return code
    return normalize_exit_code(process.wait())


def _read_exit_marker(path: Path) -> int | None:
    """Read an external-console exit code, ignoring a partially written file."""
    try:
        text = path.read_text(encoding="utf-8", errors="replace").strip()
    except OSError:
        return None
    if not text:
        return None
    try:
        return normalize_exit_code(int(text))
    except ValueError:
        return None


def preview(input_path: Path | str, ffplay: str = "ffplay") -> int:
    """Port of Preview.FFplay.Preview (simple ffplay launch)."""
    return normalize_exit_code(subprocess.call([ffplay, "-i", str(input_path)]))


def preview_async(
    input_path: Path | str,
    ffplay: str = "ffplay",
) -> subprocess.Popen:
    """Launch ffplay without blocking the Qt event loop."""
    return subprocess.Popen(
        [ffplay, "-i", str(input_path)],
        stdin=subprocess.DEVNULL,
    )

