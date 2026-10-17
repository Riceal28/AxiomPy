# Changelog

All notable changes to AxiomPy are recorded here. This project follows
[Semantic Versioning](https://semver.org/).

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

### Fixed

- Windows DWORD process exit codes are normalized before reaching Qt signals.
- Worker threads are released only after `QThread.finished`.
- External stream maps no longer concatenate during runnable script assembly.

## [0.1.0] - 2026-10-17

- Initial Python/PySide6 migration with parity-tested FFmpeg command generation,
  desktop workflow, batch queue, presets, settings and portable PyInstaller package.
