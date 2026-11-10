"""`sl status` (#386): the run state in one screen: run folder and owner, orchestrator, plan and its tasks,
fleet workers, budget, last test run, and the resume hint while an agent is busy."""
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
SL = SCRIPTS / "sl"
sys.path.insert(0, str(SCRIPTS))
import budget  # noqa: E402
import status  # noqa: E402

PLAN = "# Plan\n\n**Goal:** g\n\n" + "".join(
    f"### T{i} task {i}\n**Owns:** src/f{i}.py\n**Tests:** fast\n\n" for i in range(1, 6))


def run_folder(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    plan = tmp_path / "p.md"
    plan.write_text(PLAN, encoding="utf-8")
    (sd / "stable.json").write_text(json.dumps({"plan": str(plan)}), encoding="utf-8")
    (sd / "orchestrator.json").write_text(json.dumps({"mode": "ai", "approved": True, "by": "user",
                                                      "time": "2026-11-10T09:00:00"}), encoding="utf-8")
    (sd / "progress.md").write_text("- commit T1 abc1234def one\n- Hold T4: waiting on Max\n", encoding="utf-8")
    (sd / "pool.json").write_text(json.dumps({"agents": [{"id": "a1", "tier": "sonnet", "busy": True, "current": "T2"},
                                                         {"id": "a2", "tier": "sonnet", "busy": False}]}), encoding="utf-8")
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {
        "W1": {"agent": "superlite:implementer", "tier": "sonnet", "state": "busy", "task": "T3"},
        "W2": {"agent": "superlite:researcher", "tier": "sonnet", "state": "ready", "task": None},
        "W3": {"agent": "superlite:implementer", "tier": "sonnet", "state": "stopped", "task": None}}}), encoding="utf-8")
    (sd / "test-summary.json").write_text(json.dumps({"passed": 7, "failed": 1, "skipped": 0, "mode": "fast"}), encoding="utf-8")
    return sd, plan


def ended(sd):
    return datetime.fromtimestamp((sd / "test-summary.json").stat().st_mtime).strftime("%H:%M:%S")


def clean_env(monkeypatch, tmp_path):
    for k in [k for k in os.environ if k.startswith("SUPERLITE_")]:
        monkeypatch.delenv(k)
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.setenv("SUPERLITE_SESSION_ID", "me")


def sl(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k != "CLAUDE_CODE_SESSION_ID"}
    env.update(SUPERLITE_HOME=str(tmp_path / "home"), SUPERLITE_CACHE_DIR=str(tmp_path / "cache"), SUPERLITE_SESSION_ID="me")
    return subprocess.run(["bash", str(SL), *args], capture_output=True, text=True, cwd=tmp_path, env=env)


def test_overview_lines(tmp_path, monkeypatch):
    clean_env(monkeypatch, tmp_path)
    sd, plan = run_folder(tmp_path)
    assert status.overview(sd, plan) == [
        f"run: {sd}; owner: none",
        "orchestrator: AI (set 2026-11-10T09:00:00 by user)",
        f"plan: {plan}: 5 tasks",
        "tasks: checkpointed 1: T1; running 2: T2 (a1), T3 (W1); held 1: T4 (waiting on Max); open 1: T5",
        "fleet: on; W1 implementer busy T3, W2 researcher ready; stopped: W3",
        "budget: no metrics yet",
        f"last test run: fast, 7 passed, 1 failed, ended {ended(sd)}",
        f"after a crash: sl orchestrator resume --plan {sd}",
    ]


def test_overview_without_a_run(tmp_path, monkeypatch):
    clean_env(monkeypatch, tmp_path)
    sd = tmp_path / ".superlite"
    assert status.overview(sd, None) == [
        f"run: {sd}; owner: none",
        "orchestrator: not set (ungated)",
        "plan: none found (pass --plan <plan.md>)",
        "fleet: off",
        "budget: no plan",
        f"last test run: none in {sd}",
    ]


