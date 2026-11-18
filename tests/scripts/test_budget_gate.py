"""dispatch and fleet spawn refuse while the budget gate says paused; a failing gate fails open."""
from __future__ import annotations

import json
import sys

from test_dispatch_evict import pool_file
from test_fleet import fleet, world  # noqa: F401,E402  (world is a fixture)
from test_plan_tools import SCRIPTS
from test_routing import mixed

sys.path.insert(0, str(SCRIPTS))
import budget  # noqa: E402
import dispatch as dispatchmod  # noqa: E402

LINE = "budget: paused: x"


def go(tmp_path, capsys):
    p = mixed(tmp_path)
    pool = pool_file(tmp_path, [])
    rc = dispatchmod.main(["--plan", str(p), "--pool", str(pool), "--ledger", str(tmp_path / ".superlite" / "progress.md")])
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_dispatch_refuses_while_paused(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(budget, "gate", lambda *a, **k: LINE)
    rc, out, err = go(tmp_path, capsys)
    assert rc == 3 and out == ""
    assert f"dispatch: BLOCKED: {LINE}" in err


def test_dispatch_runs_when_gate_is_none(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(budget, "gate", lambda *a, **k: None)
    rc, out, err = go(tmp_path, capsys)
    assert rc == 0 and any(ln.startswith("T1 ") for ln in out.splitlines())


def test_dispatch_gate_error_fails_open(tmp_path, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("x")
    monkeypatch.setattr(budget, "gate", boom)
    rc, out, err = go(tmp_path, capsys)
    assert rc == 0 and "BLOCKED" not in err


def workers(world):
    f = world.sd / "fleet.json"
    return json.loads(f.read_text()).get("workers", {}) if f.is_file() else {}


def test_fleet_spawn_refuses_before_any_pane(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    capsys.readouterr()
    monkeypatch.setattr(budget, "gate", lambda *a, **k: LINE)
    world.fh.calls.clear()
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "sonnet", "--plan", str(world.plan)]) == 3
    assert capsys.readouterr().out.strip() == f"BLOCKED: fleet spawn: {LINE}"
    assert world.fh.calls == [] and workers(world) == {}


def test_fleet_for_dispatch_and_for_review_refuse(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    monkeypatch.setattr(budget, "gate", lambda *a, **k: LINE)
    for extra in (["--for-dispatch"], ["--for-review", "T1"]):
        capsys.readouterr()
        assert fleet.main(["spawn", *extra, "--plan", str(world.plan)]) == 3
        assert capsys.readouterr().out.strip() == f"BLOCKED: fleet spawn: {LINE}"
    assert workers(world) == {}


def test_fleet_spawn_without_a_plan_is_not_gated(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    capsys.readouterr()
    calls = []
    monkeypatch.setattr(budget, "gate", lambda *a, **k: calls.append(a) or LINE)
    assert fleet.main(["spawn", "--role", "fixer", "--tier", "sonnet"]) == 0
    assert calls == [] and "W1 account=" in capsys.readouterr().out
