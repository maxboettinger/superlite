"""A private copy of tests/scripts/fixtures, so no fixture plan resolves to the checkout's live .superlite.
Also drops the host's session id and state override from os.environ: test modules snapshot it into ENV at import,
and a tests/regression module imports them before pytest loads tests/scripts/conftest.py."""
import atexit
import os
import shutil
import subprocess
import tempfile
from pathlib import Path

SOURCE = Path(__file__).resolve().parent / "fixtures"
HOST_VARS = ("CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "CLAUDE_ENV_FILE",
             "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_FORK_SUBAGENT",  # the budget's agent-summary note reads these
             "SUPERLITE_FLEET_WORKER", "SUPERLITE_FLEET_AGENT",  # the SessionStart hook injects the worker note on these
             "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR")  # a batch lead pane exports these

# On first import, before any ENV snapshot (test_run_scripts imports this first): a host session id there would send a
# subprocess's default state (ledger, checkpoints, pool.json, gate) to the host session's bound .superlite.
for _var in HOST_VARS:
    os.environ.pop(_var, None)


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
