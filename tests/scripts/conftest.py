"""Keep the user's real ~/.superlite history out of the script tests: lint, schedule and predict read it.
The host's session id and state override stay out too: a test that wants a session sets one."""
import os

import pytest

import _fixtures  # noqa: F401 (the fixture copy is made before collection)

HOST_VARS = ("CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "CLAUDE_ENV_FILE",
             "CLAUDE_CODE_ENTRYPOINT", "CLAUDE_CODE_FORK_SUBAGENT")  # the budget's agent-summary note reads these

# Before collection: test modules snapshot os.environ into ENV at import, and a host session id there would send a
# subprocess's default state (pool.json, gate) to the host session's bound .superlite.
for _var in HOST_VARS:
    os.environ.pop(_var, None)


@pytest.fixture(autouse=True)
def _isolated_superlite_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "_sl_home"))
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "1")  # most tests assert real commits; test_autocommit.py turns it off
    for var in HOST_VARS:
        monkeypatch.delenv(var, raising=False)
