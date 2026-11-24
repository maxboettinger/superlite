"""#1121: a Tests: slow task's slow-test minutes join extra_min, so lint SIZE judges it like its fast twin."""
from __future__ import annotations

import argparse
import json
import sys

import pytest

from test_plan_tools import SCRIPTS, make_plan, pt

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402
import predict  # noqa: E402

SHIPPED = predict.CONFIG_DIR / "predictor.json"
TASK = {"id": "T1", "owns": "Sources/App/A.swift, Tests/AppTests/ATests.swift", "components": 1, "loc": 25, "tests": "slow", "model": "sonnet"}


def coef_file(tmp_path, slow=7.0):
    coef = json.loads(SHIPPED.read_text(encoding="utf-8"))
    coef["time"]["slow_tests_min"] = slow
    path = tmp_path / "predictor.json"
    path.write_text(json.dumps(coef), encoding="utf-8")
    return path


def task_of(tmp_path, **kw):
    plan = plan_tools.Plan.load(str(make_plan(tmp_path, [dict(TASK, **kw)])))
    return plan.by_id["T1"]


def live(tmp_path, coef):
    return predict.apply_live(coef, {"tests": {"fast_min": 1.0, "case_s": 0.2, "case_source": "prior"},
                                     "contention": {"factor": 1.0}, "root": str(tmp_path)})


def run(tmp_path, coef, **kw):
    return predict.predict_task(task_of(tmp_path, **kw), predict.load_models(), coef)


def test_slow_minutes_join_extra_min_without_live(tmp_path):
    coef = predict.load_coef(str(coef_file(tmp_path)))
    got, twin = run(tmp_path, coef), run(tmp_path, coef, tests="fast")
    assert got["slow_min"] == 7.0
    assert got["extra_min"] == 7.0
    assert got["est_time_min"] == pytest.approx(8.541, abs=0.001)
    assert got["est_time_min"] - got["extra_min"] == pytest.approx(twin["est_time_min"], abs=0.002)
    assert "slow_min" not in twin and "extra_min" not in twin


def test_shipped_prior_counts_its_slow_minutes(tmp_path):
    got = run(tmp_path, predict.load_coef(str(SHIPPED)))
    assert got["slow_min"] == pytest.approx(0.607, abs=0.001)
    assert got["extra_min"] == got["slow_min"]


def test_live_slow_task_band_equals_fast_twin(tmp_path):
    coef = live(tmp_path, predict.load_coef(str(coef_file(tmp_path))))
    got, twin = run(tmp_path, coef), run(tmp_path, coef, tests="fast")
    assert got["slow_min"] == 5.5
    assert got["test_min"] == 0.0
    assert got["est_time_min"] - got["extra_min"] == pytest.approx(twin["est_time_min"], abs=0.002)


def test_live_shipped_prior_slow_task_has_no_slow_min(tmp_path):
    got = run(tmp_path, live(tmp_path, predict.load_coef(str(SHIPPED))))
    assert "slow_min" not in got and "extra_min" not in got


@pytest.mark.parametrize("mode", ["fast", "build"])
def test_fast_and_build_tasks_get_no_slow_min(tmp_path, mode):
    got = run(tmp_path, predict.load_coef(str(coef_file(tmp_path))), tests=mode)
    assert "slow_min" not in got and "extra_min" not in got


def test_lint_size_leaves_slow_minutes_out(tmp_path):
    cp = pt("lint", "--plan", make_plan(tmp_path, [TASK]), "--coef", coef_file(tmp_path))
    assert "SIZE: T1" not in cp.out, cp.both
    assert "NOTE: T1 predicted 8.5 min, 7.0 of it outside the size band (slow tests); splitting does not shrink it" in cp.out, cp.both


def test_lint_size_still_fires_for_big_slow_work(tmp_path):
    cp = pt("lint", "--plan", make_plan(tmp_path, [dict(TASK, loc=2500)]), "--coef", coef_file(tmp_path))
    assert "SIZE: T1 predicted 6.9 min > 6 max" in cp.out, cp.both


def test_effective_times_fills_parts(tmp_path):
    plan = plan_tools.Plan.load(str(make_plan(tmp_path, [TASK])))
    graph = plan_tools.parse_taskgraph(plan)
    args = argparse.Namespace(coef=str(coef_file(tmp_path)))
    ex: dict = {}
    why: dict = {}
    plan_tools.effective_times(plan, graph, args, extra=ex, parts=why)
    assert ex == {"T1": 7.0}
    assert why == {"T1": ["slow tests"]}


def test_extra_parts_order_and_empty():
    assert plan_tools.extra_parts({"review": {"min": 5.0}, "suite": {"cases": 9}, "slow_min": 1.0}) == ["slow tests", "existing tests", "review rounds"]
    assert plan_tools.extra_parts({"est_time_min": 2.0}) == []
