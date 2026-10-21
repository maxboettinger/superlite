"""Keep the user's real ~/.superlite history out of the script tests: lint, schedule and predict read it.
The host's session id and state override stay out too: a test that wants a session sets one."""
import pytest


@pytest.fixture(autouse=True)
def _isolated_superlite_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "_sl_home"))
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "1")  # most tests assert real commits; test_autocommit.py turns it off
    for var in ("CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "CLAUDE_ENV_FILE"):
        monkeypatch.delenv(var, raising=False)
