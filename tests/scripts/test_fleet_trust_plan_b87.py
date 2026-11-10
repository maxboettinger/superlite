# tests/scripts/test_fleet_trust_plan_b87.py: trust dialog after the prime (#515) and a run folder as --plan (#508)
import json, os, sys
import pytest
from test_fleet import world, REAL  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402

D = "Quick safety check\n > No, exit\n   Yes, I trust this folder\n"
needs_fake = pytest.mark.skipif(REAL, reason="scripts herdr replies")


def test_trust_open():
    assert fleet._trust_open(D) is True
    assert fleet._trust_open("Yes, I trust this folder\nREADY\n") is False
    assert fleet._trust_open("READY\n") is False


def _worker(world):
    return json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]


@needs_fake
def test_trust_after_prime_accepted_and_prime_resent(world):
    fleet.main(["on"])
    world.fh.screen, world.fh.screen_after, world.fh.prompt_state = D, "⏺ READY\n", "idle"
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"
    calls = world.fh.calls
    name = next(c[1] for c in calls if c[0] == "start_agent")
    assert ("send_keys", name, ["Down", "Enter"]) in calls
    prompts = [c for c in calls if c[0] == "prompt"]
    assert len(prompts) == 2 and prompts[0][2] == prompts[1][2]
    assert _worker(world)["state"] == "ready"


@needs_fake
def test_trust_dialog_stays_open_names_it(world, capsys):
    fleet.main(["on"])
    world.fh.screen = world.fh.screen_after = D
    world.fh.prompt_state = "idle"
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3
    out = capsys.readouterr().out
    assert f"BLOCKED: W1 no READY: the folder trust dialog is still open in {world.proj}" in out
    assert "accept it once per account" in out
    assert _worker(world)["state"] == "blocked"


@needs_fake
def test_no_dialog_keeps_no_ready(world, capsys):
    fleet.main(["on"])
    world.fh.screen = "nothing\n"
    world.fh.prompt_state = "idle"
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3
    assert "BLOCKED: W1 no READY (pane 64 rows, 73 cols)" in capsys.readouterr().out
    assert not [c for c in world.fh.calls if c[0] == "send_keys"]


@needs_fake
def test_ready_with_trust_text_sends_no_keys(world):
    fleet.main(["on"])
    world.fh.screen = "Yes, I trust this folder\nREADY\n"
    world.fh.prompt_state = "idle"
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"
    assert not [c for c in world.fh.calls if c[0] == "send_keys"]
    assert len([c for c in world.fh.calls if c[0] == "prompt"]) == 1
    assert _worker(world)["state"] == "ready"


@needs_fake
def test_one_turn_role_accepts_trust_after_start(world):
    fleet.main(["on"])
    world.fh.screen = D
    fleet.spawn(world.sd, world.plan, "1", world.proj, role="fixer")
    calls = world.fh.calls
    names = [c[0] for c in calls]
    assert "prompt" not in names
    i = names.index("start_agent")
    keys = [c for c in calls[i:] if c[0] == "send_keys"]
    assert keys and keys[0][2] == ["Down", "Enter"]


@needs_fake
@pytest.mark.parametrize("flag,attr", [(["--for-dispatch"], "for_dispatch"), (["--for-review", "T1"], "for_review")])
def test_for_dispatch_resolves_run_folder(world, monkeypatch, flag, attr):
    fleet.main(["on"])
    (world.sd / "stable.json").write_text(json.dumps({"plan": str(world.plan)}))
    seen = []
    monkeypatch.setattr(fleet, attr, lambda sd, plan, *a, **k: seen.append(plan) or 0)
    fleet.main(["spawn", *flag, "--plan", str(world.sd)])
    assert seen == [str(world.plan)]


@needs_fake
def test_run_folder_without_plan_is_exit_2(world, monkeypatch, capsys):
    fleet.main(["on"])
    (world.sd / "prime.md").unlink(missing_ok=True)
    assert fleet.main(["spawn", "--for-dispatch", "--plan", str(world.sd)]) == 2
    err = capsys.readouterr().err
    assert (f"error: --plan {world.sd} is a run folder with no plan file (stable.json, pool.json or plan.md name none); "
            "pass the plan file") in err
    assert not [c for c in world.fh.calls if c[0] == "start_agent"]
    assert not json.loads((world.sd / "fleet.json").read_text()).get("workers")


@needs_fake
def test_one_turn_role_failed_screen_read_does_not_block_spawn(world, monkeypatch):
    fleet.main(["on"])

    def boom(*a, **k):
        raise fleet.hc.HerdrError("read_failed", "no screen")

    monkeypatch.setattr(fleet.hc, "read_screen", boom)
    assert fleet.spawn(world.sd, world.plan, "1", world.proj, role="fixer")["id"] == "W1"
