import os
import tempfile

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

# Keep test runs away from both the repository config and %APPDATA%.
os.environ["AXIOM_PORTABLE_ROOT"] = tempfile.mkdtemp(
    prefix="axiompy-test-config-"
)
