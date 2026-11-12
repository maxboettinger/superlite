"""#605 end to end: schedule, lint and predict read a project's test-run minutes and the machine's other runs."""
from __future__ import annotations

import json
import os
import sys

import pytest

from test_plan_tools import PREDICT, SCRIPTS, make_plan, pt, run

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402


def live_project(tmp_path, monkeypatch, run_min):
    monkeypatch.setenv("SUPERLITE_FORECAST_LIVE", "1")
    root = tmp_path / "proj"
    (root / ".superlite").mkdir(parents=True)
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps({"test": "true", "run_min": run_min}), encoding="utf-8")
    plan = make_plan(root, [{"id": "T1", "features": "components=1 · loc=100 · tests=fast · model=sonnet"}])
    return root, plan


def schedule(plan, cwd):
    cp = pt("schedule", "--plan", plan, "--json", cwd=cwd)
    assert cp.returncode == 0, cp.both
    return json.loads(cp.out)


def test_schedule_adds_the_test_runs_and_the_full_run(tmp_path, monkeypatch):
    root, plan = live_project(tmp_path, monkeypatch, {"fast": 6, "full": 12})
    got = schedule(plan, root)
    monkeypatch.setenv("SUPERLITE_FORECAST_LIVE", "0")
    base = schedule(plan, root)
    assert got["tasks"]["T1"]["min"] == pytest.approx(base["tasks"]["T1"]["min"] + 16.5, abs=0.01)
    assert got["tail_min"] == pytest.approx(base["tail_min"] + 11.0)


def test_lint_keeps_the_size_band_above_the_test_runs(tmp_path, monkeypatch):
    root, plan = live_project(tmp_path, monkeypatch, {"fast": 6, "full": 12})
    cp = pt("lint", "--plan", plan, cwd=root)
    assert "SIZE:" not in cp.both, cp.both


def test_another_live_run_makes_the_full_run_wait(tmp_path, monkeypatch):
    root, plan = live_project(tmp_path, monkeypatch, {"fast": 6, "full": 12})
    other = tmp_path / "other" / ".superlite"
    other.mkdir(parents=True)
    (other / "stable.json").write_text("{}", encoding="utf-8")
    binding = state.home() / "sessions" / "other-session"
    binding.parent.mkdir(parents=True, exist_ok=True)
    binding.write_text(f"{other}\n{os.getpid()}\n{other.parent}\n", encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_FORECAST_LIVE", "0")
    base = schedule(plan, root)["tail_min"]
    monkeypatch.setenv("SUPERLITE_FORECAST_LIVE", "1")
    assert schedule(plan, root)["tail_min"] == pytest.approx(base + 12.0 * 1.5 - 1.0)


def test_predict_json_names_the_live_inputs(tmp_path, monkeypatch):
    root, plan = live_project(tmp_path, monkeypatch, 6)
    cp = run(PREDICT, "--plan", plan, cwd=root)
    assert cp.returncode == 0, cp.both
    out = json.loads(cp.out)
    assert out["live"]["tests"]["fast_source"] == "test-cmd.json"
    assert out["tasks"]["T1"]["test_min"] == pytest.approx(16.5)
