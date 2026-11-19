"""#787: lint SIZE compares the predicted minutes without the suite and review extras; the forecast cost includes review."""
from __future__ import annotations

import argparse
import sys

from test_plan_tools import SCRIPTS, make_plan, pt

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402

FOCUS = "## Review Focus\n\n- auth: protocol, state; security review required\n"
OWNS = "src/auth/login.py, tests/test_login.py"
TASK = {"id": "T1", "owns": OWNS, "components": 1, "loc": 100, "tests": "fast", "model": "sonnet"}
NOTE = "NOTE: T1 predicted 6.7 min, 5.0 of it outside the size band (existing tests, review rounds); splitting does not shrink it"


def flagged(tmp_path, **kw):
    return make_plan(tmp_path, [dict(TASK, **kw)], header=FOCUS)


def test_review_minutes_do_not_trigger_size(tmp_path):
    cp = pt("lint", "--plan", flagged(tmp_path))
    assert "SIZE: T1" not in cp.out, cp.both
    assert NOTE in cp.out


def test_size_still_fires_for_big_work(tmp_path):
    cp = pt("lint", "--plan", make_plan(tmp_path, [dict(TASK, loc=2500)]))
    assert "SIZE: T1 predicted 6.9 min > 6 max" in cp.out, cp.both


def test_effective_times_passes_plan_and_fills_extra(tmp_path):
    plan = plan_tools.Plan.load(str(flagged(tmp_path)))
    graph = plan_tools.parse_taskgraph(plan)
    args = argparse.Namespace()
    ex: dict = {}
    times, _ = plan_tools.effective_times(plan, graph, args, extra=ex)
    assert round(times["T1"], 3) == 6.704
    assert ex == {"T1": 5.0}
    assert plan_tools.effective_times(plan, graph, args)[0] == times


def test_forecast_cost_includes_review(tmp_path):
    cp = pt("lint", "--stable", "--plan", flagged(tmp_path), cwd=tmp_path)
    line = next(ln for ln in cp.out.splitlines() if "predicted:" in ln)
    assert "$0.43" in line, cp.both
