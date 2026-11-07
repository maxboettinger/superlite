# tests/scripts/test_fleet_spawn_shell_retry.py
"""#295: `fleet spawn` retries once, after a pause, a pane that is not a shell yet (a freed pane after an evict)."""
import json, os, types
import pytest
from test_fleet import world  # noqa: F401
from test_fleet_for_dispatch import dwld, FRESH, _go  # noqa: F401
import fleet
import fleet_io
REAL = os.environ.get("SUPERLITE_REAL") == "1"
MSG = "agent target pane w6:p1 is not an available shell"
pytestmark = pytest.mark.skipif(REAL, reason="scripted start failures need the in-process fake")


def script(w, plan):
    """Wrap start_agent: call number n (1-based) raises HerdrError(*plan[n]) when scripted, else the original."""
    orig, n = w.fh.start_agent, [0]
    def start(*a, **k):
        n[0] += 1
        if n[0] in plan:
            w.fh.calls.append(("start_agent", a[0], a[2]))
            raise w.fh.HerdrError(*plan[n[0]])
        return orig(*a, **k)
    w.fh.start_agent = start


def starts(w):
    return [c for c in w.fh.calls if c[0] == "start_agent"]


@pytest.fixture
def pauses(monkeypatch):
    p = []
    monkeypatch.setattr(fleet, "_pause", p.append)
    return p


def test_spawn_retries_once_after_a_pause(world, pauses):
    fleet.main(["on"]); script(world, {1: ("agent_start_failed", MSG)})
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "ready"
    assert len(starts(world)) == 2 and pauses == [fleet.SHELL_PAUSE_S]
    assert [c for c in world.fh.calls if c[0] == "split_pane" or c[0] == "create_workspace"].__len__() <= 1


def test_second_shell_failure_blocks(world, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    script(world, {1: ("agent_start_failed", MSG), 2: ("agent_start_failed", MSG)})
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3
    line = capsys.readouterr().out.splitlines()[0]
    assert line.startswith("BLOCKED: W1 account ") and line.endswith(f"startup: {MSG}; retried once")
    assert len(starts(world)) == 2 and len(pauses) == 1
    assert any(c[0] == "close_pane" for c in world.fh.calls)


def test_other_startup_errors_are_not_retried(world, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    world.fh.start_error = "agent_not_ready"; world.fh.screen = "Select login method\n"
    with pytest.raises(SystemExit):
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    out = capsys.readouterr().out
    assert out.startswith("BLOCKED: ") and "retried once" not in out
    assert len(starts(world)) == 1 and pauses == []


def test_retry_then_trust_dialog(world, pauses):
    fleet.main(["on"]); world.fh.screen = f"{fleet.TRUST}\nREADY\n"
    script(world, {1: ("agent_start_failed", MSG), 2: ("agent_not_ready", "blocked during startup")})
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"
    assert ("send_keys", fleet.fs.agent_name(world.sd, "W1"), ["Down", "Enter"]) in world.fh.calls
    assert len(starts(world)) == 2 and len(pauses) == 1


def test_for_dispatch_names_the_rerun(dwld, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    script(dwld, {1: ("agent_start_failed", MSG), 2: ("agent_start_failed", MSG)})
    dwld.lines = [("T2", FRESH), ("T3", FRESH)]
    assert _go(dwld) == 3
    out = capsys.readouterr().out.splitlines()
    assert out[0].startswith("BLOCKED: T2 not sent (") and out[0].endswith("is not an available shell; retried once; rerun sl fleet spawn --for-dispatch)")
    assert out[1:] == ["W2 T3 sent"]


def test_for_dispatch_retry_success_sends(dwld, pauses, capsys):
    fleet.main(["on"]); capsys.readouterr()
    script(dwld, {1: ("agent_start_failed", MSG)})
    dwld.lines = [("T2", FRESH)]
    assert _go(dwld) == 0
    assert capsys.readouterr().out.splitlines() == ["W1 T2 sent"]


def test_pause_defaults(monkeypatch):
    assert fleet.SHELL_PAUSE_S == 3.0
    seen = []
    monkeypatch.setattr(fleet, "time", types.SimpleNamespace(sleep=seen.append))
    fleet._pause(1.5)
    assert seen == [1.5]
