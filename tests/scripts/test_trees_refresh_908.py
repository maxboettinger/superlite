"""trees refresh: report and move a run onto a newer base (#908)."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402
import trees  # noqa: E402

PLAN = "# Plan\n\n### T1 a\nOwns: src/a.py\n\n### T2 b\nOwns: src/b.py\n"


def git(root, *args, check=True, text=None):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env, input=text)
    if check and r.returncode:
        raise AssertionError(r.stderr)
    return r.stdout


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)
    trees._MOVED.clear()
    trees._WARNED.clear()


@pytest.fixture
def repo(tmp_path, monkeypatch):
    git(tmp_path, "init", "-q", "-b", "main")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".git" / "info").mkdir(exist_ok=True)
    (tmp_path / ".git" / "info" / "exclude").write_text(".superlite/\n")
    (tmp_path / "plan.md").write_text(PLAN)
    (tmp_path / "src").mkdir()
    for n, v in (("a", "A"), ("b", "B"), ("c", "C")):
        (tmp_path / "src" / f"{n}.py").write_text(f"{v} = 1\n")
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    git(tmp_path, "checkout", "-qb", "run")
    monkeypatch.chdir(tmp_path)
    return tmp_path


def head(repo):
    return git(repo, "rev-parse", "HEAD").strip()


def checkpoint(repo):
    (repo / "src" / "a.py").write_text("A = 2\n")
    return autocommit.record("T1", "first", ["src/a.py"], str(repo / "plan.md"))[0]


def advance_main(repo, files):
    """Commit `files` ({path: text}) on main without touching the run's working tree."""
    idx = repo / ".superlite" / "adv.index"
    idx.parent.mkdir(exist_ok=True)
    env = {**{k: v for k, v in os.environ.items() if k != "GIT_INDEX_FILE"}, "GIT_INDEX_FILE": str(idx)}
    parent = git(repo, "rev-parse", "main").strip()

    def run(*args, inp=None):
        return subprocess.run(["git", "-C", str(repo), *args], capture_output=True, text=True, check=True,
                              env=env, input=inp).stdout.strip()

    run("read-tree", parent)
    for path, text in files.items():
        blob = run("hash-object", "-w", "--stdin", inp=text)
        run("update-index", "--add", "--cacheinfo", f"100644,{blob},{path}")
    tree = run("write-tree")
    idx.unlink()
    m = git(repo, "commit-tree", tree, "-p", parent, "-m", "main move").strip()
    git(repo, "update-ref", "refs/heads/main", m)
    return m


def own_commit(repo):
    (repo / "src" / "r.py").write_text("R = 1\n")
    git(repo, "add", "src/r.py")
    git(repo, "commit", "-qm", "own", "--", "src/r.py")
    return head(repo)


def call(capsys, *argv):
    rc = trees.main(list(argv))
    cap = capsys.readouterr()
    return rc, cap.out, cap.err


def test_refresh_reports(repo, capsys):
    b0 = head(repo)
    m = advance_main(repo, {"src/c.py": "C = 2\n"})
    assert call(capsys, "refresh")[:2] == (0, f"trees refresh: no checkpoints; trees follow HEAD {b0[:7]}\n")
    checkpoint(repo)
    assert call(capsys, "refresh")[:2] == (0, f"trees refresh: HEAD {b0[:7]} is the run's base; trees are current\n")
    git(repo, "merge", "-q", "--ff-only", "main")
    trees.prepare(repo, "T2", ["src/b.py"])
    rc, out, _ = call(capsys, "refresh")
    s = trees.moved_base(repo)["sha"]
    assert rc == 0
    assert out == (f"trees refresh: base {b0[:7]} -> HEAD {m[:7]}; 1 task trees rebuild on {s[:7]} "
                   "(HEAD plus 1 checkpointed files) at their next run\n")


def test_refresh_reports_overlap(repo, capsys):
    checkpoint(repo)
    advance_main(repo, {"src/a.py": "A = 9\n"})
    git(repo, "update-ref", "HEAD", "main")
    rc, out, _ = call(capsys, "refresh")
    assert rc == 1
    assert "checkpointed files the move also changed: src/a.py;" in out.splitlines()[1]


