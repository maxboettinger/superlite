"""run_tests --also: declare a file before the run; ledger ruling, tree overlay, outside-file hint (GitHub #517)."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS, make_plan, run
from test_run_tests_plan_fallback import git, setup
from test_run_tests_tree_state_511 import set_cmd

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
LINE = "- Ruling: T1 also commits src/b.txt - declared before the test run (run_tests --also)"


def prep(tmp_path):
    plan = setup(tmp_path)
    (tmp_path / "src" / "b.txt").write_text("b", encoding="utf-8")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "b")
    (tmp_path / "src" / "b.txt").write_text("edited", encoding="utf-8")
    return plan


def ledger(tmp_path):
    return (tmp_path / ".superlite" / "progress.md").read_text(encoding="utf-8")


def test_also_records_claim_and_tree_holds_file(tmp_path):
    plan = prep(tmp_path)
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), "--also", "src/b.txt", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert ledger(tmp_path).splitlines().count(LINE) == 1
    assert (tmp_path / ".superlite" / "trees" / "T1" / "src" / "b.txt").read_text(encoding="utf-8") == "edited"
    assert "T1 also commits src/b.txt" in cp.err
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), "--also", "src/b.txt", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert ledger(tmp_path).splitlines().count(LINE) == 1


def test_also_relative_to_cwd(tmp_path):
    plan = prep(tmp_path)
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), "--also", "b.txt", cwd=tmp_path / "src")
    assert cp.returncode == 0, cp.both
    assert LINE in ledger(tmp_path)


def test_also_needs_task(tmp_path):
    prep(tmp_path)
    cp = run(RUN_TESTS, "--full", "--also", "src/b.txt", cwd=tmp_path)
    assert cp.returncode == 2, cp.both
    assert "--also needs --task Tn" in cp.err


def test_also_claim_read_by_commit_task(tmp_path):
    plan = prep(tmp_path)
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), "--also", "src/b.txt", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert commit_task.also_owned(tmp_path / ".superlite" / "progress.md") == {"src/b.txt": "T1"}


def test_red_tree_run_names_outside_files(tmp_path):
    plan = prep(tmp_path)
    red = "sh -c 'echo \"Executed 2 tests, with 1 failures (1 unexpected) in 0.1 (0.1) seconds\"; exit 1'"
    set_cmd(tmp_path, red)
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), cwd=tmp_path)
    assert cp.returncode == 1, cp.both
    assert "1 changed file(s) not in T1's tree: src/b.txt" in cp.err
    assert "rerun with --also" in cp.err
    set_cmd(tmp_path, "sh -c 'echo \"Executed 2 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds\"'")
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert "not in T1's tree" not in cp.err


def test_to_root_rewrites_repeated_also_flags(tmp_path, monkeypatch):
    import argparse
    import os
    import run_tests
    root, sub = tmp_path / "proj", tmp_path / "proj" / "sub"
    sub.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    a = argparse.Namespace(also=["x.c", "d/", "y.c"], fast=None)
    argv = ["--task", "T1", "--also", "x.c", "d/", "--also", "y.c", "--full"]
    run_tests.to_root(a, argv, str(sub), str(root))
    assert argv == ["--task", "T1", "--also", "sub/x.c", "sub/d/", "--also", "sub/y.c", "--full"]
    assert a.also == ["sub/x.c", "sub/d/", "sub/y.c"]
    os.chdir(tmp_path)
