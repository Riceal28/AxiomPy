"""Per-file metadata for externally muxed audio and subtitle inputs."""

from __future__ import annotations

from ..state import AxiomState
from ..text import wrap_with_quotes


def _language_param(state: AxiomState, group: str, name: str) -> str:
    for item in state.get(f"{group}.{group}_Metadata_Language_Items") or []:
        if isinstance(item, dict) and item.get("Name") == name:
            return str(item.get("Param") or "")
    return ""


def stream_metadata(state: AxiomState, kind: str) -> str:
    """Build ``-metadata:s:<kind>:N`` flags for external mux inputs.

    Title and language follow the original ``Generators/*/Metadata.cs``.  The
    original UI also stored a per-file delay value, but its generator did not emit
    it; the value is preserved in state and exposed by the Qt editor.
    """
    if kind == "audio":
        group = "Audio"
        stream_prefix = "a"
        data_key = "_audio_metadata"
        active = state.get("Audio.Audio_Stream_SelectedItem") == "mux"
    else:
        group = "Subtitle"
        stream_prefix = "s"
        data_key = "_subtitle_metadata"
        active = state.get("Subtitle.Subtitle_Stream_SelectedItem") == "mux"

    if not active:
        return ""

    shell = str(state.get("Configure.Shell_SelectedItem") or "CMD")
    priority = str(
        state.get("Configure.ProcessPriority_SelectedItem") or "Default"
    )
    lines: list[str] = []
    for index, row in enumerate(state.values.get(data_key) or []):
        if not isinstance(row, dict):
            continue
        title = str(row.get("title") or "").strip()
        if title:
            lines.append(
                f"-metadata:s:{stream_prefix}:{index} title="
                + wrap_with_quotes(title, shell, priority)
            )

        language = str(row.get("language") or "").strip()
        if language and language.lower() != "none":
            param = _language_param(state, group, language)
            if param:
                lines.append(
                    f"-metadata:s:{stream_prefix}:{index} language="
                    + wrap_with_quotes(param, shell, priority)
                )
    # The original stored one flag per line and removed all line breaks during final
    # assembly, which concatenated adjacent flags.  Space-join here keeps the same
    # ordering while producing a runnable command line.
    return " ".join(lines)
