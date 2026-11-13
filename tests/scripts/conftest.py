"""Keep the user's real ~/.superlite history out of the script tests: lint, schedule and predict read it.
The host's session id and state override stay out too: a test that wants a session sets one."""
import atexit
import os
import shutil
import tempfile

import pytest

from _fixtures import HOST_VARS  # importing it drops the host vars, sets the process-wide disk floor 0 and a git
# identity on a host without one (#631), and makes the fixture copy before collection

# a session home at import: module-level ENV dicts and subprocesses never see the real ~/.superlite (#550)
_SESSION_HOME = tempfile.mkdtemp(prefix="sl-home-")
os.environ["SUPERLITE_HOME"] = _SESSION_HOME
atexit.register(shutil.rmtree, _SESSION_HOME, True)
os.environ["SUPERLITE_GUARD_SECONDS"] = "30"  # the judge's wall-clock budget under suite load; hooks and nested runs inherit it (#739)


@pytest.fixture(autouse=True)
def _isolated_superlite_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "_sl_home"))
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "1")  # most tests assert real commits; test_autocommit.py turns it off
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(tmp_path / "_user_test_cmd.json"))  # the user's real ~/.config file stays out
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "0")  # no test depends on the free space of the machine
    monkeypatch.setenv("SUPERLITE_DISK_WARN_GB", "0")
    monkeypatch.setenv("SUPERLITE_FORECAST_LIVE", "0")  # the forecast's live inputs (ledgers, sessions, locks) stay out; #605 tests turn them on
    monkeypatch.setenv("SUPERLITE_DERIVED_DATA_HOME", str(tmp_path / "_derived_data"))  # the real DerivedData stays out
    monkeypatch.setenv("SUPERLITE_SCRATCH_HOME", str(tmp_path / "_scratch"))  # the real /tmp/claude-<uid> stays out
    monkeypatch.setenv("SUPERLITE_MACHINE_LIMIT", "0")  # 0 = no count cap; no test reaches the real ps or sysctl (#560, #643)
    monkeypatch.setenv("SUPERLITE_MACHINE_FLOOR", "0")  # 0 = no memory floor: the gate measures nothing (#560, #643)
    monkeypatch.setenv("SUPERLITE_MCP_CHECK", "0")  # no test reaches a real MCP server (#576)
    for var in HOST_VARS:
        monkeypatch.delenv(var, raising=False)
