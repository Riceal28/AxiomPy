"""Process execution for ffmpeg/ffplay, including the external console behaviour."""

from __future__ import annotations

import re
import subprocess
import threading
import base64
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

TIME_PATTERN = re.compile(r"time=(\d+):(\d+):(\d+(?:\.\d+)?)")
DURATION_PATTERN = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")


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
        return (detected, None) if detected is not None and not match else None

    seconds = (
        int(match.group(1)) * 3600
        + int(match.group(2)) * 60
        + float(match.group(3))
    )
    return min(seconds / detected, 1.0), detected


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
    cancel: threading.Event | None = None,
    duration: float | None = None,
) -> int:
    """Run a generated command line, streaming output and parsing ffmpeg's progress."""
    options = options or RunOptions()
    if options.show_console:
        return _run_external(script, options, on_log, cancel)

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
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
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
                    if fraction is not None:
                        on_progress(fraction, line.rstrip("\n"))
            if cancel is not None and cancel.is_set():
                _terminate_process_tree(process)
                break
    finally:
        if log_handle:
            log_handle.close()
    return process.wait()


def _run_external(
    script: str,
    options: RunOptions,
    on_log: Callable[[str], None] | None,
    cancel: threading.Event | None,
) -> int:
    """Launch a visible console window, optionally keeping it open."""
    if on_log:
        on_log("Started external console")
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
        encoded = base64.b64encode(script.encode("utf-16-le")).decode("ascii")
        command = ["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass"]
        if options.keep_window:
            command.append("-NoExit")
        command.extend(["-EncodedCommand", encoded])
        process = subprocess.Popen(command, **popen_kwargs)
    else:
        command_line = script + (" & pause" if options.keep_window else "")
        process = subprocess.Popen(
            command_line,
            shell=True,
            executable=__import__("os").environ.get("COMSPEC", "cmd.exe"),
            **popen_kwargs,
        )

    while process.poll() is None:
        if cancel is not None and cancel.is_set():
            _terminate_process_tree(process)
            break
        time.sleep(0.2)
    return process.wait()


def preview(input_path: Path | str, ffplay: str = "ffplay") -> int:
    """Port of Preview.FFplay.Preview (simple ffplay launch)."""
    return subprocess.call([ffplay, "-i", str(input_path)])

