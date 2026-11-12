"""#605: the forecast adds a project's test-run cost, slot contention and an evidence-checked prose factor."""
from __future__ import annotations

import os
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402
import predict  # noqa: E402

SHIPPED = predict.CONFIG_DIR / "predictor.json"


def live(fast=6.0, full=12.0, others=0, full_lock=False, factor=1.0, full_factor=1.0):
    return {"tests": {"fast_min": fast, "full_min": full,
                      "fast_source": "test-cmd.json" if fast is not None else None,
                      "full_source": "test-cmd.json" if full is not None else None,
                      "fast_runs": 0, "full_runs": 0, "slots": None},
            "contention": {"others": others, "full_lock": full_lock, "slots": 2, "factor": factor, "full_factor": full_factor}}


def shipped():
    return predict.load_coef(SHIPPED)


def task(tid="T1", owns="src/a.py, tests/test_a.py", tests="fast", kind=None):
    lines = [f"### {tid} task {tid.lower()} · Complexity 2 · Est. context 30k", f"**Owns:** {owns}", "**Components:** 1",
             "**LOC owned:** 100", f"**Tests:** {tests}", "**Model:** sonnet"]
    if kind:
        lines.append(f"**Kind:** {kind}")
    return "\n".join(lines) + "\n"


def plan_of(*blocks):
    return plan_tools.Plan("# P\n\n**Goal:** test.\n\n" + "\n".join(blocks))


def one(**kw):
    return plan_of(task(**kw)).tasks[0]


def test_a_fast_task_adds_three_runs_less_the_included_minutes():
    models, t = predict.load_models(), one()
    base = predict.predict_task(t, models, shipped())
    got = predict.predict_task(t, models, predict.apply_live(shipped(), live()))
    assert got["est_time_min"] == pytest.approx(base["est_time_min"] + 3 * 6.0 - 3 * 0.5, abs=0.002)
    assert got["test_min"] == pytest.approx(16.5)
    assert "test_min" not in base


def test_a_slow_task_counts_its_slow_tests_minutes_as_included():
    coef = shipped()
    got = predict.predict_task(one(tests="slow"), predict.load_models(), predict.apply_live(coef, live()))
    assert got["test_min"] == pytest.approx(18.0 - 1.5 - coef["time"]["slow_tests_min"], abs=0.001)


def test_a_build_task_counts_one_run():
    got = predict.predict_task(one(tests="build"), predict.load_models(), predict.apply_live(shipped(), live()))
    assert got["test_min"] == pytest.approx(6.0 - 0.5)


def test_contention_scales_the_test_runs():
    got = predict.predict_task(one(), predict.load_models(), predict.apply_live(shipped(), live(others=3, factor=2.0)))
    assert got["test_min"] == pytest.approx(3 * 6.0 * 2.0 - 1.5)


def test_a_cheap_suite_adds_nothing():
    models, t = predict.load_models(), one()
    coef = predict.apply_live(shipped(), live(fast=0.1, full=0.4))
    got, base = predict.predict_task(t, models, coef), predict.predict_task(t, models, shipped())
    assert got["test_min"] == 0.0 and got["est_time_min"] == base["est_time_min"]
    assert coef["schedule"]["tail_min"] == shipped()["schedule"]["tail_min"]
    assert coef["size_band"]["high_min"] == shipped()["size_band"]["high_min"]


def test_the_size_band_rises_by_a_fast_tasks_test_minutes():
    base, coef = shipped(), predict.apply_live(shipped(), live())
    assert coef["size_band"]["high_min"] == pytest.approx(base["size_band"]["high_min"] + 16.5)
    assert coef["size_band"]["low_min"] == base["size_band"]["low_min"]
    assert coef["live"]["task_test_min"] == pytest.approx(16.5)


def test_the_tail_adds_the_full_run_and_its_wait_for_the_lock():
    base = shipped()["schedule"]["tail_min"]
    coef = predict.apply_live(shipped(), live(others=3, full_factor=2.5))
    assert coef["schedule"]["tail_min"] == pytest.approx(base + 12.0 * 2.5 - 1.0)
    assert coef["live"]["tail_add_min"] == pytest.approx(29.0)


def test_unknown_test_minutes_change_nothing_but_are_named():
    models, t = predict.load_models(), one()
    coef = predict.apply_live(shipped(), live(fast=None, full=None, others=2, factor=1.5, full_factor=2.0))
    assert predict.predict_task(t, models, coef)["est_time_min"] == predict.predict_task(t, models, shipped())["est_time_min"]
    assert coef["schedule"]["tail_min"] == shipped()["schedule"]["tail_min"]
    assert coef["size_band"]["high_min"] == shipped()["size_band"]["high_min"]
    assert coef["live"]["contention"]["others"] == 2


