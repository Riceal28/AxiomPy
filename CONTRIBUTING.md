# Contributing to AxiomPy

Thank you for improving AxiomPy. Bug reports, compatibility findings, documentation
updates and focused pull requests are welcome.

## Before opening an issue

- Search existing issues first.
- Include the AxiomPy version, Windows version, Python version, PySide6 version and
  FFmpeg build.
- Include the generated command or FFmpeg error text when the problem is reproducible.
- Do not paste copyrighted media or secrets. Redact local paths if necessary.

## Development setup

AxiomPy targets Windows 10/11 and Python 3.9–3.13.

Clone the repository and run from its root:

```powershell
git clone https://github.com/Riceal28/AxiomPy.git
cd AxiomPy
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev]"
$env:QT_QPA_PLATFORM = "offscreen"
pytest -q
```

Launch the desktop app with:

```powershell
python -m axiom
```

## Architecture boundaries

- `axiom.core` is pure Python and must not import Qt.
- `axiom.ui` owns widgets, layout and user interaction only.
- Generated tables live in `defaults.py`, `codecs_data.py`, `controls_data.py`,
  `containers_data.py` and `presets_data.py`; prefer the scripts under
  `tools/codegen/` over hand edits.
- The original Axiom repository is a read-only reference. Point
  `AXIOM_REFERENCE_SRC` at its `source/Axiom/Axiom` directory when rebuilding the
  parity harness or generated tables.

## Validation

Run the default suite before submitting a pull request:

```powershell
$env:QT_QPA_PLATFORM = "offscreen"
pytest -q
```

Run real FFmpeg conversions when changing command assembly or process execution:

```powershell
$env:AXIOM_RUN_E2E = "1"
$env:AXIOM_FFMPEG_BIN = "C:\ffmpeg\bin"
pytest tests/test_e2e_ffmpeg.py -q
```

When changing the UI, refresh and compare screenshots:

```powershell
python tools/ui_snapshots.py
python tools/compare_screenshots.py tests/ui-baseline artifacts/ui-current
```

## Pull requests

- Keep changes focused and explain the user-visible behavior.
- Add or update tests for bug fixes and new behavior.
- Preserve byte-compatible command generation unless the change is explicitly a
  documented deviation.
- Update `CHANGELOG.md` and documentation when behavior changes.
- Confirm that no generated build output, local config, logs, media or secrets are
  included.