def test_owner_names_the_session(tmp_path, monkeypatch):
    clean_env(monkeypatch, tmp_path)
    sd, plan = run_folder(tmp_path)
    (sd / "session").write_text("me\n", encoding="utf-8")
    assert status.overview(sd, plan)[0] == f"run: {sd}; owner: this session"
    (sd / "session").write_text("old-lead\n", encoding="utf-8")
    assert status.overview(sd, plan)[0] == f"run: {sd}; owner: session old-lead"


def test_idle_run_has_no_crash_hint(tmp_path, monkeypatch):
    clean_env(monkeypatch, tmp_path)
    sd, plan = run_folder(tmp_path)
    (sd / "pool.json").write_text(json.dumps({"agents": [{"id": "a2", "busy": False}]}), encoding="utf-8")
    (sd / "fleet.json").write_text(json.dumps({"on": False, "workers": {}}), encoding="utf-8")
    lines = status.overview(sd, plan)
    assert lines[3] == "tasks: checkpointed 1: T1; held 1: T4 (waiting on Max); open 3: T2, T3, T5"
    assert lines[4] == "fleet: off"
    assert not any(ln.startswith("after a crash") for ln in lines)


def test_budget_line_comes_from_budget(tmp_path, monkeypatch):
    clean_env(monkeypatch, tmp_path)
    sd, plan = run_folder(tmp_path)
    (sd / "metrics.jsonl").write_text("", encoding="utf-8")
    monkeypatch.setattr(budget, "compute", lambda p, d: {"plan": p, "dir": d})
    monkeypatch.setattr(budget, "line", lambda b: f"budget: from {b['plan']} in {b['dir']}")
    assert f"budget: from {plan} in {sd}" in status.overview(sd, plan)
    monkeypatch.setattr(budget, "compute", lambda p, d: 1 / 0)
    assert "budget: unavailable (ZeroDivisionError: division by zero)" in status.overview(sd, plan)


def test_sl_status_prints_the_overview(tmp_path):
    sd, plan = run_folder(tmp_path)
    r = sl(tmp_path, "status", "--plan", str(sd))
    assert r.returncode == 0, r.stderr
    out = r.stdout.splitlines()
    assert out[0] == f"run: {sd}; owner: none"
    assert out[2] == f"plan: {plan}: 5 tasks"
    assert "unknown tool" not in r.stderr


def test_sl_status_with_a_plan_file(tmp_path):
    sd, plan = run_folder(tmp_path)
    (sd / "stable.json").unlink()
    r = sl(tmp_path, "status", "--plan", str(plan))
    assert r.returncode == 0, r.stderr
    assert r.stdout.splitlines()[2] == f"plan: {plan}: 5 tasks"


def test_corrupt_pool_json_does_not_stop_status(tmp_path, monkeypatch):
    clean_env(monkeypatch, tmp_path)
    sd, plan = run_folder(tmp_path)
    (sd / "pool.json").write_text("{bad", encoding="utf-8")
    lines = status.overview(sd, plan)
    assert lines[2] == f"plan: {plan}: 5 tasks"
    assert any(ln.startswith("last test run:") for ln in lines)


def test_malformed_pool_and_fleet_shapes_do_not_raise(tmp_path, monkeypatch):
    clean_env(monkeypatch, tmp_path)
    sd, plan = run_folder(tmp_path)
    (sd / "pool.json").write_text(json.dumps({"agents": [1, "x", {"id": "a1", "busy": True, "current": "T2"}]}), encoding="utf-8")
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": {"W1": 5}}), encoding="utf-8")
    assert "running 1: T2 (a1)" in status.overview(sd, plan)[3]
    (sd / "pool.json").write_text(json.dumps({"agents": 5}), encoding="utf-8")
    (sd / "fleet.json").write_text(json.dumps({"on": True, "workers": [1]}), encoding="utf-8")
    assert status.overview(sd, plan)[2] == f"plan: {plan}: 5 tasks"
