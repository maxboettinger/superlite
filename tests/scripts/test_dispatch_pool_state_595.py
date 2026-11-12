"""#595: dispatch counts busy fleet workers' tasks as running and gives a plan task that is the Wave 0 the `wave0` line."""
import json
import sys

import pytest

from test_plan_tools import SCRIPTS, make_plan
from test_fleet import world  # noqa: F401  (fixture)
from test_fleet_for_dispatch import dwld, brief_calls  # noqa: F401  (fixtures)
from test_fleet_for_dispatch import _go

sys.path.insert(0, str(SCRIPTS))
import dispatch  # noqa: E402
import wave0  # noqa: E402


def fleet(sd, workers, on=True):
    sd.mkdir(exist_ok=True)
    (sd / "fleet.json").write_text(json.dumps({"on": on, "workers": workers, "next": 9, "accounts": []}), encoding="utf-8")


def w0json(sd, **d):
    (sd / "briefs").mkdir(parents=True, exist_ok=True)
    (sd / "briefs" / "wave0.json").write_text(json.dumps(d), encoding="utf-8")


def test_pending_info_returns_the_record(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T3"}])
    rec = {"id": "T3", "synthetic": False, "owns": ["pyproject.toml"], "wait": ["T4"]}
    w0json(tmp_path / ".superlite", **rec)
    assert wave0.pending_info(str(plan)) == rec


def test_pending_info_none_without_record(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T3"}])
    assert wave0.pending_info(str(plan)) is None


def test_fleet_running_lists_implementer_tasks(tmp_path):
    fleet(tmp_path, {"W1": {"state": "busy", "task": "T2,T3", "role": "implementer"},
                     "W2": {"state": "busy", "task": "FR1", "role": "final-reviewer"}})
    assert dispatch.fleet_running(tmp_path, ["T3"]) == ["T2"]


def test_fleet_running_off_or_absent(tmp_path):
    assert dispatch.fleet_running(tmp_path) == []
    fleet(tmp_path, {"W1": {"state": "busy", "task": "T2", "role": "implementer"}}, on=False)
    assert dispatch.fleet_running(tmp_path) == []


def test_fleet_running_counts_blocked_and_missing_role(tmp_path):
    fleet(tmp_path, {"W1": {"state": "blocked", "task": "T2"}, "W2": {"state": "ready", "task": "T5"},
                     "W3": {"state": "busy", "task": "T2,T4"}})
    assert dispatch.fleet_running(tmp_path) == ["T2", "T4"]


def _world(tmp_path, tasks=("T1", "T2"), edges=()):
    plan = make_plan(tmp_path, [{"id": t, "owns": f"src/{t.lower()}.py"} for t in tasks], edges=edges)
    sd = tmp_path / ".superlite"
    sd.mkdir(exist_ok=True)
    (sd / "pool.json").write_text(json.dumps({"agents": [
        {"id": "W2", "tier": "sonnet", "tasks": [], "files": [], "context_k": 20, "idle_min": 1, "busy": False}]}), encoding="utf-8")
    ledger = sd / "progress.md"
    ledger.write_text("", encoding="utf-8")
    return plan, sd, ledger


def test_commit_dispatch_never_reoffers_a_fleet_busy_task(tmp_path):
    plan, sd, ledger = _world(tmp_path)
    fleet(sd, {"W1": {"state": "busy", "task": "T2", "role": "implementer"}})
    lines, _ = dispatch.run(str(plan), str(sd / "pool.json"), str(ledger), gate=False)
    assert lines and not any("T2" in t.split(",") for t, _ in lines)
    assert any("T1" in t.split(",") for t, _ in lines)


def test_explicit_running_ignores_fleet(tmp_path):
    plan, sd, ledger = _world(tmp_path)
    fleet(sd, {"W1": {"state": "busy", "task": "T2", "role": "implementer"}})
    lines, _ = dispatch.run(str(plan), str(sd / "pool.json"), str(ledger), running="", gate=False)
    assert any("T2" in t.split(",") for t, _ in lines)


def test_plan_task_wave0_line_first(tmp_path):
    plan, sd, ledger = _world(tmp_path, edges=[("T2", "T1")])
    w0json(sd, id="T1", synthetic=False, owns=["src/t1.py"])
    lines, _ = dispatch.run(str(plan), str(sd / "pool.json"), str(ledger), gate=False)
    assert lines[0][0] == "T1" and lines[0][1].startswith("wave0 tier=haiku agent=")
    assert [t for t, _ in lines].count("T1") == 1 and not any("T1" in t.split(",") for t, _ in lines[1:])


def test_skip_ruling_for_plan_task_wave0(tmp_path):
    plan, sd, ledger = _world(tmp_path)
    w0json(sd, id="T1", synthetic=False, owns=["src/t1.py"])
    ledger.write_text("- Ruling: skip T1 - not needed - cost: none\n", encoding="utf-8")
    lines, _ = dispatch.run(str(plan), str(sd / "pool.json"), str(ledger), gate=False)
    assert not any(d.startswith("wave0") for _, d in lines)
    assert any("T1" in t.split(",") for t, _ in lines)


def test_skip_t0_names_the_task(tmp_path):
    f = tmp_path / "l.md"
    f.write_text("- Ruling: skip T1 - x\n", encoding="utf-8")
    assert dispatch.skip_t0(f, None, "T1") is True
    assert dispatch.skip_t0(f) is False


@pytest.mark.skipif(__import__("os").environ.get("SUPERLITE_REAL") == "1", reason="scripted dispatch lines need the in-process fake")
def test_for_dispatch_sends_wave0_brief_under_task_id(dwld, capsys, brief_calls):  # noqa: F811
    import fleet
    fleet.main(["on"])
    sd = dwld.sd.resolve()
    (sd / "briefs").mkdir()
    (sd / "briefs" / "wave0.md").write_text("wave 0 brief\n")
    dwld.lines = [("T3", "wave0 tier=haiku agent=superlite:implementer-haiku")]
    assert _go(dwld) == 0
    assert brief_calls == [(sd, "W1", str(sd / "briefs" / "wave0.md"), "T3")]


def test_skip_ruling_matches_whole_task_id(tmp_path):
    f = tmp_path / "l.md"
    f.write_text("- Ruling: skip T10 - x\nRuling: skip T0 - y\n", encoding="utf-8")
    assert dispatch.skip_t0(f, None, "T1") is False
    assert dispatch.skip_t0(f, None, "T10") is True
    assert dispatch.skip_t0(f) is True
    f.write_text("- Ruling: skip T1 - x\n", encoding="utf-8")
    assert dispatch.skip_t0(f, None, "T1") is True
    assert dispatch.skip_t0(f, None, "T10") is False


def test_fleet_running_ignores_workers_moved_in_from_another_run(tmp_path):
    sd = tmp_path / ".superlite"
    other = tmp_path / "other" / ".superlite"
    fleet(sd, {"W1": {"state": "busy", "task": "T2", "role": "implementer", "state_dir": str(other)}})
    assert dispatch.fleet_running(sd) == []
    fleet(sd, {"W1": {"state": "busy", "task": "T2", "role": "implementer", "state_dir": str(sd)}})
    assert dispatch.fleet_running(sd) == ["T2"]


def test_dispatch_offers_task_of_a_worker_moved_in_from_another_run(tmp_path):
    plan, sd, ledger = _world(tmp_path)
    other = tmp_path / "other" / ".superlite"
    fleet(sd, {"W1": {"state": "busy", "task": "T2", "role": "implementer", "state_dir": str(other)}})
    lines, _ = dispatch.run(str(plan), str(sd / "pool.json"), str(ledger), gate=False)
    assert any("T2" in t.split(",") for t, _ in lines)
