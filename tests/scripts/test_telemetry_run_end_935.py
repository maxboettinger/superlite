"""run_end carries mode, orchestrator and fleet from the source run_start uses (#935)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest
from test_plan_tools import SCRIPTS, make_plan, pt

sys.path.insert(0, str(SCRIPTS))
import orchestrator  # noqa: E402
import report  # noqa: E402
import telemetry  # noqa: E402

RUN_ID = "20261116T130500Z-a1b2c3"
FAKE = {"headline": {"wall_min": {"projected": 30.0, "actual": 12.5}, "agents": {"projected": 5, "actual": 4}},
        "cost_split": {"total_usd": 3.25}, "critical_path": {"projected_min": 20.0},
        "quality": {"tests": {"passed": 9, "failed": 1}, "first_time_pass": 2, "first_time_n": 3},
        "tasks": [{"task": "T1"}]}
TASKS = [{"id": f"T{i}", "time": 3, "components": 1, "loc": 100, "tests": "fast"} for i in (1, 2, 3)]


@pytest.fixture(autouse=True)
def env(tmp_path, monkeypatch):
    for var in ("SUPERLITE_TELEMETRY", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR",
                "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_WORKER", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(report, "collect", lambda plan, sd: FAKE)


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "-C", str(cwd), "-c", "user.name=t", "-c", "user.email=t@t", *a], check=True,
                   capture_output=True, env=env)


def mode_file(sid, word):
    d = Path(os.environ["SUPERLITE_HOME"]) / "telemetry" / "sessions"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{sid}.mode").write_text(word + "\n", encoding="utf-8")


def tags(sd, orch=None, fleet=None):
    sd.mkdir(parents=True, exist_ok=True)
    if orch:
        (sd / "orchestrator.json").write_text(json.dumps({"mode": orch, "by": "main"}), encoding="utf-8")
    if fleet is not None:
        (sd / "fleet.json").write_text(json.dumps({"on": fleet}), encoding="utf-8")


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
    (sd / "stable.json").write_text(json.dumps({"plan": str(plan), "run_id": RUN_ID, "run_session": "s1"}))
    (sd / "progress.md").write_text("p")
    if brief:
        (sd / "briefs" / "lead.md").write_text(brief)
    return root, sd


def ends():
    out = [e for e in telemetry.read_events() if e["kind"] == "run_end"]
    for e in out:
        assert telemetry.validate(e) == []
    return out


@pytest.fixture
def repo(tmp_path, monkeypatch):
    monkeypatch.setenv("CLAUDECODE", "1")
    r = tmp_path / "lintrepo"
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q", "-b", "feat-x", str(r)], check=True, env=env)
    (r / ".superlite").mkdir()
    return r


def lint(repo, session):
    p = make_plan(repo, TASKS, header="**Detail:** contracts")
    os.environ["CLAUDE_CODE_SESSION_ID"] = session
    try:
        cp = pt("lint", "--stable", "--plan", p, cwd=repo)
    finally:
        del os.environ["CLAUDE_CODE_SESSION_ID"]
    assert cp.returncode == 0, cp.both


def test_run_end_fields_appended():
    assert telemetry.KINDS["run_end"][-4:] == ("reason", "mode", "orchestrator", "fleet")


def test_run_tags_examples(tmp_path, monkeypatch):
    sd = tmp_path / "a" / ".superlite"
    tags(sd, "ai", True)
    mode_file("s1", "feature")
    assert orchestrator.run_tags(sd, "s1") == {"mode": "feature", "orchestrator": "ai", "fleet": True}
    bare = tmp_path / "b" / ".superlite"
    bare.mkdir(parents=True)
    assert orchestrator.run_tags(bare) == {"mode": None, "orchestrator": None, "fleet": False}
    monkeypatch.setenv("SUPERLITE_FLEET_ROLE", "lead")
    assert orchestrator.run_tags(bare)["mode"] == "backlog"


def test_run_tags_lead_brief_wins(tmp_path):
    sd = tmp_path / ".superlite"
    (sd / "briefs").mkdir(parents=True)
    (sd / "briefs" / "lead.md").write_text("# Lead brief: B9 (topic)\n", encoding="utf-8")
    mode_file("s1", "regular")
    assert orchestrator.run_tags(sd, "s1")["mode"] == "backlog"


def test_run_tags_fail_open(tmp_path, monkeypatch):
    import fleet_state
    sd = tmp_path / ".superlite"
    tags(sd, "human", True)

    def boom(_sd):
        raise OSError("disk")
    monkeypatch.setattr(fleet_state, "is_on", boom)
    assert orchestrator.run_tags(sd) == {"mode": None, "orchestrator": "human", "fleet": None}


def test_kind_run_end_carries_run_tags(tmp_path):
    root, sd = make_run(tmp_path)
    tags(sd, "ai", True)
    mode_file("s1", "feature")
    orchestrator.end(sd)
    (e,) = ends()
    assert (e["outcome"], e["mode"], e["orchestrator"], e["fleet"]) == ("done", "feature", "ai", True)


def test_kind_run_end_tags_null_without_sources(tmp_path):
    root, sd = make_run(tmp_path)
    orchestrator.end(sd)
    (e,) = ends()
    assert (e["mode"], e["orchestrator"], e["fleet"]) == (None, None, False)


def test_kind_run_end_lead_deferred_backlog(tmp_path):
    root, sd = make_run(tmp_path, brief="# Lead brief: B9 (topic)\n")
    tags(sd, "ai", True)
    mode_file("s1", "regular")
    orchestrator.end(sd)
    assert ends() == []
    assert telemetry.finish_deferred(telemetry.batch_key(root, "B9"), "shipped")
    (e,) = ends()
    assert (e["outcome"], e["mode"], e["orchestrator"], e["fleet"]) == ("shipped", "backlog", "ai", True)


def test_run_json_carries_run_tags(tmp_path):
    root, sd = make_run(tmp_path)
    tags(sd, "human", False)
    mode_file("s1", "debug")
    orchestrator.end(sd)
    (manifest,) = (root / ".superlite" / "runs").glob("*/run.json")
    m = json.loads(manifest.read_text(encoding="utf-8"))
    assert (m["mode"], m["orchestrator"], m["fleet"]) == ("debug", "human", False)


def test_kind_run_end_abandoned_carries_run_tags(repo):
    lint(repo, "s1")
    (repo / ".superlite" / "session").unlink()  # the first session has ended
    tags(repo / ".superlite", "ai", True)
    mode_file("s1", "debug")
    lint(repo, "s2")
    (e,) = ends()
    assert e["outcome"] == "abandoned"
    assert (e["mode"], e["orchestrator"], e["fleet"]) == ("debug", "ai", True)


def test_kind_run_start_lead_is_backlog(repo):
    (repo / ".superlite" / "briefs").mkdir()
    (repo / ".superlite" / "briefs" / "lead.md").write_text("# Lead brief: B9 (topic)\n", encoding="utf-8")
    mode_file("s1", "regular")
    lint(repo, "s1")
    (s,) = [e for e in telemetry.read_events() if e["kind"] == "run_start"]
    assert telemetry.validate(s) == [] and s["mode"] == "backlog"
