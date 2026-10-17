"""Typed script representation used by the CLI and the desktop shell.

The parity-tested generator still exposes its canonical command text as a string:
the C# oracle emits text, including multi-pass joins and shell-specific batch
syntax.  ``Script`` adds the metadata the UI needs without changing that baseline.
"""

from __future__ import annotations

import shlex
from dataclasses import dataclass

from .state import AxiomState


@dataclass(frozen=True)
class Script:
    """A generated command plus the shell settings needed to launch it."""

    text: str
    shell: str = "CMD"
    keep_window: bool = False
    two_pass: bool = False
    batch: bool = False

    @property
    def inline(self) -> str:
        """Return the command with line breaks replaced by single spaces."""
        return " ".join(self.text.splitlines()).strip()

    @property
    def lines(self) -> list[str]:
        """Return one shell token per line for the script view's Sort mode.

        Quoted Windows paths are preserved.  If the generated text cannot be
        tokenised (for example an edited script with an unmatched quote), the
        original text is returned as one line instead of losing user input.
        """
        source = self.inline
        if not source:
            return []
        try:
            return shlex.split(source, posix=False)
        except ValueError:
            return [source]

    @property
    def sorted_text(self) -> str:
        return "\n".join(self.lines)


def generate_script(state: AxiomState) -> Script:
    """Build the command and capture the state that affects how it is run."""
    from .generate import generate_runnable

    return Script(
        text=generate_runnable(state),
        shell=str(state.get("Configure.Shell_SelectedItem") or "CMD"),
        keep_window=bool(state.get("Main.CMDWindowKeep_IsChecked")),
        two_pass=state.get("Video.Video_Pass_SelectedItem") == "2 Pass",
        batch=bool(state.get("Main.Batch_IsChecked")),
    )


def to_argv(text: str) -> list[str]:
    """Split a single inline command into shell-aware argv tokens."""
    try:
        return shlex.split(" ".join(text.splitlines()), posix=False)
    except ValueError:
        return [" ".join(text.splitlines()).strip()]
