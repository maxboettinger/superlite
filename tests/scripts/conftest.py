"""Keep the user's real ~/.superlite history out of the script tests: lint, schedule and predict read it.
The host's session id and state override stay out too: a test that wants a session sets one."""
import pytest

from _fixtures import HOST_VARS  # importing it drops the host vars and makes the fixture copy before collection


@pytest.fixture(autouse=True)
def _isolated_superlite_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "_sl_home"))
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "1")  # most tests assert real commits; test_autocommit.py turns it off
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(tmp_path / "_user_test_cmd.json"))  # the user's real ~/.config file stays out
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "0")  # no test depends on the free space of the machine
    monkeypatch.setenv("SUPERLITE_DISK_WARN_GB", "0")
    monkeypatch.setenv("SUPERLITE_DERIVED_DATA_HOME", str(tmp_path / "_derived_data"))  # the real DerivedData stays out
    for var in HOST_VARS:
        monkeypatch.delenv(var, raising=False)
