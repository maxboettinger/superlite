# tests/scripts/test_review_one_task_595.py: a one-task plan reviews its only task (#595)
import json, subprocess, sys
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402
from test_spawn_free import ENV, git, run, write  # noqa: E402

ONE = "# Plan\n**Goal:** x.\n\n### T1 only · Complexity 2 · Est. context 30k\n**Owns:** src/a.py\n"
TWO = ONE + "\n### T2 other · Complexity 2 · Est. context 30k\n**Owns:** src/b.py\n"


def test_review_one_task_plan(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(ONE, encoding="utf-8")
    assert io.review_reasons(p, "T1") == ["only task"]


def test_review_two_task_plan_has_no_only_task(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(TWO, encoding="utf-8")
    assert io.review_reasons(p, "T1") == []


def test_commit_task_dispatch_prints_review_for_one_task_plan(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "commit.gpgsign", "false")
    write(repo, "plan.md", ONE)
    write(repo, "README.md", "base\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    write(repo, "src/a.py", "x = 1\n")
    write(repo, ".superlite/fleet.json", json.dumps({"on": True, "workers": {}}))
    r = run("commit_task", "T1", "--plan", "plan.md", "--dispatch", cwd=repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert any(ln.startswith("review: T1 (only task); run ") for ln in r.stdout.splitlines()), r.stdout


def test_only_task_is_a_fallback_reason(tmp_path):
    p = tmp_path / "plan.md"
    p.write_text(ONE.replace("Complexity 2", "Complexity 6"), encoding="utf-8")
    assert io.review_reasons(p, "T1") == ["Complexity 6"]
