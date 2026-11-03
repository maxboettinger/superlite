"""run_tests --task: .superlite/ paths in the test command resolve against the project root, not the tree (GitHub #49)."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS, run
from test_run_tests_plan_fallback import OUT, git, setup, summary

RUN_TESTS = SCRIPTS / "run_tests.py"


def reset_cmd(tmp_path, cmd):
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd}), encoding="utf-8")


def test_superlite_script_resolves_against_root(tmp_path):
    plan = setup(tmp_path)
    (tmp_path / ".superlite" / "xctest.sh").write_text(f"echo '{OUT}'\n", encoding="utf-8")
    reset_cmd(tmp_path, "bash .superlite/xctest.sh")
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", "--plan", str(plan), cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert (s["passed"], s["failed"]) == (2, 0)


def test_ordinary_relative_path_runs_in_tree(tmp_path):
    plan = setup(tmp_path)
    (tmp_path / "scripts").mkdir()
    (tmp_path / "scripts" / "t.sh").write_text(f"pwd\necho '{OUT}'\n", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "script")
    reset_cmd(tmp_path, "bash scripts/t.sh")
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", "--plan", str(plan), cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    log = (tmp_path / ".superlite" / "test-output.log").read_text(encoding="utf-8")
    assert ".superlite/trees/T1" in log.replace("\\", "/")
