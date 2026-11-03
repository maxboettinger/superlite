"""run_tests --task without --plan finds the plan through .superlite/stable.json (GitHub #77)."""
from __future__ import annotations

import json
import subprocess
import sys

from test_plan_tools import SCRIPTS, make_plan, pt, run

RUN_TESTS = SCRIPTS / "run_tests.py"
OUT = "Executed 2 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds"


def git(tmp_path, *args):
    subprocess.run(["git", "-C", str(tmp_path), "-c", "user.email=t@t", "-c", "user.name=t", *args],
                   check=True, capture_output=True)


def setup(tmp_path):
    """Git repo, .superlite ignored, swift test command, plan in docs/plans/p.md owning src/a.txt."""
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.txt").write_text("a", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".superlite/\n", encoding="utf-8")
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    plan = make_plan(tmp_path / "docs" / "plans", [{"id": "T1", "owns": "src/a.txt"}], name="p.md")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    cmd = f'{sys.executable} -c "print(\'{OUT}\')"'
    (sl / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd}), encoding="utf-8")
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")
    return plan


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_task_without_plan_uses_stable_json_plan(tmp_path):
    plan = setup(tmp_path)
    (tmp_path / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan.resolve())}), encoding="utf-8")
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 2


def test_task_without_any_plan_exits_2_naming_plan_flag(tmp_path):
    setup(tmp_path)
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", cwd=tmp_path)
    assert cp.returncode == 2, cp.both
    assert "--plan" in cp.err
    assert "--plan" in summary(tmp_path)["failures"][0]


def test_lint_stable_records_absolute_plan(tmp_path):
    plan = make_plan(tmp_path, [{"id": "T1", "time": 2}])
    cp = pt("lint", "--stable", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    data = json.loads((tmp_path / ".superlite" / "stable.json").read_text(encoding="utf-8"))
    assert data["plan"] == str(plan.resolve())


def test_missing_stable_plan_falls_back_to_default_plan(tmp_path):
    setup(tmp_path)
    (tmp_path / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(tmp_path / "gone.md")}), encoding="utf-8")
    make_plan(tmp_path / ".superlite", [{"id": "T1", "owns": "src/a.txt"}], name="plan.md")
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 2
