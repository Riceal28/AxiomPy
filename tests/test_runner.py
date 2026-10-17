"""Shell/console command wrapping and progress parsing."""

import base64
import os
import re
import time
from pathlib import Path

import pytest

from axiom.core import runner as runner_module
from axiom.core.runner import (
    ProgressPlan,
    RunOptions,
    _ProgressMonitor,
    build_console_command,
    inject_progress_arguments,
    normalize_exit_code,
    parse_progress,
    parse_progress_file,
    run,
)


def test_cmd_wrapping_switches_keep_window_flag():
    assert build_console_command("ffmpeg -i in out", RunOptions(shell="CMD"))[:2] == [
        "cmd.exe",
        "/c",
    ]
    assert build_console_command(
        "ffmpeg -i in out", RunOptions(shell="CMD", keep_window=True)
    )[:2] == ["cmd.exe", "/k"]


def test_powershell_wrapping_uses_no_exit_only_when_requested():
    command = build_console_command("ffmpeg -i in out", RunOptions(shell="PowerShell"))
    assert command[:2] == ["powershell.exe", "-Command"]
    assert "-NoExit" not in command

    command = build_console_command(
        "ffmpeg -i in out",
        RunOptions(shell="PowerShell", keep_window=True),
    )
    assert command[:3] == ["powershell.exe", "-NoExit", "-Command"]


def test_progress_uses_duration_from_ffmpeg_log():
    assert parse_progress("  Duration: 00:00:10.00, start: 0.000000") == (
        None,
        10.0,
    )
    fraction, detected = parse_progress(
        "frame= 10 fps=0.0 q=28.0 size= 10kB time=00:00:05.00 bitrate=1.0kbits/s",
        10.0,
    )
    assert detected == 10.0
    assert fraction == 0.5


def test_progress_clamps_at_one():
    fraction, _ = parse_progress("time=00:00:12.00", 10.0)
    assert fraction == 1.0


def test_progress_file_reports_fraction_and_completion():
    assert parse_progress_file(
        "out_time_us=2500000\nprogress=continue\n",
        10.0,
    ) == (0.25, False)
    assert parse_progress_file(
        "out_time_us=10000000\nprogress=end\n",
        10.0,
    ) == (1.0, True)


def test_progress_injection_handles_quoted_paths_and_two_pass(tmp_path):
    script = (
        '"C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe" -y -i in.mp4 out1.mkv '
        '&& ffmpeg -y -i in.mp4 out2.mp4'
    )

    injected, plan = inject_progress_arguments(
        script,
        "CMD",
        tmp_path,
        500,
    )

    assert len(plan.static_paths) == 2
    assert '"C:\\Program Files\\ffmpeg\\bin\\ffmpeg.exe" -progress "' in injected
    assert "&& ffmpeg -progress \"" in injected
    assert injected.count("-stats_period 0.5") == 2
    assert "ffprobe" not in injected


def test_progress_monitor_combines_two_pass_reports(tmp_path):
    first = tmp_path / "progress-1.txt"
    second = tmp_path / "progress-2.txt"
    first.write_text(
        "out_time_us=10000000\nprogress=end\n",
        encoding="utf-8",
    )
    second.write_text(
        "out_time_us=2500000\nprogress=continue\n",
        encoding="utf-8",
    )
    monitor = _ProgressMonitor(
        ProgressPlan(tmp_path, [first, second]),
        10.0,
        None,
        None,
        500,
    )

    assert monitor.poll() == pytest.approx(0.625)
    assert monitor.finished is False
    second.write_text(
        "out_time_us=10000000\nprogress=end\n",
        encoding="utf-8",
    )
    assert monitor.poll() == 1.0
    assert monitor.finished is True


def test_batch_progress_injection_uses_filename_scoped_reports(tmp_path):
    cmd, cmd_plan = inject_progress_arguments(
        'for %f in (*.mp4) do (ffmpeg -i "%~f" "%~nf.out.mp4")',
        "CMD",
        tmp_path,
        500,
        batch=True,
    )
    powershell, ps_plan = inject_progress_arguments(
        "foreach ($f in $files) { ffmpeg -i $fullName $outputName }",
        "PowerShell",
        tmp_path,
        500,
        batch=True,
    )

    assert "progress-%~nxf-p1.txt" in cmd
    assert "progress-$inputName-p1.txt" in powershell
    assert cmd_plan.batch is True
    assert cmd_plan.pass_count == 1
    assert ps_plan.pass_count == 1


def test_batch_progress_reports_current_file_and_total(tmp_path, monkeypatch):
    first = tmp_path / "one.mp4"
    second = tmp_path / "two.mp4"
    first.write_bytes(b"x")
    second.write_bytes(b"x")
    monkeypatch.setattr(
        runner_module,
        "probe_duration",
        lambda path, ffprobe="ffprobe": 10.0,
    )
    plan = ProgressPlan(tmp_path, batch=True, pass_count=1)
    current = []
    total = []
    monitor = _ProgressMonitor(
        plan,
        None,
        lambda fraction, name: current.append((fraction, name)),
        lambda fraction, name: total.append((fraction, name)),
        500,
        [first, second],
    )

    (tmp_path / "progress-one.mp4-p1.txt").write_text(
        "out_time_us=10000000\nprogress=end\n",
        encoding="utf-8",
    )
    assert monitor.poll() == pytest.approx(0.5)
    assert current[-1] == (1.0, "one.mp4")
    assert total[-1] == (0.5, "one.mp4")

    (tmp_path / "progress-two.mp4-p1.txt").write_text(
        "out_time_us=2500000\nprogress=continue\n",
        encoding="utf-8",
    )
    assert monitor.poll() == pytest.approx(0.625)
    assert current[-1] == (0.25, "two.mp4")
    assert total[-1] == (0.625, "two.mp4")

    (tmp_path / "progress-two.mp4-p1.txt").write_text(
        "out_time_us=10000000\nprogress=end\n",
        encoding="utf-8",
    )
    assert monitor.poll() == 1.0
    assert monitor.finished is True


def test_windows_dword_exit_codes_are_normalized():
    assert normalize_exit_code(0xFFFFFFEA) == -22
    assert normalize_exit_code(0xFFFFFFFF) == -1
    assert normalize_exit_code(0) == 0
    assert normalize_exit_code(1) == 1


@pytest.mark.skipif(os.name != "nt", reason="external console is Windows-only")
def test_external_console_returns_when_shell_keeps_window_open(
    tmp_path,
    monkeypatch,
):
    class FakePopen:
        def __init__(self, command, **kwargs):
            self.pid = 4242
            self.started = time.monotonic()
            if isinstance(command, str):
                source = command
            else:
                encoded = command[-1]
                source = base64.b64decode(encoded).decode("utf-16-le")
            marker = re.search(
                r"(?:>\"|WriteAllText\(')([^\"']*exit-code\.txt)",
                source,
            )
            assert marker is not None
            Path(marker.group(1)).write_text("7", encoding="utf-8")

        def poll(self):
            # Simulate cmd /k: the shell never exits by itself.
            if time.monotonic() - self.started > 2.0:
                return 0
            return None

        def wait(self):
            return 0

    monkeypatch.setattr(runner_module.subprocess, "Popen", FakePopen)
    logged = []
    started = time.monotonic()

    code = run(
        "ffmpeg -y -i in.mp4 out.mp4",
        RunOptions(show_console=True, keep_window=True),
        on_log=logged.append,
    )

    assert code == 7
    assert time.monotonic() - started < 1.5
    assert logged == ["Started external console"]
