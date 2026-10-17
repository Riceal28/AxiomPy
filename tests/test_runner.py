"""Shell/console command wrapping and progress parsing."""

from axiom.core.runner import (
    RunOptions,
    build_console_command,
    normalize_exit_code,
    parse_progress,
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
    assert parse_progress("  Duration: 00:00:10.00, start: 0.000000") == (10.0, None)
    fraction, detected = parse_progress(
        "frame= 10 fps=0.0 q=28.0 size= 10kB time=00:00:05.00 bitrate=1.0kbits/s",
        10.0,
    )
    assert detected == 10.0
    assert fraction == 0.5


def test_progress_clamps_at_one():
    fraction, _ = parse_progress("time=00:00:12.00", 10.0)
    assert fraction == 1.0


def test_windows_dword_exit_codes_are_normalized():
    assert normalize_exit_code(0xFFFFFFEA) == -22
    assert normalize_exit_code(0xFFFFFFFF) == -1
    assert normalize_exit_code(0) == 0
    assert normalize_exit_code(1) == 1
