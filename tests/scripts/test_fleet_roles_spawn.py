# tests/scripts/test_fleet_roles_spawn.py
import json, sys, types
import pytest
from test_accounts import acc
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)

pytestmark = pytest.mark.skipif(REAL, reason="argv and calls are read from the in-process fake")

def _start(world, i=0):
    return [c for c in world.fh.calls if c[0] == "start_agent"][i]

def _env(world):
    return next(c for c in world.fh.calls if c[0] == "create_workspace")[2]

def _workers(world):
    return json.loads((world.sd / "fleet.json").read_text())["workers"]

def _killed(*a):
    raise KeyboardInterrupt  # the caller's own pane closes with the workspace

def test_final_reviewer_skips_prime_and_pool(world, capsys):
    fleet.main(["on"])
    r = fleet.spawn(world.sd, world.plan, None, world.proj, role="final-reviewer")
    assert r == {"id": "W1", "account": "claude3", "pane_id": "w6:p1", "agent": "superlite:final-reviewer", "model": "opus", "role": "final-reviewer"}
    argv = _start(world)[2]
    assert argv[:4] == ["--agent", "superlite:final-reviewer", "--effort", "high"] and "--model" not in argv
    assert not any(c[0] == "prompt" for c in world.fh.calls)
    w = _workers(world)["W1"]
    assert (w["state"], w["role"], w["one_turn"]) == ("ready", "final-reviewer", True)
    pool = world.sd / "pool.json"
    assert not pool.exists() or json.loads(pool.read_text())["agents"] == []
    assert "W1 account=claude3 pane=w6:p1 agent=superlite:final-reviewer role=final-reviewer" in capsys.readouterr().out

def test_fixer_env_names_role_and_turns_off_suggestions(world):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "2", world.proj, role="fixer")
    env = _env(world)
    assert env["SUPERLITE_FLEET_ROLE"] == "fixer" and env["CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION"] == "0"
    assert env["SUPERLITE_FLEET_AGENT"] == "superlite:fixer-sonnet-high" and env["SUPERLITE_FINAL_REVIEW"] == "off"
    assert _start(world)[2][:4] == ["--agent", "superlite:fixer-sonnet-high", "--effort", "high"]

def test_implementer_keeps_prime_pool_and_line(world, capsys):
    fleet.main(["on"]); r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert r["role"] == "implementer" and any(c[0] == "prompt" and "prime.md" in c[2] for c in world.fh.calls)
    assert _start(world)[2][:6] == ["--agent", "superlite:implementer", "--model", "sonnet", "--effort", "medium"]
    assert json.loads((world.sd / "pool.json").read_text())["agents"][0]["id"] == "W1"
    out = capsys.readouterr().out
    assert "W1 account=claude3 pane=w6:p1 agent=superlite:implementer\n" in out and "role=" not in out
    assert _env(world)["SUPERLITE_FLEET_ROLE"] == "implementer"

def test_state_dir_outside_the_project_is_added(world, tmp_path):
    fleet.main(["on"]); other = tmp_path / "elsewhere"; other.mkdir()
    fleet.spawn(world.sd, world.plan, None, other, role="research")
    argv = _start(world)[2]
    assert argv[argv.index("--add-dir") + 1] == str(world.sd.resolve())
    fleet.spawn(world.sd, world.plan, None, world.proj, role="research")
    assert "--add-dir" not in _start(world, 1)[2]

def test_unknown_role_is_exit_2(world, capsys):
    fleet.main(["on"])
    assert fleet.main(["spawn", "--role", "lead"]) == 2
    assert "unknown role lead" in capsys.readouterr().err and not world.fh.calls

def test_choose_account_and_open_pane_examples(world):
    fleet.main(["on"])
    assert fleet.choose_account(world.sd, "sonnet", {"HOME": "/u"}) == ("claude3", "/u/.claude-account3", "claude3")
    pane = fleet.open_pane(world.sd, "W1", str(world.proj), {"CLAUDE_CONFIG_DIR": "/u/.claude-account3"},
                           {"role": "layer", "state": "busy", "task": "layer-headless"})
    data = json.loads((world.sd / "fleet.json").read_text())
    assert pane == "w6:p1" and data["workspace_id"] == "w6"
    assert data["workers"]["W1"] == {"role": "layer", "state": "busy", "task": "layer-headless", "pane_id": "w6:p1"}

def test_choose_account_without_headroom_blocks(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1"])
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: {"accounts": [acc("claude1", 1, session=99)]})
    with pytest.raises(SystemExit) as e:
        fleet.choose_account(world.sd, "sonnet", {"HOME": "/u"})
    assert e.value.code == 3 and "BLOCKED: no account with headroom" in capsys.readouterr().out

def test_off_from_inside_the_workspace_writes_state_first(world, capsys):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    world.fh.close_workspace = _killed
    with pytest.raises(KeyboardInterrupt):
        fleet.main(["off"])
    assert not (world.sd / "fleet.json").exists() and "fleet: off" in capsys.readouterr().out

def test_stop_of_the_last_worker_clears_the_workspace_first(world):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    world.fh.close_workspace = _killed
    with pytest.raises(KeyboardInterrupt):
        fleet.stop(world.sd, ["W1"])
    data = json.loads((world.sd / "fleet.json").read_text())
    assert data["workspace_id"] is None and data["workers"]["W1"]["state"] == "stopped"

def test_run_is_delegated_to_fleet_layer(world, monkeypatch):
    seen = []
    monkeypatch.setitem(sys.modules, "fleet_layer", types.SimpleNamespace(main=lambda argv: seen.append(argv) or 0))
    assert fleet.main(["run", "--layer", "headless", "--plan", str(world.plan)]) == 0
    assert seen == [["--layer", "headless", "--plan", str(world.plan)]]

def test_status_names_non_implementer_roles(world, capsys):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    fleet.spawn(world.sd, world.plan, None, world.proj, role="package-reviewer")
    capsys.readouterr(); fleet.main(["status"])
    lines = capsys.readouterr().out.splitlines()
    assert lines[1].startswith("W1 ready") and "role=" not in lines[1]
    assert lines[2].startswith("W2 ready") and lines[2].endswith(" role=package-reviewer")
