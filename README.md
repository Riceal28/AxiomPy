# AxiomPy

Python / PySide6 rewrite of [Axiom](https://github.com/MattMcManis/Axiom), the Windows
FFmpeg GUI.  The original WPF application stays untouched next door and is used as the
reference implementation.

> Status: **M1 parity, the M2 desktop workflow and the M3 portable build are all
> runnable.**  The C# oracle drives 129 golden commands; the Python suite currently
> reports `311 passed` plus an opt-in real FFmpeg conversion.  The PySide6 app has
> the six original tabs, sub-tabs, all retained `IsEnabled` bindings, batch queue,
> external audio/subtitle files, editable/sorted scripts, built-in progress/cancel,
> settings and presets.  A PyInstaller onedir package is produced under `dist\AxiomPy`.
> See [docs/STATUS.md](docs/STATUS.md) for the narrow remaining polish list.

## Layout

| Path | Purpose |
|---|---|
| `src/axiom/core` | Pure logic: state model, argument generation, presets, config, probing, running. No Qt imports. |
| `src/axiom/platform` | Platform abstraction (paths, shells, process/window behaviour). Windows first, POSIX hooks reserved. |
| `src/axiom/ui` | PySide6 desktop UI (single Axiom Dark skin). |
| `packaging` | PyInstaller spec plus build and startup-verification scripts. |
| `tools/parity_harness` | C# console app that links the *original* generator sources and dumps golden commands. |
| `tests/golden` | Golden command lines produced by the harness. |

## Run

From source:

```powershell
$env:PYTHONPATH="G:\Codex_workspace\AxiomPy\src"
D:\python\python.exe -m axiom.ui.app
```

Portable build (no Python installation required on the target machine):

```powershell
.\dist\AxiomPy\AxiomPy.exe
```

The portable folder contains `ffmpeg.exe`, `ffprobe.exe` and `ffplay.exe` under
`_internal`.  If a `config\` directory exists beside `AxiomPy.exe`, settings and
presets are stored there; otherwise they use `%APPDATA%\AxiomPy\`.

## Build a portable package

```powershell
.\packaging\build.ps1
.\packaging\verify.ps1
```

`build.ps1` accepts `-FfmpegBin` and `-Python`.  The default FFmpeg source is
`F:\ffmpeg-8.0.1\bin`; the generated folder is `dist\AxiomPy`.

## Parity harness

The harness compiles the original Axiom generator, control and codec sources into a
headless console app (`tools/parity_harness/build_harness.py`).  It copies the sources
into `gen_src/`, extracts the WPF-bound members verbatim into a shim and stubs the few
UI dialogs.  The original repository is never modified.

```powershell
python tools/parity_harness/build_harness.py          # build the oracle
python tools/parity_harness/run_goldens.py --cases `
  tools/parity_harness/smoke_cases.json `
  tools/parity_harness/control_cases.json `
  tools/parity_harness/filter_cases.json `
  tools/parity_harness/batch_cases.json `
  tools/parity_harness/preset_cases.json `
  tools/parity_harness/output_cases.json `
  tools/parity_harness/external_cases.json            # all goldens
pytest -q                                             # unit tests + golden comparison
```

## Command line

```powershell
python -m axiom.cli --case tools/parity_harness/smoke_cases.json --id webm-vp8-crf-25
python -m axiom.ui.app
```

The CLI accepts the same case format as the harness, which keeps the parity tests
symmetric: one JSON case in, one command line out, compared byte for byte.

The real-conversion test is opt-in because it requires ffmpeg:

```powershell
$env:AXIOM_RUN_E2E="1"
pytest tests/test_e2e_ffmpeg.py -q
```

## Licence

GPL-3.0-or-later, matching the original Axiom.

