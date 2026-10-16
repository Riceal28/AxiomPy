"""``python -m axiom.cli`` - thin wrapper over :mod:`axiom.core.cli`."""

from __future__ import annotations

from .core.cli import describe, generate_command, load_cases, main, select_cases

__all__ = ["main", "describe", "generate_command", "load_cases", "select_cases"]

if __name__ == "__main__":
    raise SystemExit(main())
