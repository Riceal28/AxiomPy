# Changelog

All notable changes to AxiomPy are recorded here. This project follows
[Semantic Versioning](https://semver.org/).

## [0.2.3] - 2026-10-17

### Added

- Release artifacts now include two portable archives: a full Windows package
  with FFmpeg 7.1.1 and a smaller no-FFmpeg package that uses `PATH` or Settings.
- Automatic tool-path fields now display the resolved FFmpeg/FFprobe/FFplay
  executable, with Browse and Auto buttons for manual selection.
- The Log File setting has a Browse button.
- Parameter-level presets (video quality, optimization, size and audio quality)
  contribute to disabled-control tooltips and the persistent preset hint.

### Changed

- Custom quality now preserves user-entered values through control resolution.
- Bare bitrate/rate-limit numbers are normalized to kilobits (`4500` becomes
  `4500K`); image codecs use `-q:v` and video codecs use `-b:v`.
- Selecting Custom starts on the CRF pass. Bitrate is preserved as `-b:v` and
  no longer synthesizes Max Rate/Buffer Size by itself. A supplied Max Rate is
  clamped to at least Bitrate and gets a default buffer when Buffer Size is
  empty.
- In 1-pass/2-pass Custom mode, VBR checked uses average bitrate; VBR unchecked
  now emits real CBR defaults (`-minrate`/`-maxrate` plus a buffer) when no
  explicit limits are supplied.
- Custom max-rate/buffer limits now reach software and NVENC/AMF/QSV commands;
  min-rate is used in bitrate modes, where the encoders honor it.

### Fixed

- Switching to Custom quality clears stale named-quality values once, while
  later edits and parameter changes preserve them.
- Custom CRF is no longer silently dropped, and VBR is no longer ignored.
- CRF is disabled outside the CRF pass with an explanatory tooltip; VBR is
  disabled in CRF mode because CRF is variable bitrate by definition.
- Disabled parameter rows now gray their labels as well as controls and explain
  the controlling preset or mode on hover.

## [0.2.2] - 2026-10-17

### Added

- A persistent preset hint above Input/Output, in addition to the grayed
  controls, hover reasons and Unlock action.
- Actionable status text when FFmpeg reports an NVENC API/driver mismatch.

### Changed

- Portable releases now pin FFmpeg 7.1.1 (NVENC API 13.0, NVIDIA driver
  570.00+) instead of FFmpeg 8.x (NVENC API 13.1, driver 610+).
- The release workflow downloads, checksum-verifies and version-checks the
  pinned FFmpeg archive before packaging.

## [0.2.1] - 2026-10-17

### Added

- Preset-owned values are grayed out, with a hover explanation, and can be
  unlocked without discarding the current preset values.
- An opt-in mouse-wheel value adjustment setting; it is disabled by default.

### Changed

- New installations start on the MP4 container and keep all audio streams
  selected.
- Hardware acceleration keeps the selected codec family visible and AMF quality
  uses its native QVBR options instead of an unsupported generic `-crf` flag.
- README now documents portable-folder integrity, preset locking and wheel
  behavior in English and Simplified Chinese.

### Fixed

- The Windows release package now bundles real FFmpeg binaries instead of
  Chocolatey shims. This fixes the startup error
  `..\lib\ffmpeg\tools\ffmpeg\bin\ffmpeg.exe` in the 0.2.0 archive.
- Build and verification scripts reject shim executables and smoke-test every
  bundled tool with `-version`.

## [0.2.0] - 2026-10-17

### Added

- 1280x720 default desktop layout with a dedicated Input/Output panel.
- Adjustable 8-16 pt application font size.
- Optional workspace snapshots on exit, including geometry, dock layout, tabs,
  edited script and conversion parameters.
- Hardware-acceleration control linkage and oracle-tested NVENC/QSV quality arguments.
- 1280x720 native screenshot regression baseline.

### Changed

- Input/Output controls are visually grouped into a separate panel.
- The GUI starts with the audio stream set to `all`.
- Packaging and development scripts discover FFmpeg/Python from environment variables
  or `PATH` instead of hard-coded local paths.
- Project metadata now declares PySide6, package data and GitHub-facing classifiers.
- README now supports English/Simplified Chinese switching.
- Tagged releases now build and upload a portable Windows archive plus SHA-256 checksum
  through GitHub Actions.

### Fixed

- Windows DWORD process exit codes are normalized before reaching Qt signals.
- Worker threads are released only after `QThread.finished`.
- External stream maps no longer concatenate during runnable script assembly.

## [0.1.0] - 2026-10-17

- Initial Python/PySide6 migration with parity-tested FFmpeg command generation,
  desktop workflow, batch queue, presets, settings and portable PyInstaller package.
