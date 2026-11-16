"""Run id, run_start and abandoned runs from `plan_tools lint --stable` (#933)."""
import json
import os
import re
import subprocess
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS, make_plan, pt

sys.path.insert(0, str(SCRIPTS))
import telemetry  # noqa: E402

TASKS = [{"id": f"T{i}", "time": 3, "components": 1, "loc": 100, "tests": "fast"} for i in (1, 2, 3)]


@pytest.fixture(autouse=True)
def _env(monkeypatch, tmp_path):
    for var in ("SUPERLITE_TELEMETRY", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_SESSION_ID", "SUPERLITE_STATE_DIR",
                "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_WORKER", "GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(var, raising=False)
    monkeypatch.setenv("CLAUDECODE", "1")
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "init", "-q", "-b", "feat-x", str(tmp_path)], check=True, env=env)
    (tmp_path / ".superlite").mkdir()


def lint(tmp_path, session="s1", detail="**Detail:** contracts"):
    p = make_plan(tmp_path, TASKS, header=detail)
    os.environ["CLAUDE_CODE_SESSION_ID"] = session
    try:
        cp = pt("lint", "--stable", "--plan", p, cwd=tmp_path)
    finally:
        del os.environ["CLAUDE_CODE_SESSION_ID"]
    assert cp.returncode == 0, cp.both
    return json.loads((tmp_path / ".superlite" / "stable.json").read_text(encoding="utf-8"))


def kinds(kind):
    return [e for e in telemetry.read_events() if e["kind"] == kind]


def test_kind_run_start_first_lint(tmp_path):
    sd = tmp_path / ".superlite"
    (sd / "orchestrator.json").write_text(json.dumps({"mode": "ai", "by": "main"}), encoding="utf-8")
    (sd / "fleet.json").write_text(json.dumps({"on": True}), encoding="utf-8")
    sess = Path(os.environ["SUPERLITE_HOME"]) / "telemetry" / "sessions"
    sess.mkdir(parents=True)
    (sess / "s1.mode").write_text("feature\n", encoding="utf-8")
    stable = lint(tmp_path)
    assert re.match(r"^\d{8}T\d{6}Z-[0-9a-f]{6}$", stable["run_id"]) and stable["run_session"] == "s1"
    (line,) = kinds("run_start")
    assert telemetry.validate(line) == []
    assert line["run"] == stable["run_id"] and line["session"] == "s1"
    assert (line["tasks"], line["detail"], line["branch"]) == (3, "contracts", "feat-x")
    assert (line["orchestrator"], line["fleet"], line["mode"]) == ("ai", True, "feature")
    assert line["plan"] == "plan.md"


def test_relint_keeps_run_id(tmp_path):
    first = lint(tmp_path)
    second = lint(tmp_path)
    assert second["run_id"] == first["run_id"] and second["run_session"] == "s1"
    assert len(kinds("run_start")) == 1 and kinds("run_end") == []


def test_kind_run_end_abandoned_on_resume(tmp_path):
    first = lint(tmp_path, session="s1")
    (tmp_path / ".superlite" / "session").unlink()  # the first session has ended
    second = lint(tmp_path, session="s2")
    assert second["run_id"] != first["run_id"] and second["run_session"] == "s2"
    (end,) = kinds("run_end")
    assert telemetry.validate(end) == []
    assert (end["run"], end["outcome"], end["reason"]) == (first["run_id"], "abandoned", "resumed by another session")
    starts = kinds("run_start")
    assert [s["run"] for s in starts] == [first["run_id"], second["run_id"]]


def test_lead_run_mode_backlog(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_ROLE", "lead")
    lint(tmp_path)
    (line,) = kinds("run_start")
    assert line["mode"] == "backlog" and telemetry.validate(line) == []


def test_old_stable_json_gets_id(tmp_path):
    (tmp_path / ".superlite" / "stable.json").write_text(json.dumps({"stable": []}), encoding="utf-8")
    stable = lint(tmp_path)
    assert stable["run_id"] and len(kinds("run_start")) == 1 and kinds("run_end") == []


def test_no_detail_is_null(tmp_path):
    lint(tmp_path, detail="")
    (line,) = kinds("run_start")
    assert line["detail"] is None


def test_kind_run_end_abandoned_after_takeover(tmp_path):
    first = lint(tmp_path, session="s1")
    os.environ["CLAUDE_CODE_SESSION_ID"] = "s2"
    try:
        cp = subprocess.run([sys.executable, str(SCRIPTS / "orchestrator.py"), "takeover", "--plan", str(tmp_path / "plan.md")],
                            cwd=tmp_path, capture_output=True, text=True)
    finally:
        del os.environ["CLAUDE_CODE_SESSION_ID"]
    assert cp.returncode == 0, cp.stdout + cp.stderr
    second = lint(tmp_path, session="s2")
    assert second["run_id"] != first["run_id"] and second["run_session"] == "s2"
    (end,) = kinds("run_end")
    assert (end["run"], end["outcome"]) == (first["run_id"], "abandoned")


def test_clear_handoff_keeps_run(tmp_path):
    first = lint(tmp_path, session="s1")
    sessions = Path(os.environ["SUPERLITE_HOME"]) / "sessions"
    # what the SessionStart hook does after /clear: the folder and its binding move to the new session id
    (tmp_path / ".superlite" / "session").write_text("s2\n", encoding="utf-8")
    (sessions / "s2").write_text((sessions / "s1").read_text(encoding="utf-8"), encoding="utf-8")
    (sessions / "s1").unlink()
    second = lint(tmp_path, session="s2")
    assert second["run_id"] == first["run_id"] and second["run_session"] == "s2"
    assert kinds("run_end") == [] and len(kinds("run_start")) == 1
    third = lint(tmp_path, session="s2")
    assert third["run_id"] == first["run_id"] and kinds("run_end") == []
