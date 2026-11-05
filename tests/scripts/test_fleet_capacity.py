# tests/scripts/test_fleet_capacity.py
import hashlib, json
import pytest
from test_accounts import acc
from test_fleet import REAL, _three_accounts, fleet, world  # noqa: F401  (world is a fixture)
from test_plan_tools import ROOT

def _rows(*names):
    return [{"name": n, "agent_status": "working", "cwd": "/u/x", "pane_id": f"w9:p{i}"} for i, n in enumerate(names, 1)]

def _name(world, wid):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]["name"]

def _kinds(world):
    return [c[0] for c in world.fh.calls]

@pytest.mark.skipif(REAL, reason="call order is read from the in-process fake")
def test_fifth_worker_opens_a_tab(world):
    fleet.main(["on"])
    for _ in range(5): fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    k = _kinds(world)
    assert (k.count("create_workspace"), k.count("split_pane"), k.count("create_tab")) == (1, 3, 1)
    assert [w["state"] for w in json.loads((world.sd / "fleet.json").read_text())["workers"].values()] == ["ready"] * 5

@pytest.mark.skipif(REAL, reason="call order is read from the in-process fake")
def test_eight_workers_fill_two_tabs(world):
    fleet.main(["on"])
    for _ in range(8): fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    k = _kinds(world)
    assert (k.count("create_workspace"), k.count("split_pane"), k.count("create_tab")) == (1, 6, 1)

@pytest.mark.skipif(REAL, reason="scripted layout needs the in-process fake")
def test_short_panes_open_a_tab(world):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj); w2 = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    world.fh.layout = [{"pane_id": "w6:p1", "rows": 30, "cols": 73}, {"pane_id": w2["pane_id"], "rows": 30, "cols": 73}]
    w3 = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _kinds(world).count("create_tab") == 1 and w3["pane_id"] not in ("w6:p1", w2["pane_id"])

@pytest.mark.skipif(REAL, reason="scripted screen needs the in-process fake")
def test_no_ready_names_the_pane_size(world, capsys):
    fleet.main(["on"]); world.fh.screen = "something else\n"; world.fh.layout = [{"pane_id": "w6:p1", "rows": 14, "cols": 47}]
    with pytest.raises(SystemExit) as e: fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and "BLOCKED: W1 no READY (pane 14 rows, 47 cols)" in capsys.readouterr().out

@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_stalled_prime_is_resent_once(world):
    fleet.main(["on"]); orig, seen = world.fh.prompt, []
    def flaky(n, t, u, ms):
        seen.append(t)
        if len(seen) == 1: raise world.fh.HerdrError("agent_prompt_stalled", "no working state within 5000 ms")
        return orig(n, t, u, ms)
    world.fh.prompt = flaky
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1" and len(seen) == 2 and seen[0] == seen[1]

@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_second_stall_blocks_and_other_errors_are_not_resent(world, capsys):
    fleet.main(["on"]); seen = []
    def stalled(n, t, u, ms): seen.append(t); raise world.fh.HerdrError("agent_prompt_stalled", "stalled")
    world.fh.prompt = stalled
    with pytest.raises(SystemExit) as e: fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and len(seen) == 2 and "agent_prompt_stalled" in capsys.readouterr().out
    def gone(n, t, u, ms): seen.append(t); raise world.fh.HerdrError("agent_not_found", "gone")
    world.fh.prompt = gone; seen.clear()
    with pytest.raises(SystemExit): fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert len(seen) == 1

@pytest.mark.skipif(REAL, reason="scripted agent list needs the in-process fake")
def test_spawn_avoids_accounts_busy_in_other_sessions(world, monkeypatch):
    """Spike S1: a lead's W1 landed on claude3, the lead's own account and the one with the lowest weekly use."""
    usage = {"accounts": [acc("claude1", 1, weekly_all=70), acc("claude2", 2, weekly_all=32), acc("claude3", 3, weekly_all=13)]}
    listing = {"accounts": [{"name": f"claude{i}", "dir": f"/u/.claude-account{i}"} for i in (1, 2, 3)]}
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: usage); monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: listing)
    for name in ("sl-main-1a2b-w2", "sl-dashmax-3c4d-w31"):  # the lead itself and a worker of another session, both on claude3
        fleet.fs.register_agent(name, "claude3")
    world.fh.agent_rows = _rows("sl-main-1a2b-w2", "sl-dashmax-3c4d-w31", "sl-old-9e9e-w1")
    fleet.main(["on"])
    assert [fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] for _ in range(2)] == ["claude2", "claude1"]

@pytest.mark.skipif(REAL, reason="scripted agent list needs the in-process fake")
def test_agent_list_error_counts_this_run_only(world, monkeypatch):
    _three_accounts(world, monkeypatch); fleet.fs.register_agent("sl-other-5e6f-w1", "claude1")
    def boom(): raise world.fh.HerdrError("timeout", "herdr agent list timed out")
    world.fh.agents = boom
    fleet.main(["on"])
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] == "claude1"

def test_spawn_registers_its_worker_machine_wide(world):
    fleet.main(["on"]); r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert fleet.fs.live_by_account(_rows(_name(world, r["id"])), set()) == {"claude3": 1}

def test_capped_current_account_is_refused(world, monkeypatch, capsys):
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: {"accounts": [acc("claude1", 1, session=95, weekly_all=10)]})
    fleet.main(["on", "--accounts", "current"])
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env={"HOME": "/u", "CLAUDE_CONFIG_DIR": "/u/.claude-account1"})
    out = capsys.readouterr().out
    assert e.value.code == 3 and "BLOCKED: no account with headroom" in out and "current: 5-hour 95%" in out

def test_current_with_headroom_registers_its_claude_profile_name(world):
    fleet.main(["on", "--accounts", "current"])
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env={"HOME": "/u", "CLAUDE_CONFIG_DIR": "/u/.claude-account1"})
    assert r["account"] == "current" and fleet.fs.live_by_account(_rows(_name(world, r["id"])), set()) == {"claude1": 1}

def test_agent_name_carries_a_hash_of_the_run_root(world):
    fleet.main(["on"]); r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _name(world, r["id"]) == f"sl-proj-{hashlib.sha1(str(world.proj.resolve()).encode()).hexdigest()[:4]}-w1"

def test_fleet_docs_name_capacity_and_hard_stop():
    skill = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
    docs = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
    for text in (skill, docs):
        assert "report BLOCKED" in text and "never fall back to in-process" in text and "sl-<run folder>-<hash>-w" in text
    assert "one taskgraph plan in one checkout" in skill and "in addition" in skill
    assert "4 panes" in docs and "20 rows" in docs and "fleet/agents" in docs and "different names" not in docs
