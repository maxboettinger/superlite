"""trees.moved_base / base_commit: task trees follow a run moved onto a new HEAD (#908)."""
from __future__ import annotations

import json
import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402
import trees  # noqa: E402

PLAN = "# Plan\n\n### T1 a\nOwns: src/a.py\n\n### T2 b\nOwns: src/b.py\n\n### T3 c\nOwns: src/c.py\n"


def git(root, *args, check=True):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    r = subprocess.run(["git", "-C", str(root), *args], capture_output=True, text=True, env=env)
    if check and r.returncode:
        raise AssertionError(r.stderr)
    return r.stdout if check else r


@pytest.fixture(autouse=True)
def clean(monkeypatch):
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)
    trees._MOVED.clear()
    trees._WARNED.clear() if hasattr(trees, "_WARNED") else None


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
    monkeypatch.chdir(tmp_path)
    return tmp_path


def head(repo):
    return git(repo, "rev-parse", "HEAD").strip()


def checkpoint(repo):
    (repo / "src" / "a.py").write_text("A = 2\n")
    sha, _ = autocommit.record("T1", "first", ["src/a.py"], str(repo / "plan.md"))
    return sha


def move(repo):
    (repo / "src" / "c.py").write_text("C = 2\n")
    (repo / "src" / "d.py").write_text("D = 1\n")
    git(repo, "add", "src/c.py", "src/d.py")
    git(repo, "commit", "-qm", "main", "--", "src/c.py", "src/d.py")
    return head(repo)


def show(repo, rev, path):
    return git(repo, "show", f"{rev}:{path}")


def test_unmoved_base_is_newest_checkpoint(repo):
    h = head(repo)
    assert trees.base_commit(repo) == h
    c1 = checkpoint(repo)
    assert trees.moved_base(repo) is None
    assert trees.base_commit(repo) == c1


def test_moved_base_replays_checkpoints_on_head(repo):
    b0 = head(repo)
    c1 = checkpoint(repo)
    m = move(repo)
    s = trees.base_commit(repo)
    assert s not in (c1, m)
    assert show(repo, s, "src/a.py") == "A = 2\n"
    assert show(repo, s, "src/c.py") == "C = 2\n"
    assert show(repo, s, "src/d.py") == "D = 1\n"
    assert git(repo, "rev-parse", f"{s}^").strip() == m
    assert trees.moved_base(repo) == {"base": b0, "head": m, "checkpoint": c1, "sha": s,
                                      "files": ["src/a.py"], "overlap": [], "error": ""}


def test_moved_base_is_deterministic(repo):
    checkpoint(repo)
    move(repo)
    s1 = trees.moved_base(repo)["sha"]
    trees._MOVED.clear()
    assert trees.moved_base(repo)["sha"] == s1
    assert not list((repo / ".superlite").glob("trees/base-*.index"))
    assert not list((repo / ".superlite").rglob("*.index"))


def test_moved_base_removes_checkpointed_deletion(repo):
    git(repo, "rm", "-q", "src/b.py")
    autocommit.record("T2", "drop b", ["src/b.py"], str(repo / "plan.md"))
    checkpoint(repo)
    move(repo)
    s = trees.moved_base(repo)["sha"]
    assert git(repo, "cat-file", "-e", f"{s}:src/b.py", check=False).returncode != 0
    assert show(repo, s, "src/a.py") == "A = 2\n"


def test_path_with_space(repo):
    (repo / "src" / "x y.py").write_text("X = 1\n")
    autocommit.record("T1", "x", ["src/x y.py"], str(repo / "plan.md"))
    move(repo)
    s = trees.moved_base(repo)["sha"]
    assert show(repo, s, "src/x y.py") == "X = 1\n"


def test_tree_after_move_holds_main_and_checkpoints(repo, capsys):
    b0 = head(repo)
    checkpoint(repo)
    m = move(repo)
    tree = trees.prepare(repo, "T2", ["src/b.py"])
    assert (tree / "src" / "c.py").read_text() == "C = 2\n"
    assert (tree / "src" / "a.py").read_text() == "A = 2\n"
    assert (tree / "src" / "d.py").exists()
    assert (f"trees: T2 tree on HEAD {m[:7]} plus the run's checkpoints "
            f"(the run moved off its base {b0[:7]})") in capsys.readouterr().err


def test_reused_tree_rebuilt_after_move(repo):
    checkpoint(repo)
    tree = trees.prepare(repo, "T2", ["src/b.py"])
    (tree / ".build").mkdir()
    (tree / ".build" / "out.txt").write_text("x")
    move(repo)
    trees._MOVED.clear()
    tree = trees.prepare(repo, "T2", ["src/b.py"])
    s = trees.moved_base(repo)["sha"]
    assert git(tree, "rev-parse", "HEAD").strip() == s
    assert (tree / "src" / "c.py").read_text() == "C = 2\n"
    assert (tree / ".build" / "out.txt").exists()


