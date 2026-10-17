# Port status

Snapshot of the Axiom -> Python rewrite.  The original WPF sources in
`G:\Codex_workspace\Axiom` stay read-only and act as the reference implementation.

## Done

| Area | Deliverable | Verified by |
|---|---|---|
| Oracle | `tools/parity_harness` builds a headless C# console app out of the *original* generator, control and codec sources (`build_harness.py`) and emits the exact Axiom command line for a case file | runs end to end; produced complete 2-pass commands with codec args, filters and stream maps |
| Golden pipeline | `run_goldens.py` turns case files into `tests/golden/*.json`; `tests/test_parity.py` compares the Python output byte for byte | 129 golden cases green; `311 passed` |
| State model | `axiom/core/defaults.py` generated from the eight ViewModel classes (508 properties/fields), including collection initialisers and `Load*Defaults`, plus `axiom/core/state.py` with the original names | `tests/test_state.py` |
| String layer | `axiom/core/text.py`: `RemoveLineBreaks`, `ReplaceLineBreaksWithSpaces`, `WrapWithQuotes`, `IsValidPath`, `IsValidFilename`, `NormalizeValue` | `tests/test_text.py` |
| Assembly | `axiom/core/assembly.py` reproduces "join with space, then delete line breaks" | `tests/test_assembly.py` |
| Settings/presets | `axiom/core/config.py`: JSON schema v1, no legacy `axiom.conf`/`.ini` | `tests/test_config.py` |
| Probing | `axiom/core/probe.py`: the same `-show_entries` queries, returned as `MediaInfo` | smoke-run against local ffmpeg 8.0.1 |
| Running | `axiom/core/runner.py`: external console wrapping (`cmd /k`, `/c`, PowerShell `-NoExit`), progress parsing, log file | manual smoke |
| CLI | `python -m axiom.cli --case <file> --id <id> --print resolved|command` - same case format as the oracle | exercised against the smoke cases |
| Codec tables | `axiom/core/codecs_data.py`, generated from the 40 `Codecs/**` files (19 video, 12 audio, 6 subtitle, 3 image) incl. per-codec `qualityPass` tables | `tests/test_codecs.py` |
| Codec runtime | `axiom/core/codecs.py`: lookups plus the `EncodingPass()` state machine (`apply_quality_pass`) | `tests/test_codecs.py` |
| Control layer (complete) | `axiom/core/controls.py`: container defaults, `MediaTypeControls`/`MediaTypeControls_SelectedItems`, `CutControls`, `AudioStreamControls`, video/audio/subtitle codec controls, pixel format, encoding pass, quality/bitrate, optimize, previous-item fallback and filter enable/reset side effects | 129-case oracle matrix in `tests/test_control_parity.py`; every control-owned key matches |
| State oracle | the harness dumps both the post-preset and final resolved ViewModel state next to the golden command | `tests/test_control_parity.py` across 129 cases |
| Single-file generator | `axiom/core/generate/pipeline.py` and fragments: path/format/chapter/stream-map helpers, video codec/encode/quality/pixel-format/optimize, audio codec/quality/channels, subtitles, 1-pass/CRF/2-pass assembly | byte-identical commands across the control and filter matrices |
| Video filters | `generate/filters_video.py`: drop frames, deinterlace, deblock, deflicker, denoise, deband, deshake, dejudder, flip, rotate, EQ and all 9 selective-colour groups; `generate/video.py` now covers the full `Size.Scale()` matrix | `filter_cases.json`, including scale presets, odd-size crops, speed, 2-pass and combined chains |
| Audio filters | `generate/filters_audio.py`: volume, hard limiter range mapping, low/high pass, contrast, extra stereo, headphones and tempo | `filter_cases.json` audio and combined-video cases |
| Batch scripts | `generate/batch.py`: CMD `for` loops, PowerShell `foreach`, Auto-bitrate ffprobe snippets, audio limiters, CRF/1-pass/2-pass and shell-specific command joining | 5 CMD/PowerShell batch goldens |
| Presets | `presets_data.py` generated from post-preset oracle snapshots; 30 built-ins plus video/audio variants of the default `Preset` row; YouTube download presets removed | 45 preset goldens and `tests/test_presets.py` |
| Output naming | `generate/naming.py`: token appender, filename spacing, collision-safe renaming and output-path derivation | `output_cases.json` covers binary/no tokens, custom output directory and spacing modes |
| External streams | external audio/subtitle mux, per-file stream maps, metadata preservation and subtitle burn filters; optional `afterControls` fixture hook mirrors user changes after codec resolution | `external_cases.json` |
| M2 desktop workflow | `axiom/ui`: six top-level tabs with Video Encoding/Size/Color, Audio Encoding/External, Filters Video/Audio and Settings Config/File/System; batch queue preview; external audio/subtitle add/remove/reorder; editable script with Sort/Inline, copy/load/save; built-in progress, cancel and optional external console; JSON settings save/load; user preset save/delete | `tests/test_ui.py`; retained XAML `IsEnabled` audit reports zero unmapped bindings |
| Control linkage | `ui/control_rules.py` maps bound fields to their ViewModel `_IsEnabled` flags; targeted structural refresh avoids resetting codec choices when quality/pass changes; custom rules cover cut start/end, scale size, crop, batch, stream lists and path buttons | `test_scale_controls_follow_custom_and_source`, `test_quality_change_keeps_selected_video_codec`, full UI suite |
| Script/runtime API | `core/script.py`: typed `Script`, inline/sorted forms, `generate_script()` and `generate_args()` while keeping `generate()` as the parity text surface; runner parses duration/progress, cancels process trees, supports hidden capture or a visible console | `test_script_model.py`, `test_runner.py`, `test_e2e_ffmpeg.py` |
| Batch/name polish | `core/batch_scan.py` scans queue files; TokenRemover corpus expanded for release tags, H.264/H.265 spellings, profiles, languages, audio formats, file sizes and custom tokens | `test_batch_scan.py`, `test_token_remover.py` |
| Portable build (M3) | `packaging/axiompy.spec`, `build.ps1` and `verify.ps1`; onedir package bundles ffmpeg/ffprobe/ffplay, theme, README and licence; portable `config/` takes precedence | `dist\AxiomPy` built and `AxiomPy.exe` stayed running through a 5-second startup smoke |
| Generator fixes | string item lists no longer coerced to numbers; ViewModel defaults now read from backing-field initialisers; property writes mirror the public backing field | regenerated `codecs_data.py` / `defaults.py` |
| Containers | `containers_data.py` generated from `FormatContainers.cs` (15 containers, media/codec lists) and `FormatControls.cs` (per-container defaults); codec tables are now keyed by the **combo box labels** (`"MOV Text"`, `"H264 NVENC"`, `"MPEG-2"`) instead of C# class names | `tests/test_control_parity.py` |

## Next

The main migration is runnable end to end.  Remaining work is polish rather than a
missing milestone:

1. Per-file batch status rows instead of one preview queue for the generated loop.
2. Optional audio/subtitle title/language/delay editors; the current generator keeps
   stream metadata and the external-file plumbing is wired, but those per-file editors
   are not in the Qt shell yet.
3. Review residual WPF handlers that only changed visual state (expanders, hover
   animations, button captions) against the Qt layout.
4. Add screenshot-based visual comparison against the original theme.

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
* `Program.Reset()` also clears the generated crop state, and batch cases normalise
  `BatchExtension_Text` the same way the input textbox does.
* Preset cases capture `presetState` immediately after `Profiles.Presets.SetPreset()`;
  `tools/codegen/gen_presets.py` extracts only the properties each branch assigns.
* `build_harness.py` overwrites `gen_src/` in place instead of deleting it, because the
  Windows sandbox may deny recursive deletes while allowing writes.

