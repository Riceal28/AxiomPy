# AxiomPy

**English** | [简体中文](README.zh-CN.md)

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
  `Cancelled` states, plus current-file and total progress bars.
- Editable generated script, sorting, copy/save/load, progress, cancellation and
  optional external console.
- Optional HTTP notifications with hot-reloadable `notify.json`, custom URL,
  headers and body, selectable/renamable FFmpeg result fields, and
  enabled-parameter insertion for messages and HTTP bodies.
- Presets, ffprobe analysis, preview, drag-and-drop input/output paths and a portable
  PyInstaller build.
- 1280x720 default layout, adjustable 8–16 pt interface font and optional restoration
  of the complete workspace on exit.
- Preset-owned values are grayed out with a visible hint, hover explanations and an
  **Unlock** button that keeps the current values while allowing edits.
- Parameter-level presets such as video quality, optimization, size and audio
  quality also gray their dependent controls and explain themselves on hover.
- Custom quality supports explicit CRF, bitrate, min/max rate and buffer size;
  bare rate numbers are normalized to kilobits.
- Mouse-wheel value adjustment is available as an opt-in setting and is disabled by
  default to prevent accidental parameter changes.

## Requirements

| Component | Requirement |
|---|---|
| Operating system | Windows 10 or Windows 11 |
| Python (source install) | Python 3.9–3.13 |
| GUI toolkit | PySide6 6.9.x |
| FFmpeg | `ffmpeg`, `ffprobe` and `ffplay` on `PATH`, configured in Settings, or bundled with a portable build |

The source code is Windows-first. The core layer is Qt-free and the platform layer
keeps POSIX hooks, but Windows is the supported release target for this version.
The full portable release bundles **FFmpeg 7.1.1**, whose NVENC API 13.0 works with
NVIDIA driver 570.00 or newer. FFmpeg 8.x targets NVENC API 13.1 and requires driver
610+. A smaller no-FFmpeg archive relies on FFmpeg from `PATH` or Settings.

## Quick start

### Portable package