def test_overlap_named_in_tree_line(repo, capsys):
    checkpoint(repo)
    base_tree = git(repo, "rev-parse", "HEAD^{tree}").strip()
    env_idx = repo / ".superlite" / "t.index"
    env = {**{k: v for k, v in os.environ.items() if k != "GIT_INDEX_FILE"}, "GIT_INDEX_FILE": str(env_idx)}
    subprocess.run(["git", "-C", str(repo), "read-tree", base_tree], check=True, env=env)
    for path, text in (("src/a.py", "A = 9\n"), ("src/c.py", "C = 2\n")):
        blob = subprocess.run(["git", "-C", str(repo), "hash-object", "-w", "--stdin"], input=text,
                              capture_output=True, text=True, check=True).stdout.strip()
        subprocess.run(["git", "-C", str(repo), "update-index", "--cacheinfo", f"100644,{blob},{path}"],
                       check=True, env=env)
    tree = subprocess.run(["git", "-C", str(repo), "write-tree"], capture_output=True, text=True, check=True,
                          env=env).stdout.strip()
    env_idx.unlink()
    new = git(repo, "commit-tree", tree, "-p", head(repo), "-m", "move").strip()
    git(repo, "update-ref", "HEAD", new)
    mb = trees.moved_base(repo)
    assert mb["overlap"] == ["src/a.py"]
    assert show(repo, mb["sha"], "src/a.py") == "A = 2\n"
    trees.prepare(repo, "T2", ["src/b.py"])
    assert ("checkpointed files the move also changed keep the checkpoint's version: src/a.py "
            "(re-checkpoint their tasks with sl commit_task)") in capsys.readouterr().err


def test_fallback_on_missing_checkpoint(repo, capsys):
    b0 = head(repo)
    st = repo / ".superlite" / "checkpoints.json"
    st.parent.mkdir(exist_ok=True)
    st.write_text(json.dumps({"base": b0, "entries": [{"sha": "f" * 40, "task": "T1", "files": ["src/a.py"]}]}))
    m = move(repo)
    assert trees.base_commit(repo) == "f" * 40
    assert trees.base_commit(repo) == "f" * 40
    err = capsys.readouterr().err
    assert err.count(f"trees: base not rebuilt on HEAD {m[:7]}:") == 1


def test_no_base_keeps_newest_checkpoint(repo, capsys):
    st = repo / ".superlite" / "checkpoints.json"
    st.parent.mkdir(exist_ok=True)
    st.write_text(json.dumps({"entries": [{"sha": "a1"}, {"sha": "b2"}]}))
    assert trees.base_commit(repo) == "b2"
    assert capsys.readouterr().err == ""


def test_signing_config_ignored(repo):
    checkpoint(repo)
    git(repo, "config", "commit.gpgsign", "true")
    git(repo, "config", "gpg.program", "false")
    (repo / "src" / "c.py").write_text("C = 2\n")
    git(repo, "-c", "commit.gpgsign=false", "commit", "-qm", "main", "--", "src/c.py")
    mb = trees.moved_base(repo)
    assert mb["sha"] and mb["error"] == ""


def _checkpoint_is_commit(repo, b0, sha):
    st = repo / ".superlite" / "checkpoints.json"
    st.parent.mkdir(exist_ok=True)
    st.write_text(json.dumps({"base": b0, "entries": [{"sha": sha, "task": "T1", "files": ["src/a.py"]}]}))


def test_checkpoint_is_head(repo):
    b0 = head(repo)
    (repo / "src" / "a.py").write_text("A = 2\n")
    git(repo, "commit", "-qam", "cp")
    _checkpoint_is_commit(repo, b0, head(repo))
    assert trees.base_commit(repo) == head(repo)
    mb = trees.moved_base(repo)
    assert mb["sha"] == head(repo) and mb["overlap"] == [] and mb["files"] == ["src/a.py"]


def test_checkpoint_ancestor_of_head(repo):
    b0 = head(repo)
    (repo / "src" / "a.py").write_text("A = 2\n")
    git(repo, "commit", "-qam", "cp")
    cp = head(repo)
    (repo / "src" / "a.py").write_text("A = 3\n")
    git(repo, "commit", "-qam", "later")
    _checkpoint_is_commit(repo, b0, cp)
    assert trees.base_commit(repo) == head(repo)
    tree = trees.prepare(repo, "T2", ["src/b.py"])
    assert (tree / "src" / "a.py").read_text() == "A = 3\n"