def test_onto_fast_forwards_keeps_work(repo, capsys):
    b0 = head(repo)
    checkpoint(repo)
    m = advance_main(repo, {"src/c.py": "C = 2\n"})
    rc, out, _ = call(capsys, "refresh", "--onto", "main")
    assert rc == 0 and head(repo) == m
    assert (repo / "src" / "a.py").read_text() == "A = 2\n"
    lines = out.splitlines()
    assert lines[0] == f"trees refresh: fast-forwarded run {b0[:7]} -> {m[:7]}"
    assert lines[1].startswith(f"trees refresh: base {b0[:7]} -> HEAD {m[:7]};")


def test_onto_already_contained(repo, capsys):
    b0 = head(repo)
    rc, out, _ = call(capsys, "refresh", "--onto", b0[:10])
    assert rc == 0 and out.startswith(f"trees refresh: HEAD already contains {b0[:10]}\n")
    assert head(repo) == b0


def test_onto_refuses_overlap(repo, capsys):
    b0 = head(repo)
    checkpoint(repo)
    advance_main(repo, {"src/a.py": "A = 9\n"})
    rc, _, err = call(capsys, "refresh", "--onto", "main")
    assert rc == 2
    assert "trees refresh: refused, main changes files of the run: src/a.py; move the run by hand" in err
    assert head(repo) == b0 and (repo / "src" / "a.py").read_text() == "A = 2\n"


def test_onto_refuses_untracked_overlap(repo, capsys):
    (repo / "src" / "new.py").write_text("N = 1\n")
    advance_main(repo, {"src/new.py": "N = 2\n"})
    rc, _, err = call(capsys, "refresh", "--onto", "main")
    assert rc == 2 and "src/new.py" in err


def test_onto_rebases_own_commits(repo, capsys):
    checkpoint(repo)
    own_commit(repo)
    m = advance_main(repo, {"src/c.py": "C = 2\n"})
    rc, out, _ = call(capsys, "refresh", "--onto", "main")
    assert rc == 0
    assert git(repo, "rev-parse", "HEAD^").strip() == m
    assert git(repo, "show", "HEAD:src/r.py") == "R = 1\n"
    assert (repo / "src" / "a.py").read_text() == "A = 2\n"
    assert f"trees refresh: rebased run (1 commits) onto {m[:7]}" in out
    assert git(repo, "stash", "list") == ""


def test_onto_failure_moves_nothing(repo, capsys):
    checkpoint(repo)
    r = own_commit(repo)
    advance_main(repo, {"src/c.py": "C = 2\n"})
    hook = repo / ".git" / "hooks" / "pre-rebase"
    hook.parent.mkdir(exist_ok=True)
    hook.write_text("#!/bin/sh\nexit 1\n")
    hook.chmod(0o755)
    rc, _, err = call(capsys, "refresh", "--onto", "main")
    assert rc == 3
    assert err.startswith("trees refresh: rebase onto main failed:") and err.rstrip().endswith("; nothing moved")
    assert head(repo) == r and (repo / "src" / "a.py").read_text() == "A = 2\n"
    assert not (repo / ".git" / "rebase-merge").exists()


def test_onto_unknown_revision(repo, capsys):
    rc, _, err = call(capsys, "refresh", "--onto", "nope")
    assert rc == 2 and "trees refresh: unknown revision nope" in err


def test_refresh_with_plan_flag(repo, tmp_path_factory, monkeypatch, capsys):
    b0 = head(repo)
    checkpoint(repo)
    monkeypatch.chdir(tmp_path_factory.mktemp("elsewhere"))
    rc, out, _ = call(capsys, "refresh", "--plan", str(repo / ".superlite"))
    assert rc == 0 and f"HEAD {b0[:7]} is the run's base" in out


@pytest.mark.parametrize("argv", [["refresh", "--onto"], ["refresh", "x"]])
def test_usage(repo, capsys, argv):
    rc, _, err = call(capsys, *argv)
    assert rc == 2 and "usage: trees.py clean | path Tn | refresh [--onto REV] [--plan P]" in err


def test_onto_rebase_refuses_staged_changes(repo, capsys):
    checkpoint(repo)
    r = own_commit(repo)
    advance_main(repo, {"src/c.py": "C = 2\n"})
    (repo / "src" / "b.py").write_text("B = 2\n")
    git(repo, "add", "src/b.py")
    rc, _, err = call(capsys, "refresh", "--onto", "main")
    assert rc == 2
    assert err == "trees refresh: refused, staged changes would come back unstaged after the rebase: commit or unstage them, then rerun\n"
    assert head(repo) == r
    assert git(repo, "diff", "--cached", "--name-only").split() == ["src/b.py"]
