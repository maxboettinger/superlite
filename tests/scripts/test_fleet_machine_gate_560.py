"""#560, #643: every fleet spawn passes the machine gate; fleet status shows the machine line."""
import pytest
from test_fleet import fleet, world  # noqa: F401,E402

import machine_load as ml  # noqa: E402

BUSY = "machine busy after 0 s: memory 10% free, floor 15% (23 agents, about 0.7 GB each)"
LINE = "machine: memory 81% free, floor 15% (15 agents, about 0.6 GB each); no count cap"


def _gate(monkeypatch, ret):
    calls = []
    monkeypatch.setattr(ml, "gate", lambda *a, **k: calls.append((a, k)) or ret)
    return calls


def test_fixer_spawn_blocked_when_busy(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    _gate(monkeypatch, BUSY)
    capsys.readouterr()
    world.fh.calls.clear()
    with pytest.raises(SystemExit) as e:
        fleet.main(["spawn", "--role", "fixer", "--tier", "1"])
    assert e.value.code == 3
    assert capsys.readouterr().out.strip() == f"BLOCKED: fleet spawn: {BUSY}; rerun later, or pass --over-limit"
    assert world.fh.calls == []


def test_implementer_spawn_is_gated(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    calls = _gate(monkeypatch, BUSY)
    with pytest.raises(SystemExit):
        fleet.main(["spawn", "--tier", "sonnet"])
    assert len(calls) == 1 and calls[0][0][0] == "fleet spawn (implementer)"


def test_over_limit_and_wait_reach_the_gate(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    calls = _gate(monkeypatch, None)
    monkeypatch.setattr(fleet, "_spawn", lambda *a, **k: {"id": "W1"})
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "1", "--over-limit", "--machine-wait", "5"]) == 0
    (args, _), = calls
    assert args[1] == 5.0 and args[2] is True


def test_default_wait_is_100(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    calls = _gate(monkeypatch, None)
    monkeypatch.setattr(fleet, "_spawn", lambda *a, **k: {"id": "W1"})
    fleet.main(["spawn", "--role", "fixer", "--tier", "1"])
    assert calls[0][0][1] == 100.0 and calls[0][0][2] is False


def test_retry_is_not_gated_again(world, monkeypatch):
    calls = _gate(monkeypatch, None)
    seen = []

    def fake(sd, plan, tier, project, cfg, env, role, after):
        seen.append(after)
        if after is None:
            raise fleet._Slow("W1", "claude1", "slow")
        return {"id": "W2"}
    monkeypatch.setattr(fleet, "_spawn", fake)
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W2"
    assert len(calls) == 1 and len(seen) == 2


def test_spawn_quiet_reports_machine_busy(world, monkeypatch):
    _gate(monkeypatch, BUSY)
    w, why = fleet._spawn_quiet(world.sd, world.plan, "sonnet", world.proj, False, 0.0)
    assert w is None and why == f"fleet spawn: {BUSY}; rerun later, or pass --over-limit"


def test_spawn_writes_no_registry(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    _gate(monkeypatch, None)
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert not (ml.home() / "load").exists()


def test_status_prints_machine_line(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    monkeypatch.setattr(ml, "enabled", lambda: True, raising=False)
    monkeypatch.setattr(ml, "snapshot_text", lambda: LINE)
    capsys.readouterr()
    fleet.main(["status"])
    assert LINE in capsys.readouterr().out.splitlines()


def test_status_without_checks_has_no_machine_line(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    monkeypatch.setattr(ml, "enabled", lambda: False, raising=False)
    monkeypatch.setattr(ml, "snapshot_text", lambda: pytest.fail("no measurement when both checks are off"))
    capsys.readouterr()
    fleet.main(["status"])
    assert not any(x.startswith("machine:") for x in capsys.readouterr().out.splitlines())