def test_the_language_scale_leaves_the_test_minutes_alone():
    models, t = predict.load_models(), one()
    coef = shipped()
    coef["time"]["language_scale"] = 0.5
    base = predict.predict_task(t, models, coef)["est_time_min"]
    got = predict.predict_task(t, models, predict.apply_live(coef, live()))["est_time_min"]
    assert got == pytest.approx(base + 16.5, abs=0.002)


def test_apply_live_does_not_touch_its_input():
    coef = shipped()
    predict.apply_live(coef, live(others=3, full_factor=2.5))
    assert coef == shipped()


def test_strip_live_restores_the_shipped_values():
    assert predict.strip_live(predict.apply_live(shipped(), live(others=3, full_factor=2.5))) == shipped()


def test_a_refit_never_stores_live_values():
    obs = [{"components": 1.0, "loc": float(50 + 10 * i), "slow": False, "model": "sonnet",
            "actual": 1.5 + 0.02 * i, "overhead": None} for i in range(8)]
    new, _ = predict.refit(obs, predict.load_models(), predict.apply_live(shipped(), live(others=3, full_factor=2.5)))
    assert "live" not in new
    assert new["schedule"]["tail_min"] == shipped()["schedule"]["tail_min"]


def test_the_plan_forecast_names_its_live_inputs():
    plan, models = plan_of(task()), predict.load_models()
    out = predict.predict_plan(plan, models, predict.apply_live(shipped(), live()))
    assert out["live"]["tests"]["fast_min"] == 6.0 and out["live"]["task_test_min"] == pytest.approx(16.5)
    assert "base" not in out["live"]
    assert "live" not in predict.predict_plan(plan, models, shipped())


def test_a_task_owning_only_prose_files_is_prose():
    models, coef = predict.load_models(), shipped()
    p = predict.predict_task(one(owns="docs/tools.md, skills/x/SKILL.md"), models, coef)
    c = predict.predict_task(one(), models, coef)
    assert p["features"]["prose"] is True and "prose" not in c["features"]
    assert p["est_time_min"] == pytest.approx(c["est_time_min"] * 2.0, abs=0.002)
    assert p["tokens"]["cache_read"] == pytest.approx(c["tokens"]["cache_read"] * 3.0, rel=0.02)


def test_kind_prose_marks_any_task_and_mechanical_never_is_prose():
    coef = shipped()
    assert predict.is_prose(one(kind="prose"), coef)
    assert not predict.is_prose(one(owns="docs/a.md", kind="mechanical"), coef)


def test_mixed_owns_are_not_prose():
    assert not predict.is_prose(one(owns="docs/a.md, scripts/a.py"), shipped())


def test_prose_extensions_ignore_case():
    assert predict.is_prose(one(owns="README.MD, docs/x.rst, notes.txt"), shipped())


def test_prose_leaves_the_test_minutes_alone():
    models, coef = predict.load_models(), predict.apply_live(shipped(), live())
    p = predict.predict_task(one(owns="docs/a.md"), models, coef)
    c = predict.predict_task(one(), models, coef)
    assert p["test_min"] == c["test_min"] == pytest.approx(16.5)
    assert p["est_time_min"] - 16.5 == pytest.approx((c["est_time_min"] - 16.5) * 2.0, abs=0.003)


@pytest.fixture
def live_on(monkeypatch, tmp_path):
    monkeypatch.setenv(predict.LIVE_ENV, "1")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(predict, "_LIVE_CACHE", {})
    return monkeypatch


def test_load_coef_applies_the_live_inputs(live_on):
    live_on.setattr(predict, "live_inputs", lambda coef: live())
    assert predict.load_coef()["live"]["tests"]["fast_min"] == 6.0


def test_the_env_switch_turns_the_live_inputs_off(live_on):
    live_on.setattr(predict, "live_inputs", lambda coef: live())
    live_on.setenv(predict.LIVE_ENV, "0")
    assert "live" not in predict.load_coef()


def test_an_explicit_coef_file_has_no_live_inputs(live_on):
    live_on.setattr(predict, "live_inputs", lambda coef: live())
    assert "live" not in predict.load_coef(SHIPPED)


def test_a_failing_live_read_never_breaks_a_prediction(live_on):
    def boom(coef):
        raise RuntimeError("probe failed")

    live_on.setattr(predict, "live_inputs", boom)
    assert "live" not in predict.load_coef()


def test_live_inputs_are_read_once_per_window(live_on):
    calls = []
    live_on.setattr(predict, "_read_live", lambda root, coef: calls.append(root) or live())
    predict.load_coef()
    predict.load_coef()
    assert len(calls) == 1


def test_the_script_tests_run_with_the_live_inputs_off():
    assert os.environ.get(predict.LIVE_ENV) == "0"
