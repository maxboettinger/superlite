"""Full-suite isolation: tests/regression modules import test_run_scripts before pytest loads tests/scripts/conftest.py,
so its ENV snapshot must already be free of the host session's vars; else commit_task in a tmp repo writes the host run's
ledger and reads its stable.json baseline (25 full-suite-only failures in batch 6)."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS_TESTS = Path(__file__).resolve().parents[1] / "scripts"

PROBE = """
import json, sys
sys.path.insert(0, sys.argv[1])
from test_run_scripts import ENV
from _fixtures import HOST_VARS
print(json.dumps(sorted(v for v in HOST_VARS if v in ENV)))
"""


def test_env_snapshot_drops_host_vars_without_scripts_conftest(tmp_path):
    leak = {"CLAUDE_CODE_SESSION_ID": "host-session", "SUPERLITE_SESSION_ID": "host-session",
            "SUPERLITE_STATE_DIR": str(tmp_path / "host" / ".superlite"), "CLAUDE_PROJECT_DIR": str(tmp_path / "host")}
    r = subprocess.run([sys.executable, "-c", PROBE, str(SCRIPTS_TESTS)], capture_output=True, text=True,
                       encoding="utf-8", cwd=tmp_path, env={**os.environ, **leak})
    assert r.returncode == 0, r.stderr
    assert json.loads(r.stdout.strip().splitlines()[-1]) == []
