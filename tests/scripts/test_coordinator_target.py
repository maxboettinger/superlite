"""#112: the coordinator has a measured cost target per committed task: the report shows the cost per task against
it, and the budget line hints when the run is above it (from 3 committed tasks on)."""
from __future__ import annotations

import sys

import pytest

from test_plan_tools import SCRIPTS
from test_routing import mech_plan

sys.path.insert(0, str(SCRIPTS))
import budget  # noqa: E402
import metrics  # noqa: E402
import report  # noqa: E402


def _collected(co_usd, n_tasks):
    """The shape `report.collect` returns, reduced to what `render` reads for the cost split."""
    tasks = [{"task": f"T{i}", "model": "sonnet", "pred_min": 1.0, "actual_min": 1.0, "delta": {"abs": 0.0, "pct": 0.0},
              "cost_usd": 0.1, "first_time_pass": True} for i in range(1, n_tasks + 1)]
    return {"projection_note": "projection: n/a",
            "headline": {k: {"projected": None, "actual": 1} for k in ("wall_min", "cost_usd_agents", "task_min", "agents")},
            "cost_split": {"agents_usd": 0.4, "rework_usd": 0.0, "coordinator_usd": co_usd, "coordinator_session_usd": None,
                           "coordinator": None, "total_usd": 0.4 + (co_usd or 0.0)},
            "concurrency": {"peak": 1, "projected_peak": None},
            "critical_path": {"actual": [], "projected": None, "projected_min": None},
            "model_mix": {}, "coordinator_cost_by_model": None,
            "quality": {"tests": None, "first_time_pass": n_tasks, "first_time_n": n_tasks, "rework_dispatches": 0, "open_incidents": 0},
            "tasks": tasks}


def test_report_shows_per_task_cost():
    txt = report.render(_collected(6.0, 4))
    split = next(ln for ln in txt.splitlines() if ln.startswith("cost split:"))
    assert "coordinator per task $1.50 (target $1.00)" in split


def test_report_without_tasks_omits_the_per_task_line():
    split = next(ln for ln in report.render(_collected(6.0, 0)).splitlines() if ln.startswith("cost split:"))
    assert "per task" not in split
    split = next(ln for ln in report.render(_collected(None, 4)).splitlines() if ln.startswith("cost split:"))
    assert "per task" not in split  # no coordinator transcript: nothing to divide


def test_target_constant_is_shared():
    assert budget.COORDINATOR_TARGET_USD == 1.00 and report.COORDINATOR_TARGET_USD is budget.COORDINATOR_TARGET_USD


def _budget_for(tmp_path, monkeypatch, co_usd, committed):
    p = mech_plan(tmp_path, 4)
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "progress.md").write_text("".join(f"- commit T{i} abc{i}\n" for i in range(1, committed + 1)), encoding="utf-8")
    co = {"cost_usd": co_usd, "turns": 5, "context_median": 1_000, "context_peak": 2_000, "session": {"cost_usd": co_usd}}
    monkeypatch.setattr(metrics, "coordinator_record", lambda *a, **k: co)
    monkeypatch.setattr(metrics, "agents_cost", lambda *a, **k: 0.5)
    return budget.compute(p, sl)


def test_budget_hint_above_target(tmp_path, monkeypatch):
    b = _budget_for(tmp_path, monkeypatch, 4.5, 3)  # $1.50 per committed task
    assert b["hint"] and "$1.50 per committed task" in b["hint"] and "$1.00" in b["hint"]
    assert "$1.50 per committed task" in budget.line(b)


@pytest.mark.parametrize("co_usd,committed", [(2.7, 3), (6.0, 2)])  # $0.90 per task; above target but only 2 committed tasks
def test_budget_no_hint_below_target_or_under_three_tasks(tmp_path, monkeypatch, co_usd, committed):
    b = _budget_for(tmp_path, monkeypatch, co_usd, committed)
    assert not b["hint"] or "per committed task" not in b["hint"]
