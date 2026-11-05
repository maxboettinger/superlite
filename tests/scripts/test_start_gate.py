"""Tests for start_gate.py and its call in `plan_tools lint --stable` (temp repositories only)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS, make_plan, pt

sys.path.insert(0, str(SCRIPTS))
import start_gate  # noqa: E402
import worktree  # noqa: E402

SL = (SCRIPTS / "sl").as_posix()


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    p = tmp_path.resolve() / "repo"
    p.mkdir()
    git(p, "init", "-q", "-b", "main")
    git(p, "config", "user.name", "t")
    git(p, "config", "user.email", "t@t")
    (p / "src").mkdir()
    (p / "src" / "a.py").write_text("x = 1\n")
    (p / ".gitignore").write_text(".superlite/\n.claude/\n")
    git(p, "add", ".")
    git(p, "commit", "-q", "-m", "init")
    return p


def plan_in(root, header=""):
    d = root / "docs" / "plans"
    d.mkdir(parents=True, exist_ok=True)
    return make_plan(d, [{"id": "T1", "time": 2}], header=header, name="p.md")


def sj(root):
    return json.loads((root / ".superlite" / "stable.json").read_text(encoding="utf-8"))


def test_opt_out_header():
    assert start_gate.opt_out("# P\n**Worktree:** none\n\n## Design\n")
    assert start_gate.opt_out("# P\n**worktree:** None\n")
    assert not start_gate.opt_out("# P\n\n## Design\n**Worktree:** none\n")
    assert not start_gate.opt_out("# P\n**Goal:** x\n")


def test_topic_from_plan_name():
    assert start_gate.topic(Path("docs/plans/2026-11-05-run-isolation.md")) == "run-isolation"
    assert start_gate.topic(Path("plan.md")) == "plan"


def test_gate_blocks_shared_checkout(repo):
    p = plan_in(repo)
    g = start_gate.check(repo, p, repo, SL)
    assert (g.ok, g.mode) == (False, "shared")
    cp = pt("lint", "--plan", p, "--stable", cwd=repo)
    assert cp.returncode == 2
    assert f"lint --stable: BLOCKED: {repo.as_posix()} is the shared checkout, not a worktree" in cp.err
    assert f"run: {SL} worktree ensure p" in cp.err
    assert "or add **Worktree:** none to the plan header" in cp.err
    assert not (repo / ".superlite" / "stable.json").exists()


def test_gate_passes_in_linked_worktree(repo):
    git(repo, "add", "-A")
    wt, _ = worktree.ensure("x", repo)
    p = plan_in(wt)
    assert start_gate.check(wt, p, wt, SL).mode == "linked"
    pt("lint", "--plan", p, "--stable", cwd=wt)
    d = sj(wt)
    assert d["worktree"] == "linked" and d["baseline_dirty"] == []


def test_gate_in_place_records_baseline_once(repo):
    p = plan_in(repo, header="**Worktree:** none")
    (repo / "src" / "a.py").write_text("x = 2\n")
    (repo / "notes.txt").write_text("n")
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "junk").write_text("j")
    cp = pt("lint", "--plan", p, "--stable", cwd=repo)
    d = sj(repo)
    assert d["baseline_dirty"] == ["notes.txt", "src/a.py"]
    assert d["worktree"] == "in-place"
    assert "IN-PLACE: dirty before start: notes.txt, src/a.py" in cp.out
    (repo / "more.txt").write_text("m")
    pt("lint", "--plan", p, "--stable", cwd=repo)
    assert sj(repo)["baseline_dirty"] == ["notes.txt", "src/a.py"]
    ledger = (repo / ".superlite" / "progress.md").read_text(encoding="utf-8")
    assert ledger.count("- Ruling: in-place run") == 1


def test_gate_skips_resumed_run(repo):
    p = plan_in(repo)
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "stable.json").write_text("{}")
    g = start_gate.check(repo, p, repo, SL)
    assert (g.ok, g.mode) == (True, "resumed")
    assert pt("lint", "--plan", p, "--stable", cwd=repo).returncode != 2
    assert "worktree" not in sj(repo)


def test_gate_no_repo_or_no_commit(tmp_path):
    plain = tmp_path.resolve() / "plain"
    plain.mkdir()
    g = start_gate.check(plain, plan_in(plain), plain, SL)
    assert (g.ok, g.mode) == (True, "no-repo")
    e = tmp_path.resolve() / "empty"
    e.mkdir()
    git(e, "init", "-q", "-b", "main")
    g = start_gate.check(e, plan_in(e), e, SL)
    assert (g.ok, g.mode) == (True, "no-repo")


def test_cwd_outside_root_warns(repo, tmp_path):
    p = plan_in(repo, header="**Worktree:** none")
    other = tmp_path.resolve() / "other"
    other.mkdir()
    g = start_gate.check(repo, p, other, SL)
    assert any("outside the run root" in m and "EnterWorktree path=" in m for m in g.messages)
    g = start_gate.check(repo, p, repo / "src", SL)
    assert not any("outside the run root" in m for m in g.messages)


def test_shared_run_line_is_shell_safe(repo):
    d = repo / "docs" / "plans"
    d.mkdir(parents=True)
    plan = d / "a b; rm -rf x.md"
    plan.write_text("# P\n")
    g = start_gate.check(repo, plan, repo, "/abs dir/sl")
    run = [m for m in g.messages if m.startswith("run: ")][0]
    import shlex
    assert shlex.split(run[5:]) == ["/abs dir/sl", "worktree", "ensure", "a b; rm -rf x"]


def test_baseline_rename_and_odd_names(repo):
    git(repo, "mv", "src/a.py", "src/b.py")
    (repo / "säd file.txt").write_text("x")
    plan = plan_in(repo, header="**Worktree:** none\n")
    g = start_gate.check(repo, Path(plan), repo, SL)
    assert g.baseline == ["src/a.py", "src/b.py", "säd file.txt"]
