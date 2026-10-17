# AxiomPy

Python / PySide6 rewrite of [Axiom](https://github.com/MattMcManis/Axiom), the Windows
FFmpeg GUI.  The original WPF application stays untouched next door and is used as the
reference implementation.

> Status: **M1 in progress.**  The C# parity harness is working and produces byte-exact
> golden command lines.  The full control layer (container/media-type/codec/cut/quality
> resolution) now matches the oracle across a 60-case matrix; the command generator is
> the next module.  See [docs/STATUS.md](docs/STATUS.md) for details.

## Layout

| Path | Purpose |
|---|---|
| `src/axiom/core` | Pure logic: state model, argument generation, presets, config, probing, running. No Qt imports. |
| `src/axiom/platform` | Platform abstraction (paths, shells, process/window behaviour). Windows first, POSIX hooks reserved. |
| `src/axiom/ui` | PySide6 desktop UI (single Axiom Dark skin). |
| `tools/parity_harness` | C# console app that links the *original* generator sources and dumps golden commands. |
| `tests/golden` | Golden command lines produced by the harness. |

## Parity harness

The harness compiles the original Axiom generator, control and codec sources into a
headless console app (`tools/parity_harness/build_harness.py`).  It copies the sources
into `gen_src/`, extracts the WPF-bound members verbatim into a shim and stubs the few
UI dialogs.  The original repository is never modified.

```powershell
python tools/parity_harness/build_harness.py          # build the oracle
python tools/parity_harness/run_goldens.py            # cases -> tests/golden/*.json
pytest -q                                             # unit tests + golden comparison
```

## Command line

```powershell
python -m axiom.cli --case tools/parity_harness/smoke_cases.json --id webm-vp8-crf-25
```

The CLI accepts the same case format as the harness, which keeps the parity tests
symmetric: one JSON case in, one command line out, compared byte for byte.

## Licence

GPL-3.0-or-later, matching the original Axiom.

