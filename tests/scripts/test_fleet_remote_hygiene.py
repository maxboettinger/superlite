# tests/scripts/test_fleet_remote_hygiene.py: pruning of old plugin trees and the longer waits for a remote agent
import json
import sys
import time

import pytest
from test_fleet_remote_worker import world, started  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_remote as fr  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402
import fleet_state as fs  # noqa: E402


def listing(monkeypatch, trees_, fail=False):
    """Fake `list` of the remote_tree command; every other verb runs for real. The dropped tree names."""
    real, dropped, calls = fr._run, [], []
    def run(label, verb, args, cwd, timeout_s):
        if verb == "list":
            calls.append((label, args, cwd, timeout_s))
            if fail: raise fr.RemoteError("box unreachable: x")
            return json.dumps({"trees": trees_}).encode()
        return real(label, verb, args, cwd, timeout_s)
    monkeypatch.setattr(fr, "_run", run)
    real_drop = fr.drop
    def drop(label, root, name, timeout_s=60):
        if name.startswith("plugin/"):
            dropped.append(name); return True
        return real_drop(label, root, name, timeout_s)
    monkeypatch.setattr(fr, "drop", drop)
    return dropped, calls


def test_trees_runs_list(monkeypatch):
    dropped, calls = listing(monkeypatch, [{"name": "plugin/abc", "base": "b", "path": "/u/p"}])
    assert fr.trees("box", "/u/sl") == [{"name": "plugin/abc", "base": "b", "path": "/u/p"}]
    assert calls == [("box", ["--json"], "/u/sl", 30)]


def test_prune_keeps_live_plugin(world, monkeypatch):
    monkeypatch.setattr(rw, "_committed", lambda base: time.time() - 30 * 3600)
    started(world)
    live = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["remote"]["plugin"]
    dropped, _ = listing(monkeypatch, [{"name": "plugin/abc123", "path": live}, {"name": "plugin/old999", "base": "old", "path": "/h/old"}, {"name": "other/x", "path": "/h/x"}])
    monkeypatch.setattr(fr, "plugin", lambda label, r, timeout_s=120: fr.push(label, r, "plugin/def456", "def456", [], timeout_s))
    rw.spawn(world.sd, "research", None, world.proj, "box")
    assert dropped == ["plugin/old999"]


def test_prune_failure_not_fatal(world, monkeypatch, capsys):
    listing(monkeypatch, [], fail=True)
    assert started(world)["id"] == "W1"
    assert "plugin trees kept on box: box unreachable: x" in capsys.readouterr().err


def test_prune_drop_failure_not_fatal(world, monkeypatch, capsys):
    monkeypatch.setattr(rw, "_committed", lambda base: time.time() - 30 * 3600)
    dropped, _ = listing(monkeypatch, [{"name": "plugin/old999", "base": "old", "path": "/h/old"}])
    def bad(label, root, name, timeout_s=60): raise fr.RemoteError("drop failed")
    monkeypatch.setattr(fr, "drop", bad)
    assert started(world)["id"] == "W1"
    assert "plugin trees kept on box: drop failed" in capsys.readouterr().err


def test_spawn_waits_90s_for_agent(world, monkeypatch):
    seen = []
    monkeypatch.setattr(world.fh, "wait_state", lambda name, until, timeout_ms: seen.append((until, timeout_ms)) or "idle", raising=False)
    started(world)
    assert (["idle", "done"], 90000) in seen


def test_remote_prompt_wait_60s(world, monkeypatch):
    started(world)
    seen = []
    monkeypatch.setattr(world.fh, "prompt", lambda name, text, until, timeout_ms: seen.append(timeout_ms), raising=False)
    b = world.sd / "briefs" / "q.md"; b.write_text("question")
    rw.send_brief(world.sd, "W1", str(b), "Q1")
    assert seen == [60000]


def test_prune_keeps_young_unused_plugin(world, monkeypatch):
    ages = {"young": 2 * 3600, "old": 30 * 3600}
    monkeypatch.setattr(rw, "_committed", lambda base: time.time() - ages[base] if base in ages else None)
    dropped, _ = listing(monkeypatch, [{"name": "plugin/y", "base": "young", "path": "/h/y"}, {"name": "plugin/o", "base": "old", "path": "/h/o"},
                                       {"name": "plugin/u", "base": "gone", "path": "/h/u"}])
    started(world)
    assert dropped == ["plugin/o"]


OLD = [{"name": "plugin/o", "base": "old", "path": "/h/o"}]


def old_plugins(monkeypatch):
    monkeypatch.setattr(rw, "_committed", lambda base: time.time() - 30 * 3600)
    return listing(monkeypatch, OLD)[0]


def test_prune_skips_a_host_with_another_superlite_agent(world, monkeypatch, capsys):
    dropped = old_plugins(monkeypatch)
    world.fh.agent_map = {"sl-other-w9": "working", "my-own-agent": "idle"}
    assert started(world)["id"] == "W1"
    assert dropped == [] and "plugin trees kept" not in capsys.readouterr().err


def test_prune_runs_on_an_idle_host(world, monkeypatch):
    dropped = old_plugins(monkeypatch)
    world.fh.agent_map = {"my-own-agent": "idle"}
    started(world)
    assert dropped == ["plugin/o"] and ("on", "box") in world.fh.calls


def test_prune_ignores_this_runs_own_workers(world, monkeypatch):
    started(world)
    own = rw.fs.name_of(world.sd, "W1", rw.fs.workers(world.sd)["W1"])
    dropped = old_plugins(monkeypatch)
    world.fh.agent_map = {own: "working"}
    rw.spawn(world.sd, "research", None, world.proj, "box")
    assert dropped == ["plugin/o"]


def test_prune_failed_agent_list_drops_nothing(world, monkeypatch, capsys):
    dropped = old_plugins(monkeypatch)
    world.fh.list_error = True
    assert started(world)["id"] == "W1"
    assert dropped == [] and "plugin trees kept on box:" in capsys.readouterr().err


def _stalled_prompt(world, monkeypatch):
    sent = []

    def prompt(name, text, until, timeout_ms):
        sent.append(text)
        raise world.fh.HerdrError("agent_prompt_stalled", "agent prompt produced no observed working or blocked state within 5000 ms; current status is idle")
    monkeypatch.setattr(world.fh, "prompt", prompt, raising=False)
    b = world.sd / "briefs" / "q.md"; b.write_text("question")
    return sent, b


def test_remote_prompt_login_line_fails_without_resend(world, monkeypatch):
    started(world)
    sent, b = _stalled_prompt(world, monkeypatch)
    world.fh.screen = "❯ Read the brief\n⏺ Login reached its time limit · Please run /login\n✻ Cooked for 0s\n"
    with pytest.raises(world.fh.HerdrError) as ei:
        rw.send_brief(world.sd, "W1", str(b), "Q1")
    assert ei.value.code == rw.SIGNED_OUT and "signed out" in ei.value.message and len(sent) == 1


def test_remote_prompt_stall_without_login_line_resends(world, monkeypatch):
    started(world)
    sent, b = _stalled_prompt(world, monkeypatch)
    world.fh.screen = "❯ Read the brief\n"
    with pytest.raises(world.fh.HerdrError) as ei:
        rw.send_brief(world.sd, "W1", str(b), "Q1")
    assert ei.value.code == "agent_prompt_stalled" and len(sent) == 2
