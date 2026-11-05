# tests/scripts/test_fleet_lead.py
import json
from pathlib import Path
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import fleet_lead as fl  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="argv and env are read from the in-process fake")

def test_lead_argv_and_env(tmp_path):
    assert fl.lead_argv("/p/sl", "opus") == ["--model", "opus", "--permission-mode", "auto", "--allowedTools", "Bash(maxapp ship *)",
                                             "Bash(/p/sl backlog ship *)", "--disallowedTools", "AskUserQuestion"]
    m, l = tmp_path / "m" / ".superlite", tmp_path / "wt" / ".superlite"
    assert fl.lead_env(m, l, "W2", "/u/.claude-account3", {"HOME": "/u", "CLAUDE_CODE_PLUGIN_CACHE_DIR": "/c"}, ["claude1", "claude3"]) == {
        "SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_AGENT": "lead", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_STATE_DIR": str(l.resolve()),
        "SUPERLITE_FLEET_PARENT_DIR": str(m.resolve()), "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION": "0", "SUPERLITE_FLEET_ACCOUNTS": "claude1,claude3",
        "CLAUDE_CONFIG_DIR": "/u/.claude-account3", "CLAUDE_CODE_PLUGIN_CACHE_DIR": "/c"}
    assert not {"SUPERLITE_FLEET_ACCOUNTS", "CLAUDE_CONFIG_DIR", "SUPERLITE_FINAL_REVIEW"} & set(fl.lead_env(m, l, "W2", "/u/.claude", {"HOME": "/u"}, []))

def test_spawn_lead_starts_in_the_worktree_without_prime(world, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    wt = tmp_path / "wt"; wt.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    lsd, name = str((wt / ".superlite").resolve()), fleet.fs.agent_name(world.sd, "W1")
    assert r == {"id": "W1", "name": name, "account": "claude3", "pane_id": "w6:p1", "agent": "lead", "model": "opus", "role": "lead", "lead_sd": lsd}
    sl = str(Path(fl.__file__).resolve().parent / "sl")
    assert ("start_agent", name, fl.lead_argv(sl, "opus")) in world.fh.calls and not any(c[0] == "prompt" for c in world.fh.calls)
    env = next(c for c in world.fh.calls if c[0] == "create_workspace")[2]
    assert (env["SUPERLITE_FLEET_ROLE"], env["SUPERLITE_STATE_DIR"], env["SUPERLITE_FLEET_PARENT_DIR"]) == ("lead", lsd, str(world.sd.resolve()))
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert (w["state"], w["role"], w["one_turn"], w["lead_sd"], w["worktree"]) == ("ready", "lead", False, lsd, str(wt.resolve()))
    assert not (world.sd / "pool.json").exists() or json.loads((world.sd / "pool.json").read_text())["agents"] == []
    assert "W1 account=claude3 pane=w6:p1 agent=lead role=lead" in capsys.readouterr().out
    assert json.loads((world.sd / "metrics.jsonl").read_text().splitlines()[0])["type"] == "fleet:lead"

def test_trust_dialog_and_stopping_a_lead_stops_its_fleet_first(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    fleet.main(["on"]); world.fh.start_error = "agent_not_ready"; world.fh.screen = "Quick safety check\n   Yes, I trust this folder\n"
    wt = tmp_path / "wt"; fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    name = fleet.fs.agent_name(world.sd, "W1")
    assert ("send_keys", name, ["Down", "Enter"]) in world.fh.calls
    lsd = wt / ".superlite"
    fleet.fs.save(lsd, {**fleet.fs.default(), "on": True, "workspace_id": "w9", "workers": {"W1": {"name": "sl-wt-ab12-w1", "pane_id": "w9:p1", "state": "busy"}}})
    fleet.stop(world.sd, ["W1"])
    assert [c[1] for c in world.fh.calls if c[0] == "exit_agent"] == ["sl-wt-ab12-w1", name]
    assert fleet.fs.load(lsd)["workers"]["W1"]["state"] == "stopped"
