"""An isolated --fast task run tests the whole working tree and names the overlay (#339)."""
from __future__ import annotations

import json

from test_plan_tools import run
from test_run_tests_plan_fallback import OUT, RUN_TESTS, git, setup, summary

CHECK = f"""#!/usr/bin/env bash
if grep -q BROKEN src/b.txt; then echo "error: BROKEN"; exit 1; fi
if [ -n "$CHECK_NEW" ]; then
  if [ ! -f src/c.txt ] || [ -f src/d.txt ]; then exit 1; fi
fi
echo "{OUT}"
"""


def fixture(tmp_path, env=None):
    plan = setup(tmp_path)
    (tmp_path / "src" / "b.txt").write_text("ok", encoding="utf-8")
    (tmp_path / "src" / "d.txt").write_text("d", encoding="utf-8")
    sl = tmp_path / ".superlite"
    (sl / "check.sh").write_text(CHECK, encoding="utf-8")
    spec = {"language": "swift", "test": "bash .superlite/check.sh", "test_file": "bash .superlite/check.sh",
            "isolate": True}
    if env:
        spec["env"] = env
    (sl / "test-cmd.json").write_text(json.dumps(spec), encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "more")
    return plan


def test_fast_tree_carries_an_unowned_change(tmp_path):
    plan = fixture(tmp_path)
    (tmp_path / "src" / "b.txt").write_text("BROKEN", encoding="utf-8")
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 1, cp.both
    assert summary(tmp_path)["failed"] >= 1
    assert "run_tests: tree .superlite/trees/T1 = base + all working-tree changes (--fast): 1 file" in cp.err


def test_fast_tree_carries_new_and_deleted_files(tmp_path):
    plan = fixture(tmp_path, env={"CHECK_NEW": "1"})
    (tmp_path / "src" / "c.txt").write_text("c", encoding="utf-8")
    (tmp_path / "src" / "d.txt").unlink()
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 2
    assert "(--fast): 2 files" in cp.err


def test_fast_tree_drops_a_reverted_change(tmp_path):
    plan = fixture(tmp_path)
    b = tmp_path / "src" / "b.txt"
    b.write_text("BROKEN", encoding="utf-8")
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 1, cp.both
    b.write_text("ok", encoding="utf-8")
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert "(--fast): 0 files" in cp.err


def test_full_task_tree_keeps_own_files_only(tmp_path):
    plan = fixture(tmp_path)
    (tmp_path / "src" / "b.txt").write_text("BROKEN", encoding="utf-8")
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert "run_tests: tree .superlite/trees/T1 = base + T1's own changes: 0 files" in cp.err


def test_untask_fast_run_prints_no_tree_line(tmp_path):
    fixture(tmp_path)
    cp = run(RUN_TESTS, "--fast", "src/a.txt", cwd=tmp_path)
    assert "run_tests: tree " not in cp.err
