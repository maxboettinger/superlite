"""#566: a run with no test command names the fix: run_tests --task names the Tests cmd=."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"

TASK_HINT = "; or name T1's own command on its Tests line: **Tests:** fast cmd=<command>"


def env(tmp_path):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    e.update(SUPERLITE_HOME=str(tmp_path / "home"), SUPERLITE_USER_TEST_CMD=str(tmp_path / "no-user-file.json"),
             PYTHONIOENCODING="utf-8")
    return e


def rt(tmp_path, *args):
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    return subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), *map(str, args), "--log", str(sl / "incidents.jsonl"),
                           "--ledger", str(sl / "ledger.md"), "--summary", str(sl / "test-summary.json")],
                          capture_output=True, cwd=tmp_path, env=env(tmp_path), timeout=120, text=True)


def test_task_run_without_command_names_tests_cmd(tmp_path):
    (tmp_path / "plan.md").write_text("# Plan\n\n### T1 app\n**Owns:** Sources/App/A.swift\n**Tests:** fast\n", encoding="utf-8")
    cp = rt(tmp_path, "--task", "T1", "--plan", tmp_path / "plan.md")
    assert cp.returncode == 2, cp.stdout + cp.stderr
    assert "no test command found" in cp.stderr and TASK_HINT in cp.stderr
    s = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert s["error"].endswith(TASK_HINT)


def test_run_without_task_has_no_task_hint(tmp_path):
    cp = rt(tmp_path, "--full")
    assert cp.returncode == 2 and "no test command found" in cp.stderr
    assert "cmd=<command>" not in cp.stderr
