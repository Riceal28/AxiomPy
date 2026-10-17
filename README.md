# AxiomPy

[![CI](https://github.com/Riceal28/AxiomPy/actions/workflows/ci.yml/badge.svg)](https://github.com/Riceal28/AxiomPy/actions/workflows/ci.yml)
[![Python](https://img.shields.io/badge/python-3.9--3.13-3776AB)](https://www.python.org/)
[![PySide6](https://img.shields.io/badge/PySide6-6.9.x-41CD52)](https://doc.qt.io/qtforpython/)
[![Platform](https://img.shields.io/badge/platform-Windows%2010%2F11-0078D6)](https://www.microsoft.com/windows/)
[![License](https://img.shields.io/badge/license-GPL--3.0--or--later-blue)](LICENSE)

AxiomPy is a Windows desktop frontend for building, inspecting and running FFmpeg
commands. It is a Python/PySide6 rewrite of [Matt McManis's Axiom](https://github.com/MattMcManis/Axiom),
with a focus on a practical daily encoding workflow rather than exposing every FFmpeg
option as raw text.

![AxiomPy main window](docs/images/main-window.png)

## Highlights

- Video, audio, subtitle, filter, container and output-naming controls for common
  FFmpeg workflows.
- Software and hardware encoding paths, including x264/x265, NVENC, QSV and AMF.
- CRF, VBR, CBR, lossless, 1-pass and 2-pass modes.
- External audio/subtitle muxing, stream selection, metadata and burn-in subtitles.
- Batch queue with per-file `Pending`, `Running`, `Completed`, `Failed` and
  `Cancelled` states.
- Editable generated script, sorting, copy/save/load, progress, cancellation and
  optional external console.
- Presets, ffprobe analysis, preview, drag-and-drop input/output paths and a portable
  PyInstaller build.
- 1280x720 default layout, adjustable 8–16 pt interface font and optional restoration
  of the complete workspace on exit.

## Requirements

| Component | Requirement |
|---|---|
| Operating system | Windows 10 or Windows 11 |
| Python (source install) | Python 3.9–3.13 |
| GUI toolkit | PySide6 6.9.x |
| FFmpeg | `ffmpeg`, `ffprobe` and `ffplay` on `PATH`, configured in Settings, or bundled with a portable build |

The source code is Windows-first. The core layer is Qt-free and the platform layer
keeps POSIX hooks, but Windows is the supported release target for this version.

## Quick start

### Portable package

Download a release archive from
[Releases](https://github.com/Riceal28/AxiomPy/releases), extract it, and run:

```powershell
.\AxiomPy\AxiomPy.exe
```

The portable folder already contains FFmpeg, FFprobe and FFplay. A `config` directory
next to `AxiomPy.exe` keeps settings and presets with the application.

### From source

Clone the repository, then run from its root:

```powershell
git clone https://github.com/Riceal28/AxiomPy.git
cd AxiomPy
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
python -m axiom
```

The installed GUI launcher is also available as `axiom-gui`.

### Command line

The CLI consumes the same JSON case format as the parity harness:

```powershell
python -m axiom.cli --case tools/parity_harness/smoke_cases.json --id webm-vp8-crf-25
axiom-cli --case tools/parity_harness/control_cases.json --id ctl-mp4-x264 --print resolved
```

## Using the application

1. Choose an input file or batch directory.
2. Select a container and an optional preset.
3. Configure video, audio, subtitles and filters.
4. Review the generated command in the Script dock.
5. Run the conversion, or run the same command externally.

Input/Output is a dedicated panel. The Script and Log docks are resizable and their
layout is included in workspace snapshots.

### Hardware acceleration

Set **Video → Encoding → Hardware Acceleration** to `On` to expose hardware codec
choices. **HW Transcode** synchronizes the software/hardware codec family:

- x264 ↔ H.264 AMF / NVENC / QSV
- x265 ↔ HEVC AMF / NVENC / QSV

Hardware quality arguments follow the original Axiom tables. Encoder availability
depends on the installed GPU driver and FFmpeg build; feature detection cannot
guarantee that a driver session will open successfully.

### Workspace and interface settings

Open **Settings → System** to configure:

- **Font Size**: 8–16 pt, applied immediately to the application and stylesheet.
- **Save workspace on exit**: when enabled, AxiomPy restores window geometry, dock
  layout, active tabs, edited script and conversion parameters on the next launch.

The default window size is 1280x720. A restored workspace takes precedence over the
default size.

![AxiomPy interface settings](docs/images/settings.png)

## Configuration and data

AxiomPy uses a versioned JSON configuration instead of the legacy `axiom.conf` and INI
presets.

| Data | Location |
|---|---|
| Portable configuration | `<portable>/config/axiom.json` |
| Standard configuration | `%APPDATA%\AxiomPy\axiom.json` |
| User presets | `<config>/presets/*.json` |

The portable `config` directory takes precedence when it exists. Settings, presets and
workspace snapshots use schema version 1 and are written as UTF-8 JSON.

## Build a portable package

Install the packaging extra and point the build at a directory containing the three
FFmpeg executables:

```powershell
python -m pip install -e ".[package]"
$env:AXIOM_FFMPEG_BIN = "C:\ffmpeg\bin"
.\packaging\build.ps1
.\packaging\verify.ps1
```

`build.ps1` also accepts `-FfmpegBin` and `-Python`. If `AXIOM_FFMPEG_BIN` is omitted,
the script tries `ffmpeg.exe` from `PATH`. Output is written to `dist\AxiomPy`.

## Development

```powershell
python -m pip install -e ".[dev]"
$env:QT_QPA_PLATFORM = "offscreen"
pytest -q
```

Current validation on the development machine:

- `342 passed, 2 skipped`
- opt-in real FFmpeg conversion tests: `2 passed`
- 13 native Windows screenshot pages matched at `0.0000%`

### Parity harness

The C# oracle links the original Axiom generator/control/codec sources and produces
byte-exact golden commands. The original repository is never modified.

```powershell
$env:AXIOM_REFERENCE_SRC = "C:\src\Axiom\source\Axiom\Axiom"
python tools/parity_harness/build_harness.py
python tools/parity_harness/run_goldens.py
pytest -q
```

Building the harness additionally requires a .NET Framework 4.7.1 reference assembly
environment.

### Real conversions

```powershell
$env:AXIOM_RUN_E2E = "1"
$env:AXIOM_FFMPEG_BIN = "C:\ffmpeg\bin"
pytest tests/test_e2e_ffmpeg.py -q
```

### UI screenshot regression

```powershell
python tools/ui_snapshots.py
python tools/compare_screenshots.py tests/ui-baseline artifacts/ui-current
```

The baseline covers all six top-level tabs, relevant sub-tabs and the batch queue at
1280x720.

## Project structure

| Path | Purpose |
|---|---|
| `src/axiom/core` | Qt-free state model, argument generation, presets, config, probing and process execution |
| `src/axiom/platform` | Windows/POSIX platform abstractions |
| `src/axiom/ui` | PySide6 application, widgets and the Axiom Dark stylesheet |
| `packaging` | PyInstaller spec, portable build and startup verification |
| `tools/parity_harness` | C# reference oracle and golden-case generation |
| `tools/codegen` | Generators for defaults, codecs, controls and preset tables |
| `tests` | Unit, control-parity, golden, UI and opt-in FFmpeg tests |
| `docs` | Delivery status, UI parity notes and README images |

## Known limitations

- YouTube/yt-dlp download support is intentionally removed.
- The UI is English-only in this release; strings are centralized for future
  localization.
- The application does not bundle an installer or code-signing certificate.
- QSV/AMF encoder availability depends on the machine's GPU runtime and drivers.
- Invalid or unsupported FFmpeg options still fail in FFmpeg itself; AxiomPy reports
  the process exit code and log.

## Contributing and security

See [CONTRIBUTING.md](CONTRIBUTING.md) for development setup, test commands and pull
request expectations. Report security issues privately as described in
[SECURITY.md](SECURITY.md). Participation is governed by
[CODE_OF_CONDUCT.md](CODE_OF_CONDUCT.md).

Repository: [github.com/Riceal28/AxiomPy](https://github.com/Riceal28/AxiomPy)

## License and attribution

AxiomPy is licensed under GPL-3.0-or-later, matching the original Axiom project.
See [LICENSE](LICENSE).

This project is based on Axiom by Matt McManis and is not affiliated with the original
author. The original WPF implementation remains a separate reference project.

## 中文简介

AxiomPy 是一个基于 Python 与 PySide6 的 Windows FFmpeg 桌面前端，源自 Matt McManis
的 Axiom。它保留了常用的视频/音频/字幕/滤镜与批处理工作流，并加入硬件编码、
1280×720 默认布局、界面字体缩放和可关闭的工作区状态恢复。项目采用 GPL-3.0-or-later
许可证，构建、测试与贡献方式见上方英文文档。
