# Port status

Snapshot of the Axiom -> Python rewrite.  The original WPF sources in
`G:\Codex_workspace\Axiom` stay read-only and act as the reference implementation.

## Done

| Area | Deliverable | Verified by |
|---|---|---|
| Oracle | `tools/parity_harness` builds a headless C# console app out of the *original* generator, control and codec sources (`build_harness.py`) and emits the exact Axiom command line for a case file | runs end to end; produced complete 2-pass commands with codec args, filters and stream maps |
| Golden pipeline | `run_goldens.py` turns case files into `tests/golden/*.json`; `tests/test_parity.py` compares the Python output byte for byte | pipeline green (comparison skips until the generator lands) |
| State model | `axiom/core/defaults.py` generated from the eight ViewModel classes (491 properties) plus `axiom/core/state.py` with the original names | `tests/test_state.py` |
| String layer | `axiom/core/text.py`: `RemoveLineBreaks`, `ReplaceLineBreaksWithSpaces`, `WrapWithQuotes`, `IsValidPath`, `IsValidFilename`, `NormalizeValue` | `tests/test_text.py` |
| Assembly | `axiom/core/assembly.py` reproduces "join with space, then delete line breaks" | `tests/test_assembly.py` |
| Settings/presets | `axiom/core/config.py`: JSON schema v1, no legacy `axiom.conf`/`.ini` | `tests/test_config.py` |
| Probing | `axiom/core/probe.py`: the same `-show_entries` queries, returned as `MediaInfo` | smoke-run against local ffmpeg 8.0.1 |
| Running | `axiom/core/runner.py`: external console wrapping (`cmd /k`, `/c`, PowerShell `-NoExit`), progress parsing, log file | manual smoke |
| CLI | `python -m axiom.cli --case <file> --id <id> --print resolved|command` - same case format as the oracle | exercised against the smoke cases |

## Next (in this order)

1. **Control-layer resolution** (`Controls.Format/Video/Audio/Subtitles`) - fills the VM
   with codec/quality/optimize item tables.  The harness already replays the exact call
   order (`Program.ResolveControls`), so the port has a working reference for both the
   behaviour and the call sequence.
2. **Codec tables** (`Codecs/Video|Audio|Image|Subtitle`, 40 files) - declarative data.
3. **Single-pass generator** (`_1_Pass` + `Generate.Video.*` + `Generate.Audio.*` +
   `Generate.Streams` + `Generate.Format`) until `tests/test_parity.py` passes for the
   smoke cases.
4. **2-pass / CRF / batch** assemblies.
5. **Filters** (`Filters.Video`, `Filters.Audio`, 9-section selective colour).
6. **Presets** - `Presets/Presets.cs` is 1642 plain `VM.*.* = value;` assignments, so a
   code generator (same approach as `gen_defaults.py`) turns it into a declarative table.
7. **Path/output tokens** (`MainWindow.OutputPath`, `TokenAppender`, `TokenRemover`,
   `FileRenamer`) - already extracted verbatim into the harness shim, so both sides can
   be diffed directly.
8. **UI** (M2): PySide6 main window with the six top-level tabs, script view, run/progress,
   log window, batch, single Axiom Dark skin.
9. **Packaging** (M3): PyInstaller onedir with bundled ffmpeg/ffprobe/ffplay.

## Deliberate deviations from the original

* YouTube/yt-dlp download support is removed entirely (feature dropped from scope).
* Custom skins are reduced to one (Axiom Dark); no `Theme*` XAML equivalents.
* Crop window, debug console, file properties window, built-in updater and the C++/CLI
  troubleshooter are out of scope; the crop generator stays (driven by state, not by the
  crop window).
* Settings and presets use a new JSON format; the legacy INI files are not read.
* The GUI is English and all strings live in one resource module for later localisation.

## Harness notes

* `build_harness.py` copies the original sources into `gen_src/`, replaces
  `MessageBox.Show(` with a non-blocking stub and extracts the WPF-bound members
  (`MainWindow.*`, `Controls.*`) verbatim into `MainWindow.Shim.cs`.  Anything it cannot
  place is reported; the member list is persisted in `members.json`.
* The harness needs the .NET Framework 4.7.1 reference assemblies (present on this
  machine) and builds with the installed `dotnet` SDK.
* `Program.ResolveControls()` replays the GUI's control-layer call order before
  generating, so goldens include the codec/quality tables - without it the generated
  commands are missing `-c:v`, quality and map arguments.

