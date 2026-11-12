"""#560: fleet spawn gates fixers on the machine-wide cap and registers started workers."""
from test_fleet import fleet, world  # noqa: F401,E402

import machine_load as ml  # noqa: E402


def _gate(monkeypatch, ret):
    calls = []
    monkeypatch.setattr(ml, "gate", lambda *a, **k: calls.append((a, k)) or ret)
    return calls


def test_fixer_spawn_blocked_when_busy(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    _gate(monkeypatch, "machine busy after 0 s: 6 of limit 6")
    capsys.readouterr()
    world.fh.calls.clear()
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "1"]) == 3
    assert capsys.readouterr().out.strip() == "BLOCKED: fleet spawn: machine busy after 0 s: 6 of limit 6; rerun later, or pass --over-limit"
    assert world.fh.calls == []


def test_over_limit_passes_through(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    calls = _gate(monkeypatch, None)
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: {"id": "W1"})
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "1", "--over-limit", "--machine-wait", "5"]) == 0
    (args, _), = calls
    assert args[1] == 5.0 and args[2] is True


def test_default_wait_is_100(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    calls = _gate(monkeypatch, None)
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: {"id": "W1"})
    fleet.main(["spawn", "--role", "fixer", "--tier", "1"])
    assert calls[0][0][1] == 100.0 and calls[0][0][2] is False


def test_implementer_spawn_not_gated(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    calls = _gate(monkeypatch, "busy")
    assert fleet.main(["spawn", "--tier", "sonnet"]) == 0
    assert calls == []


def test_spawn_registers_role(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    reg = []
    monkeypatch.setattr(ml, "register", lambda name, role, root: reg.append((name, role, root)))
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert len(reg) == 1 and reg[0][1] == "implementer" and reg[0][0] and reg[0][2] == str(world.proj)
