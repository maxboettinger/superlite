"""A private copy of tests/scripts/fixtures, so no fixture plan resolves to the checkout's live .superlite."""
import atexit
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "fixtures"


def _in_git(path):
    return subprocess.run(["git", "-C", str(path), "rev-parse"], capture_output=True).returncode == 0


def _make():
    base = Path(tempfile.mkdtemp(prefix="sl_fixtures_")).resolve()
    if _in_git(base):  # TMPDIR inside a repo: fall back to /tmp
        shutil.rmtree(base, ignore_errors=True)
        base = Path(tempfile.mkdtemp(prefix="sl_fixtures_", dir="/tmp")).resolve()
        if _in_git(base):
            shutil.rmtree(base, ignore_errors=True)
            raise RuntimeError("no temp folder outside a git repository for the fixture copy")
    atexit.register(shutil.rmtree, base, ignore_errors=True)
    dest = base / "fixtures"
    shutil.copytree(SOURCE, dest, symlinks=True)
    return dest


FIXTURES = _make()
