# Port status

Snapshot of the Axiom -> Python rewrite.  The original WPF sources in
`G:\Codex_workspace\Axiom` stay read-only and act as the reference implementation.

## Done

| Area | Deliverable | Verified by |
|---|---|---|
| Oracle | `tools/parity_harness` builds a headless C# console app out of the *original* generator, control and codec sources (`build_harness.py`) and emits the exact Axiom command line for a case file | runs end to end; produced complete 2-pass commands with codec args, filters and stream maps |
| Golden pipeline | `run_goldens.py` turns case files into `tests/golden/*.json`; `tests/test_parity.py` compares the Python output byte for byte | 60/60 command goldens green |
| State model | `axiom/core/defaults.py` generated from the eight ViewModel classes (508 properties/fields), including collection initialisers and `Load*Defaults`, plus `axiom/core/state.py` with the original names | `tests/test_state.py` |
| String layer | `axiom/core/text.py`: `RemoveLineBreaks`, `ReplaceLineBreaksWithSpaces`, `WrapWithQuotes`, `IsValidPath`, `IsValidFilename`, `NormalizeValue` | `tests/test_text.py` |
| Assembly | `axiom/core/assembly.py` reproduces "join with space, then delete line breaks" | `tests/test_assembly.py` |
| Settings/presets | `axiom/core/config.py`: JSON schema v1, no legacy `axiom.conf`/`.ini` | `tests/test_config.py` |
| Probing | `axiom/core/probe.py`: the same `-show_entries` queries, returned as `MediaInfo` | smoke-run against local ffmpeg 8.0.1 |
| Running | `axiom/core/runner.py`: external console wrapping (`cmd /k`, `/c`, PowerShell `-NoExit`), progress parsing, log file | manual smoke |
| CLI | `python -m axiom.cli --case <file> --id <id> --print resolved|command` - same case format as the oracle | exercised against the smoke cases |
| Codec tables | `axiom/core/codecs_data.py`, generated from the 40 `Codecs/**` files (19 video, 12 audio, 6 subtitle, 3 image) incl. per-codec `qualityPass` tables | `tests/test_codecs.py` |
| Codec runtime | `axiom/core/codecs.py`: lookups plus the `EncodingPass()` state machine (`apply_quality_pass`) | `tests/test_codecs.py` |
| Control layer (complete) | `axiom/core/controls.py`: container defaults, `MediaTypeControls`/`MediaTypeControls_SelectedItems`, `CutControls`, `AudioStreamControls`, video/audio/subtitle codec controls, pixel format, encoding pass, quality/bitrate, optimize, previous-item fallback and filter enable/reset side effects | 60-case oracle matrix in `tests/test_control_parity.py`; every control-owned key matches |
| State oracle | the harness dumps the full resolved ViewModel state next to the golden command; `control_cases.json` covers all containers, four media types, codec variants, quality/pass modes, cut and subtitle/audio branches | `tests/test_control_parity.py` (60 cases) |
| Single-file generator | `axiom/core/generate/`: path/format/chapter/stream-map helpers, video codec/encode/quality/pixel-format/optimize, audio codec/quality/channels, subtitles, 1-pass and 2-pass assembly | `tests/test_parity.py` across all 60 cases, including 2-pass, CRF, audio-only, image/sequence, cut and subtitle branches |
| Generator fixes | string item lists no longer coerced to numbers; ViewModel defaults now read from backing-field initialisers; property writes mirror the public backing field | regenerated `codecs_data.py` / `defaults.py` |
| Containers | `containers_data.py` generated from `FormatContainers.cs` (15 containers, media/codec lists) and `FormatControls.cs` (per-container defaults); codec tables are now keyed by the **combo box labels** (`"MOV Text"`, `"H264 NVENC"`, `"MPEG-2"`) instead of C# class names | `tests/test_control_parity.py` |

## Next (in this order)

1. **Full filter chain** (`Filters.Video`, `Filters.Audio`, 9-section selective colour) -
   the control-layer enable/reset state and the scale/PNG-to-JPG fragments are already
   ported; the remaining fragments need golden cases.
2. **Batch scripts** - case variables, pass-1/pass-2 batch assembly, shell wrapping and
   script sorting.
3. **Presets** - `Presets/Presets.cs` is 1642 plain `VM.*.* = value;` assignments, so a
   code generator (same approach as `gen_defaults.py`) turns it into a declarative table.
4. **Path/output tokens** (`MainWindow.OutputPath`, `TokenAppender`, `TokenRemover`,
   `FileRenamer`) - already extracted verbatim into the harness shim, so both sides can
   be diffed directly.
5. **UI** (M2): PySide6 main window with the six top-level tabs, script view, run/progress,
   log window, batch, single Axiom Dark skin.
6. **Packaging** (M3): PyInstaller onedir with bundled ffmpeg/ffprobe/ffplay.

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
* A case may carry an `afterFormat` section to simulate a user changing a codec, media
  type or quality after the container was selected; Python applies it at the same point
  in `controls.resolve()`.
* `Program.Reset()` clears the previous-item statics and `passUserSelected` between
  cases, so goldens do not depend on case order.
* `Program.ResetGeneratorStatics()` clears the generator/filter accumulators
  (`vFiltersList`, `vParamsList`, output path caches, ...) between cases; this removed
  the repeated `-vf` fragments from the original 60-case run.
* `build_harness.py` overwrites `gen_src/` in place instead of deleting it, because the
  Windows sandbox may deny recursive deletes while allowing writes.