Download a release archive from
[Releases](https://github.com/Riceal28/AxiomPy/releases), extract it, and run:

```powershell
.\AxiomPy\AxiomPy.exe
```

Two Windows archives are published for each version:

- `AxiomPy-<version>-win64.zip` includes FFmpeg, FFprobe and FFplay. This is the
  recommended package for a self-contained setup.
- `AxiomPy-<version>-win64-noffmpeg.zip` is smaller and does not include the three
  tools. Install FFmpeg separately, put its `bin` directory on `PATH`, or select the
  executables in **Settings → Config**.

Both archives extract to an `AxiomPy` folder. A `config` directory next to
`AxiomPy.exe` keeps settings and presets with the application.

Keep the extracted folder intact: in the full package the bundled tools are stored
under `_internal`. Moving `AxiomPy.exe` away from that folder will make the bundled
FFmpeg unavailable. If you see a missing-file message such as
`..\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe`, you are running an old package that
bundled a package-manager shim instead of the real FFmpeg binaries; download release
0.2.1 or later.

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
layout is included in workspace snapshots. Closing a dock hides it; use **View** to
reopen **Script Panel**, **Log Panel** or **Batch Queue**.

New installations start with **MP4** as the container and **all** audio streams
selected. Choosing a preset locks the preset identity controls (container, codecs,
quality, stream selection and hardware path). Locked controls are disabled and show
the reason on hover; click **Unlock** to keep those values and edit them, or choose
`Preset` to return to manual defaults.

Parameter presets are treated separately from the Input/Output preset list. For
example, **Video → Encoding → Quality = High** manages CRF/bitrate/VBR fields,
**Optimize = Web** manages tune/profile/level, **Size = 1080p** manages width/height,
and **Audio → Quality = 192** manages the audio bitrate. Grayed labels and controls
explain these dependencies on hover.

### Custom quality

When **Quality** is `Custom`:

- Selecting Custom starts on the `CRF` pass, so the CRF field is usable
  immediately.
- Bare numbers in bitrate/min/max/buffer fields are treated as kilobits
  (`4500` → `4500K`).
- In the `CRF` pass, CRF sets the quality target and Bitrate is preserved as
  `-b:v`. Bitrate alone does not synthesize Max Rate or Buffer Size. x264/x265
  still prioritize CRF, so use Max Rate when you need a VBV cap.
- Max Rate is emitted only from the Max Rate field. When both Bitrate and Max
  Rate are set, Max Rate is clamped up to Bitrate if it is lower. A Max Rate
  without an explicit Buffer Size gets a default buffer of twice the cap.
- In `1 Pass` / `2 Pass`, Bitrate drives the encode. VBR checked uses average
  variable bitrate (`-b:v`); VBR unchecked uses CBR defaults
  (`-minrate`/`-maxrate` equal to Bitrate and a buffer of twice the rate) unless
  you provide your own limits.
- In CRF mode, a supplied Max Rate plus its buffer act as VBV limits. Min Rate
  applies to 1-pass/2-pass VBR/CBR and is disabled on the CRF pass because CRF
  has no minimum-bitrate target. These limits also reach NVENC/AMF/QSV quality
  arguments where the encoder supports them.
- `2 Pass` remains bitrate-based and ignores CRF, which FFmpeg cannot combine
  with two-pass encoding.
- Image codecs use `-q:v` for the Custom quality value.
- Values are preserved when pass, VBR or other controls are changed.

### Hardware acceleration

Set **Video → Encoding → Hardware Acceleration** to `On` to expose hardware codec
choices. **HW Transcode** synchronizes the software/hardware codec family:

- x264 ↔ H.264 AMF / NVENC / QSV
- x265 ↔ HEVC AMF / NVENC / QSV

Hardware quality arguments follow the original Axiom tables. Encoder availability
depends on the installed GPU driver and FFmpeg build; feature detection cannot
guarantee that a driver session will open successfully.

NVENC uses `-rc:v vbr_hq` with CRF/CQ values, QSV uses `-global_quality` with
look-ahead, and AMF uses its native `-rc qvbr -qvbr_quality_level` options. H.264 and
HEVC NVENC commands are covered by opt-in real-encoder tests. The portable build pins
FFmpeg 7.1.1 so a driver reporting NVENC API 13.0 does not fail against an FFmpeg
binary compiled for API 13.1. If the driver is older than 570.00, update it, use
x264/x265, or point Settings → FFmpeg at a compatible custom build.

### Workspace and interface settings

Open **Settings → System** to configure:

- **Font Size**: 8–16 pt, applied immediately to the application and stylesheet.
- **Save workspace on exit**: when enabled, AxiomPy restores window geometry, dock
  layout, active tabs, edited script and conversion parameters on the next launch.
- **Mouse wheel adjusts values**: disabled by default; enable it only if you want the
  wheel to change combo boxes and spin boxes without clicking them first.

The default window size is 1280x720. A restored workspace takes precedence over the
default size.

In **Settings → Config**, FFmpeg, FFprobe and FFplay rows show the path resolved by
`<auto>` underneath the field. Use **Browse…** for a manual executable, or **Auto** to
return to the bundled/`PATH` lookup. The Log File row also has **Browse…**.

![AxiomPy interface settings](docs/images/settings.png)

## Configuration and data

AxiomPy uses a versioned JSON configuration instead of the legacy `axiom.conf` and INI
presets.

| Data | Location |
|---|---|
| Source configuration | `<project>/config/axiom.json` |
| Portable configuration | `<portable>/config/axiom.json` |
| Notify configuration | `<config>/notify.json` |
| User presets | `<config>/presets/*.json` |

Configuration always lives beside the application: source runs use the repository's
`config` directory, and portable builds use `config` next to `AxiomPy.exe`. On first
launch, an existing `%APPDATA%\AxiomPy` configuration is copied into that directory
without overwriting files that are already present; the old directory is left
untouched. Settings, presets and workspace snapshots use schema version 1 and are
written as UTF-8 JSON.

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
the script tries `ffmpeg.exe` from `PATH`. It refuses to bundle small package-manager
shims or `.shim` companions, because those launch helpers do not contain FFmpeg and
fail after the package is moved. The release workflow downloads the pinned FFmpeg
7.1.1 archive, checks its SHA-256, and verifies the version before building. The build
creates `dist\AxiomPy` with FFmpeg and `dist\AxiomPy-noffmpeg` without it. Verify both
variants before publishing:

```powershell
.\packaging\verify.ps1 -Package "dist\AxiomPy"
.\packaging\verify.ps1 -Package "dist\AxiomPy-noffmpeg" -NoFfmpeg
```

The full-package verification starts each bundled tool with `-version`; both variants
start `AxiomPy.exe` for a smoke test.

## Development

```powershell
python -m pip install -e ".[dev]"
$env:QT_QPA_PLATFORM = "offscreen"
pytest -q
```

Current validation on the development machine:

- `455 passed, 9 skipped`
- opt-in real FFmpeg conversion tests: `9 passed`, including H.264/HEVC NVENC and
  Custom CRF/bitrate/CBR cases
- 15 native Windows screenshot pages matched at `0.0000%`

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
