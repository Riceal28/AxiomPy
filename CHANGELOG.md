# Changelog

All notable changes to AxiomPy are recorded here. This project follows
[Semantic Versioning](https://semver.org/).

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
