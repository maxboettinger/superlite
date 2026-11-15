# tests/scripts/test_fleet_remote_account.py
import sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_remote_account as fra  # noqa: E402
import fleet_state as fs  # noqa: E402

ENV = {"HOME": "/Users/u"}


def fake(monkeypatch, result, seen=None):
    def choose(sd, model, env, avoid=None, lead=False):
        if seen is not None:
            seen.append((sd, model, env))
        return result
    monkeypatch.setattr(fleet, "choose_account", choose)


def test_maps_folder_to_remote_home(monkeypatch, tmp_path):
    seen = []
    fake(monkeypatch, ("claude2", "/Users/u/.claude-account2", "claude2"), seen)
    assert fra.pick(tmp_path, "box", "sonnet", ENV, "/home/u", "/Users/u") == ("claude2@box", "/home/u/.claude-account2")
    assert seen == [(tmp_path, "sonnet", ENV)]


def test_default_dir(monkeypatch, tmp_path):
    fake(monkeypatch, ("claude1", "/Users/u/.claude", "claude1"))
    assert fra.pick(tmp_path, "box", "sonnet", ENV, "/home/u", "/Users/u") == ("claude1@box", None)


def test_outside_home(monkeypatch, tmp_path, capsys):
    fake(monkeypatch, ("claude2", "/opt/c", "claude2"))
    with pytest.raises(SystemExit) as e:
        fra.pick(tmp_path, "box", "sonnet", ENV, "/home/u", "/Users/u")
    assert e.value.code == 3
    assert "BLOCKED: fleet spawn: machine box: account claude2 folder /opt/c is outside /Users/u" in capsys.readouterr().out


def test_local_home_default(monkeypatch, tmp_path):
    fake(monkeypatch, ("claude2", str(Path.home() / ".claude-account2"), "claude2"))
    assert fra.pick(tmp_path, "box", "sonnet", {"HOME": str(Path.home())}, "/home/u") == ("claude2@box", "/home/u/.claude-account2")


def test_pick_counts_remote_live(monkeypatch, tmp_path):
    # the real choose_account counts a ready remote worker like a local one
    import accounts as ac
    import herdr_client as hc
    monkeypatch.setattr(ac, "read_usage", lambda env: {"accounts": [
        {"name": "claude1", "weekly_all": {"percent": 10}, "session": {"percent": 10}},
        {"name": "claude2", "weekly_all": {"percent": 10}, "session": {"percent": 10}}]})
    monkeypatch.setattr(ac, "read_listing", lambda env: {"accounts": []})
    monkeypatch.setattr(hc, "agents", lambda: [])
    seen = {}

    def pick_account(usage, allowed, running, model, alias):
        seen.update(running)
        return "claude1"
    monkeypatch.setattr(ac, "pick_account", pick_account)
    monkeypatch.setattr(ac, "account_dir", lambda *a, **k: "/Users/u/.claude")
    data = {"workers": {"W1": {"state": "ready", "account": "claude2@box", "machine": "box"}}, "accounts": ["claude1", "claude2"]}
    monkeypatch.setattr(fs, "load", lambda sd: data)
    monkeypatch.setattr(fs, "name_of", lambda sd, k, v: k)
    assert fra.pick(tmp_path, "box", "sonnet", ENV, "/home/u", "/Users/u")[0] == "claude1@box"
    assert seen.get("claude2") == 1


def test_login_screen():
    assert fra.login_screen("Select login method:\n1. Claude account")
    assert fra.login_screen("Please run /login")
    assert not fra.login_screen("> READY")
