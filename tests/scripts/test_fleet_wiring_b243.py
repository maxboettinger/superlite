"""#902/#909 wiring in fleet.py: --over-limit bounds and rank reach the machine gate, live_workers, the not-sent line,
the skipped-accounts line and the waits-on suffix of `fleet status`."""
import json
import sys

import pytest
from test_fleet import world  # noqa: F401
from test_accounts import acc
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_state as fs  # noqa: E402
import fleet_waits  # noqa: E402


def put(sd, **states):
    with fs.locked(sd):
        d = fs.load(sd)
        for wid, st in states.items():
            d["workers"][wid] = {"id": wid, "state": st, "pane_id": "p" + wid, "account": "claude3", "role": "implementer"}
        fs.save(sd, d)


def test_bound_without_over_limit_exits_2(world, monkeypatch, capsys):
    fleet.main(["on"]); capsys.readouterr()
    monkeypatch.setattr(fleet.ml, "gate", lambda *a, **k: pytest.fail("gate ran"))
    assert fleet.main(["spawn", "--role", "research", "--max-workers", "6", "--plan", str(world.sd)]) == 2
    assert "error: --max-workers and --min-swap-free-mb bound --over-limit; pass --over-limit too" in capsys.readouterr().err


def test_bounds_and_rank_reach_gate(world, monkeypatch):
    fleet.main(["on"])
    put(world.sd, W1="busy", W2="stopped")
    calls = []
    monkeypatch.setattr(fleet.ml, "gate", lambda what, wait, over=False, **k: calls.append((over, k)) or None)
    monkeypatch.setattr(fleet, "_spawn", lambda *a, **k: {"id": "W9"})
    fleet.main(["spawn", "--role", "research", "--over-limit", "--max-workers", "6", "--min-swap-free-mb", "1024", "--plan", str(world.sd)])
    rw = calls[-1][1].pop("run_workers")
    assert calls[-1] == (True, {"rank": 1, "bounds": {"max_workers": 6, "min_swap_free_mb": 1024}})
    assert callable(rw) and rw() == fleet.live_workers(world.sd)
    assert fleet.live_workers(world.sd) == 1
    for role in ("package-reviewer", "final-reviewer"):
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj, role=role)
        assert calls[-1][1]["rank"] == 0 and calls[-1][1]["bounds"] is None and calls[-1][1]["run_workers"] is None


def test_live_workers_example(world):
    fleet.main(["on"])
    put(world.sd, W1="busy", W2="ready", W3="stopped", W4="blocked", W5="starting")
    assert fleet.live_workers(world.sd) == 3


def test_for_dispatch_and_for_review_pass_bounds(world, monkeypatch, capsys):
    fleet.main(["on"]); capsys.readouterr()
    seen = []
    monkeypatch.setattr(fleet, "for_dispatch", lambda *a, **k: seen.append(("dispatch", k.get("bounds"))) or 0)
    monkeypatch.setattr(fleet, "for_review", lambda *a, **k: seen.append(("review", k.get("bounds"))) or 0)
    b = {"max_workers": 6, "min_swap_free_mb": None}
    fleet.main(["spawn", "--for-dispatch", "--over-limit", "--max-workers", "6", "--plan", str(world.plan)])
    fleet.main(["spawn", "--for-review", "T1", "--over-limit", "--max-workers", "6", "--plan", str(world.plan)])
    assert seen == [("dispatch", b), ("review", b)]
    # the dispatch round's fresh lines reach _spawn_quiet with the same bounds
    got = []
    monkeypatch.undo()
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: got.append(k.get("bounds")) or {"id": "W1"})
    fleet._spawn_quiet(world.sd, world.plan, "sonnet", world.proj, True, 0.0, bounds=b)
    assert got == [b]


def test_for_review_blocked_line_names_worker(world, monkeypatch, capsys):
    import fleet_io as fio
    fleet.main(["on"]); capsys.readouterr()
    (world.sd / "progress.md").write_text("- commit T1 abc1234 first\n")
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: put(world.sd, W1="ready") or {"id": "W1"})
    monkeypatch.setattr(fleet, "stop", lambda *a, **k: None)
    monkeypatch.setattr(fio, "review_brief", lambda *a, **k: "BRIEF\n")
    def boom(*a, **k):
        raise fio.hc.HerdrError("x", "stalled")
    monkeypatch.setattr(fio, "send_brief", boom)
    assert fleet.main(["spawn", "--for-review", "T1", "--plan", str(world.plan)]) == 3
    assert "BLOCKED: W1 review-T1 not sent (stalled)" in capsys.readouterr().out


def test_choose_account_prints_skip_line(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    usage = {"accounts": [acc("claude1", 1, weekly_all=100), acc("claude3", 3, weekly_all=3)]}
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: usage)
    capsys.readouterr()
    assert fleet.choose_account(world.sd, "sonnet", {})[0] == "claude3"
    assert "accounts skipped: claude1 (weekly_all 100%)" in capsys.readouterr().err.splitlines()


def test_status_appends_waits(world, monkeypatch, capsys):
    fleet.main(["on"])
    put(world.sd, W1="busy", W2="ready")
    monkeypatch.setattr(fleet, "agent_gone", lambda name: False)
    monkeypatch.setattr(fleet_waits, "suffixes", lambda sd, workers: {"W1": " waits on run_tests --full 8 min"})
    capsys.readouterr()
    fleet.main(["status"])
    lines = capsys.readouterr().out.splitlines()
    assert next(l for l in lines if l.startswith("W1 busy")).endswith(" waits on run_tests --full 8 min")
    assert not next(l for l in lines if l.startswith("W2 ready")).endswith("min")
    def broken(sd, workers):
        raise RuntimeError("ps failed")
    monkeypatch.setattr(fleet_waits, "suffixes", broken)
    fleet.main(["status"])
    assert next(l for l in capsys.readouterr().out.splitlines() if l.startswith("W1 busy")).endswith("task=-")


def test_fallback_spawn_after_unsent_remote_brief_keeps_bounds(world, monkeypatch):
    import fleet_io as fio
    fleet.main(["on"])
    brief = world.sd / "b.md"; brief.write_text("do it\n")
    seen = []
    def fake_spawn(sd, plan, tier, proj, **k):
        seen.append(k.get("bounds")); return {"id": "W%d" % len(seen)}
    def send(sd, wid, *a, **k):
        if wid == "W1":
            raise OSError("not taken")
    monkeypatch.setattr(fleet, "spawn", fake_spawn)
    monkeypatch.setattr(fleet, "stop", lambda *a, **k: None)
    monkeypatch.setattr(fleet, "_unavailable", lambda *a, **k: None)
    monkeypatch.setattr(fleet, "add_constraints", lambda *a, **k: None)
    monkeypatch.setattr(fio, "send_brief", send)
    monkeypatch.setattr(fleet, "_placed", lambda *a, **k: "box")
    fleet.main(["spawn", "--role", "research", "--over-limit", "--max-workers", "6", "--brief", str(brief), "--plan", str(world.sd)])
    assert len(seen) == 2 and seen[-1] == seen[0] and seen[-1]["max_workers"] == 6
