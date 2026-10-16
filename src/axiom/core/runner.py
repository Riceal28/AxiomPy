"""Process execution for ffmpeg/ffplay, including the external console behaviour."""

from __future__ import annotations

import re
import subprocess
import threading
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable, Iterable, Sequence

TIME_PATTERN = re.compile(r"time=(\d+):(\d+):(\d+\.\d+)")


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
    command = build_console_command(script, options)
    process = subprocess.Popen(
        command,
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

    log_handle = options.log_path.open("a", encoding="utf-8") if options.log_path else None
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if on_log:
                on_log(line.rstrip("\n"))
            if log_handle:
                log_handle.write(line)
            if on_progress:
                match = TIME_PATTERN.search(line)
                if match and duration:
                    seconds = int(match.group(1)) * 3600 + int(match.group(2)) * 60 + float(match.group(3))
                    on_progress(min(seconds / duration, 1.0), line.rstrip("\n"))
            if cancel is not None and cancel.is_set():
                process.terminate()
                break
    finally:
        if log_handle:
            log_handle.close()
    return process.wait()


def preview(input_path: Path | str, ffplay: str = "ffplay") -> int:
    """Port of Preview.FFplay.Preview (simple ffplay launch)."""
    return subprocess.call([ffplay, "-i", str(input_path)])

