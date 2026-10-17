# WPF to Qt UI parity notes

This document closes out the residual visual-handler review.  It records how the
original `MainWindow` handler families map to the Qt shell and which differences are
intentional under the migration plan.

## Handler audit

The original WPF partial classes contain 550 methods, including helpers as well as
event handlers.  Grouping method names by suffix gives:

| Family | Count | Qt treatment |
|---|---:|---|
| Click handlers | 103 | Buttons/actions for run, preview, presets, script I/O, stream lists, settings and crop |
| Selection changes | 51 | Direct bindings plus `ui/control_rules.py` structural refresh scopes |
| Checked/unchecked | 16 | `QCheckBox` bindings for VBR, batch, log, console and auto-sort |
| Keyboard/focus | 93 | Native Qt widget editing; numeric editors use `QSpinBox`/`QDoubleSpinBox` |
| Preview mouse events | 75 | QSS hover/pressed states and standard slider/spin-box behaviour |
| Text changes | 6 | `textChanged` bindings through the generated state model |
| Helpers and other methods | 206 | Ported into `core`, runner, naming, presets, controls or replaced by Qt APIs |

The earlier audit of every retained XAML `IsEnabled` binding reports zero unmapped
controls.  Removed features remain intentionally excluded: downloader, updater,
debug console, crop window, file-properties window and legacy theme/config formats.

## Handler behaviours closed in the final polish pass

* Batch rows now transition through Pending, Running, Completed, Failed and Cancelled
  by matching FFmpeg's `Input #... from '...'` log lines.
* Audio and subtitle mux lists have per-file Title, Language and Delay editors.
  Title/language emit the original `-metadata:s:<stream>:N` flags; delay follows the
  original UI by being stored per file while remaining non-emitting.
* Auto Sort now follows the original default-on behaviour and is persisted in settings.
* Shell title modes (`Filename`, `Tokens`, `Filename+Tokens`) are applied when a visible
  external console is requested.
* Preview launches ffplay asynchronously and refuses batch mode, matching the original
  guard.
* Input and output boxes accept Explorer drag/drop.
* Selecting a preset disables the preset-owned profile controls, shows a persistent
  hint above Input/Output, explains the lock on hover, and offers an Unlock action
  that keeps the current values editable.
* Mouse-wheel changes on combo boxes and spin boxes are blocked by default; the
  behavior is opt-in from Settings → System.

## Intentional visual differences

* Accordion `Expander` panels are represented by nested `QTabWidget` pages and scroll
  areas.  Expansion animation state therefore has no direct equivalent.
* WPF opacity animations and image-sliced disabled/hover backgrounds are replaced by
  one Axiom Dark QSS with native Qt state rendering.
* Button captions use text instead of the original bitmap icon set.
* Five WPF themes are deliberately reduced to one dark skin.

## Screenshot comparison

`tests/ui-baseline` contains 13 deterministic screenshots: all main tabs, all Video,
Audio, Filters and Settings sub-pages, plus the batch queue.

```powershell
python tools/ui_snapshots.py
python tools/compare_screenshots.py tests/ui-baseline artifacts/ui-current
```

The comparison writes per-page difference images to `artifacts/ui-diff` and fails when
more than 0.5% of pixels differ beyond an 8-level channel threshold.  Regenerate the
baseline only for intentional layout or theme changes.

The upstream reference screenshot is `G:\Codex_workspace\Axiom\images\axiom.png`.
That WPF capture remains the manual theme reference; the committed baseline is for
repeatable Qt regression checks, not a pixel-for-pixel WPF target, because the
migration intentionally replaces five WPF skins with one Axiom Dark QSS.
