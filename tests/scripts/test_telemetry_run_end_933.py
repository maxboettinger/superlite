"""orchestrator: the `orchestrator` and `run_end` telemetry lines (#933)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import orchestrator  # noqa: E402
import report  # noqa: E402
import telemetry  # noqa: E402

RUN_ID = "20261116T130500Z-a1b2c3"


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True, capture_output=True, env=env)


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SUPERLITE_TELEMETRY", raising=False)


def make_run(tmp_path, brief=None):
    root = tmp_path / "proj"
    root.mkdir()
    git(root, "init", "-q")
    (root / "f").write_text("x")
    git(root, "add", "f")
    git(root, "commit", "-qm", "c")
    plan = root / "docs" / "plans" / "p.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# plan\n")
    sd = root / ".superlite"
    (sd / "briefs").mkdir(parents=True)
    (sd / "stable.json").write_text(json.dumps({"plan": str(plan), "run_id": RUN_ID}))
    (sd / "progress.md").write_text("p")
    if brief:
        (sd / "briefs" / "lead.md").write_text(brief)
    return root, sd, plan


FAKE = {"headline": {"wall_min": {"projected": 30.0, "actual": 12.5}, "agents": {"projected": 5, "actual": 4}},
        "cost_split": {"total_usd": 3.25}, "critical_path": {"projected_min": 20.0},
        "quality": {"tests": {"passed": 9, "failed": 1}, "first_time_pass": 2, "first_time_n": 3},
        "tasks": [{"task": "T1"}, {"task": "T2"}, {"task": "T3"}]}


@pytest.fixture
def fake_report(monkeypatch):
    monkeypatch.setattr(report, "collect", lambda plan, sd: FAKE)


def last(kind):
    ev = [e for e in telemetry.read_events() if e["kind"] == kind]
    assert ev, f"no {kind} line"
    assert telemetry.validate(ev[-1]) == []
    return ev[-1]


def test_kind_orchestrator_set(tmp_path):
    sd = tmp_path / "sd"
    assert orchestrator.main(["set", "ai", "--by", "main", "--plan", str(sd)]) == 0
    e = last("orchestrator")
    assert (e["mode"], e["by"]) == ("ai", "main")


def test_kind_run_end_done(tmp_path, fake_report):
    root, sd, plan = make_run(tmp_path)
    orchestrator.end(sd)
    e = last("run_end")
    assert (e["outcome"], e["run"], e["wall_s"], e["cost_usd"], e["tasks"]) == ("done", RUN_ID, 750.0, 3.25, 3)
    assert (e["agents"], e["tests_passed"], e["tests_failed"], e["first_time_pass"]) == (4, 9, 1, 2)
    assert (e["projected_min"], e["critical_path_min"]) == (30.0, 20.0)
    run = next((sd / "runs").iterdir())
    assert json.loads((run / "run.json").read_text())["run_id"] == RUN_ID


def test_kind_run_end_stopped(tmp_path, fake_report):
    root, sd, plan = make_run(tmp_path)
    (sd / "stopped.md").write_text("stop")
    orchestrator.end(sd)
    assert last("run_end")["outcome"] == "stopped"


def test_kind_run_end_outcome_flag(tmp_path, fake_report, capsys):
    root, sd, plan = make_run(tmp_path)
    assert orchestrator.main(["end", "--plan", str(plan), "--outcome", "failed"]) == 0
    assert last("run_end")["outcome"] == "failed"


def test_lead_run_end_deferred(tmp_path, fake_report):
    root, sd, plan = make_run(tmp_path, brief="# Lead brief: B9 (topic)\n")
    orchestrator.end(sd)
    assert [e for e in telemetry.read_events() if e["kind"] == "run_end"] == []
    pend = tmp_path / "home" / "telemetry" / "pending" / f"{telemetry.batch_key(root, 'B9')}.json"
    assert pend.is_file()
    assert json.loads(pend.read_text())["run"] == RUN_ID


def test_run_end_missing_report_nulls(tmp_path, monkeypatch):
    def boom(plan, sd):
        raise OSError("no report")
    monkeypatch.setattr(report, "collect", boom)
    root, sd, plan = make_run(tmp_path)
    orchestrator.end(sd)
    e = last("run_end")
    assert e["outcome"] == "done"
    for k in ("wall_s", "cost_usd", "tasks", "agents", "tests_passed", "tests_failed", "first_time_pass"):
        assert e[k] is None


def test_end_output_unchanged(tmp_path, fake_report, capsys):
    root, sd, plan = make_run(tmp_path)
    assert orchestrator.main(["end", "--plan", str(plan)]) == 0
    out = capsys.readouterr()
    assert out.out.startswith("orchestrator: run ended; ") and " files moved to " in out.out
    assert out.out.count("\n") == 1


def test_run_end_grade_fields(tmp_path, fake_report):
    root, sd, plan = make_run(tmp_path)
    reports = sd / "fleet" / "reports"
    reports.mkdir(parents=True)
    for name, label, role, status in (("a", "T1", "implementer", "DONE"), ("b", "F-T1-1", "fixer", "DONE"),
                                      ("c", "FR1", "final-reviewer", "NEEDS_FIXES"), ("d", "FR2", "final-reviewer", "APPROVED")):
        (reports / f"{name}.json").write_text(json.dumps({"label": label, "role": role, "status": status}))
    orchestrator.end(sd)
    e = last("run_end")
    assert (e["fix_rounds"], e["final_verdict"], e["ci_red"], e["questions"]) == (1, "APPROVED", 0, 0)
