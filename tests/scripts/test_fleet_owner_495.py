import json
import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_state as fs  # noqa: E402

SL = str(SCRIPTS / "sl")


@pytest.fixture
def d(tmp_path, monkeypatch):
    for k in list(os.environ):
        if k.startswith("SUPERLITE_FLEET_"):
            monkeypatch.delenv(k)
    for k in ("SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "CLAUDE_PID"):
        monkeypatch.delenv(k, raising=False)
    p = tmp_path / "proj" / ".superlite"
    p.mkdir(parents=True)
    return p


def test_owner_reads_session_and_pid(d, monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", "42")
    assert fs.owner() == {"owner_session": "s1", "owner_pid": 42}


def test_owner_empty_without_env(d):
    assert fs.owner() == {}


def test_owner_skips_non_digit_pid(d, monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "abc")
    monkeypatch.setenv("CLAUDE_PID", "12a")
    assert fs.owner() == {"owner_session": "abc"}


def test_set_on_records_owner(d, monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", "42")
    fs.set_on(d, "sl:x", [])
    data = fs.load(d)
    assert data["on"] is True and data["owner_session"] == "s1" and data["owner_pid"] == 42


def test_set_on_again_takes_over(d, monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", "42")
    fs.set_on(d, "sl:x", [])
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s2")
    monkeypatch.delenv("CLAUDE_PID")
    fs.set_on(d, "sl:y", [])
    data = fs.load(d)
    assert data["owner_session"] == "s2" and "owner_pid" not in data and data["label"] == "sl:y"


def test_set_on_without_session_drops_owner(d, monkeypatch):
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "s1")
    monkeypatch.setenv("CLAUDE_PID", "42")
    fs.set_on(d, "sl:x", [])
    monkeypatch.delenv("SUPERLITE_SESSION_ID")
    monkeypatch.delenv("CLAUDE_PID")
    fs.set_on(d, "sl:x", [])
    data = fs.load(d)
    assert "owner_session" not in data and "owner_pid" not in data


def test_sl_fleet_on_records_owner(d):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.update(SUPERLITE_SESSION_ID="s9", CLAUDE_PID="7")
    r = subprocess.run([SL, "fleet", "on", "--plan", str(d)], env=env, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    data = json.loads((d / "fleet.json").read_text())
    assert data["owner_session"] == "s9" and data["owner_pid"] == 7
