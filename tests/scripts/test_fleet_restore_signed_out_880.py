# tests/scripts/test_fleet_restore_signed_out_880.py: sl fleet restore notices Claude Code's sign-in screen (#880)
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_fleet_restore_577 import HE, World, worker  # noqa: E402,F401

SIGN_IN = "Select login method:\n"
HINT = "sign in once (CLAUDE_CONFIG_DIR=/x/.claude-1 claude, then /login), then rerun sl fleet restore"


@pytest.fixture
def w(tmp_path, monkeypatch):
    return World(tmp_path, monkeypatch)


def claude1(**kw):
    launch = {"argv": ["--agent", "superlite:implementer"], "env": {"CLAUDE_CONFIG_DIR": "/x/.claude-1"}, "cwd": "/p"}
    return worker(**{"account": "claude1", "state": "ready", "task": None, "launch": launch, **kw})


def line(who="W1", acct="claude1", hint=HINT):
    return f"BLOCKED: {who} not restored (account {acct} signed out: Claude Code sign-in screen; {hint})"


def test_restore_signed_out_worker_blocked(w):
    w.save({"W1": claude1()})
    w.fake.screen = SIGN_IN
    lines, blocked = w.run()
    assert blocked and lines[0] == line()
    assert w.data()["workers"]["W1"]["state"] == "blocked"
    import fleet
    assert fleet.signed_out_accounts(w.sd) == {"claude1"}
    new = next(c for c in w.fake.calls if c[0] == "start_agent")[2]
    assert ("close_pane", new) in w.fake.calls
    assert not any(c[0] == "prompt" for c in w.fake.calls)


def test_restore_signed_out_default_dir_hint(w):
    rec = claude1()
    rec["launch"]["env"] = {}
    w.save({"W1": rec})
    w.fake.screen = SIGN_IN
    lines, blocked = w.run()
    assert blocked and lines[0] == line(hint="sign in once (claude, then /login), then rerun sl fleet restore")


def test_restore_signed_out_dead_worker_keeps_record(w):
    w.save({"W1": claude1(state="stopped", dead=True, was="ready")})
    w.fake.screen = SIGN_IN
    lines, blocked = w.run()
    assert blocked and lines[0] == line()
    rec = w.data()["workers"]["W1"]
    assert rec["state"] == "stopped" and rec["dead"]


def test_restore_sign_in_after_start_error(w):
    w.save({"W1": claude1()})
    w.fake.screen = SIGN_IN
    w.fake.start_errors = [("agent_not_ready", "not ready")]
    lines, blocked = w.run()
    assert blocked and lines[0] == line()


def test_restore_remote_record_not_marked(w):
    import fleet
    w.save({"W1": claude1(machine="box", account="claude1@box")})
    w.fake.screen = SIGN_IN
    lines, blocked = w.run()
    assert blocked and lines[0].startswith("BLOCKED: W1 not restored (account claude1@box signed out")
    assert fleet.signed_out_accounts(w.sd) == set()
