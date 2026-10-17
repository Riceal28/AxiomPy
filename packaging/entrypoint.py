"""PyInstaller entry point that avoids executing ``axiom.ui.app`` as a script."""

from axiom.ui.app import main


if __name__ == "__main__":
    raise SystemExit(main())
