"""Flow: a blocked start, the printed worktree command, then a passing lint (temp repositories only)."""
from __future__ import annotations

import json
import shlex
import shutil
import subprocess
from pathlib import Path

import pytest

from test_plan_tools import make_plan, pt

ROOT = Path(__file__).resolve().parents[2]


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    p = tmp_path.resolve() / "repo"
    p.mkdir()
    git(p, "init", "-q", "-b", "main")
    git(p, "config", "user.name", "t")
    git(p, "config", "user.email", "t@t")
    (p / "a.py").write_text("x = 1\n")
    (p / ".gitignore").write_text(".superlite/\n")
    git(p, "add", ".")
    git(p, "commit", "-q", "-m", "init")
    return p


def test_blocked_then_ensure_then_lint_passes(repo):
    d = repo / "docs" / "plans"
    d.mkdir(parents=True)
    plan = make_plan(d, [{"id": "T1", "time": 2}], name="2026-11-05-flow.md")
    cp = pt("lint", "--plan", plan, "--stable", cwd=repo)
    assert cp.returncode == 2
    line = next(ln for ln in cp.err.splitlines() if ln.startswith("run: "))
    assert "worktree ensure flow" in line
    done = subprocess.run(shlex.split(line[5:]), cwd=repo, capture_output=True, text=True)
    assert done.returncode == 0, done.stderr
    wt = Path(done.stdout.strip())
    assert wt.name == "superlite-flow" and wt.is_dir()
    (wt / "docs" / "plans").mkdir(parents=True, exist_ok=True)
    moved = wt / "docs" / "plans" / plan.name
    shutil.move(str(plan), str(moved))
    cp = pt("lint", "--plan", moved, "--stable", cwd=wt)
    assert cp.returncode != 2, cp.err
    sj = json.loads((wt / ".superlite" / "stable.json").read_text(encoding="utf-8"))
    assert sj["worktree"] == "linked"
    tracked = [ln for ln in git(repo, "status", "--porcelain").splitlines() if not ln.startswith("??")]
    assert tracked == []
    assert not (repo / ".superlite" / "stable.json").exists()


def test_docs_name_tool_gate_and_guard():
    tools = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    hooks = (ROOT / "docs" / "hooks.md").read_text(encoding="utf-8")
    for s in ("worktree ensure", "**Worktree:** none", "baseline_dirty"):
        assert s in tools, s
    for s in (".git/info/exclude", "Blocked target:"):
        assert s in hooks, s
    assert "subcommands. `lint --stable`" in tools and "noted on stderr). The prime" in tools
    assert "protected-file block" in hooks
