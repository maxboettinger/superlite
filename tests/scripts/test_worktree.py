"""Tests for worktree.py: slug, is_linked, ensure and the CLI (temp repositories only)."""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
SL = SCRIPTS / "sl"
sys.path.insert(0, str(SCRIPTS))

import worktree  # noqa: E402


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def init(path, commit=True):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "t")
    git(path, "config", "user.email", "t@t")
    if commit:
        (path / "a.txt").write_text("one\n")
        (path / "src").mkdir()
        (path / "src" / "b.txt").write_text("b\n")
        git(path, "add", ".")
        git(path, "commit", "-q", "-m", "init")
    return path


@pytest.fixture
def repo(tmp_path):
    return init(tmp_path.resolve() / "repo")


def branch(p):
    return git(p, "rev-parse", "--abbrev-ref", "HEAD").strip()


def count(p):
    return git(p, "worktree", "list", "--porcelain").count("worktree ")


def cli(*args, cwd=None):
    return subprocess.run(["bash", str(SL), "worktree", *map(str, args)], capture_output=True, text=True,
                          encoding="utf-8", cwd=cwd)


def test_slug():
    assert worktree.slug("Add Login!") == "add-login"
    assert worktree.slug("  a//b__c  ") == "a-b-c"
    assert worktree.slug("日本語") == "change"
    s = worktree.slug("word " * 12)
    assert len(s) == 39 or len(s) == 40
    assert not s.endswith("-")
    s = worktree.slug("a" * 39 + " bbb")
    assert s == "a" * 39


def test_slug_never_escapes():
    s = worktree.slug("../../etc/passwd ü")
    assert "/" not in s and ".." not in s


def test_is_linked(repo, tmp_path):
    p, _ = worktree.ensure("x", repo)
    assert not worktree.is_linked(repo)
    assert worktree.is_linked(p)
    plain = tmp_path / "plain"
    plain.mkdir()
    assert not worktree.is_linked(plain)


def test_is_linked_submodule_style(tmp_path):
    d = tmp_path / "sub"
    d.mkdir()
    (d / ".git").write_text("gitdir: ../.git/modules/sub\n")
    assert not worktree.is_linked(d)


def test_ensure_creates_worktree_and_branch(repo):
    p, st = worktree.ensure("Add Login!", repo)
    assert (p, st) == (repo / ".claude/worktrees/superlite-add-login", "created")
    assert branch(p) == "superlite/add-login"
    assert branch(repo) == "main"


def test_ensure_twice_same_path(repo):
    p, _ = worktree.ensure("x", repo)
    p2, st = worktree.ensure("x", repo)
    assert (p2, st) == (p, "exists")
    assert count(repo) == 2


def test_ensure_inside_linked_returns_it(repo):
    p, _ = worktree.ensure("x", repo)
    got, st = worktree.ensure("other", p / "src")
    assert (got, st) == (p, "linked")
    assert count(repo) == 2


def test_ensure_from_subdirectory_uses_main_root(repo):
    p, _ = worktree.ensure("x", repo / "src")
    assert (repo / ".claude/worktrees") in p.parents


def test_existing_branch_without_worktree_is_checked_out(repo):
    git(repo, "branch", "superlite/x")
    p, st = worktree.ensure("x", repo)
    assert st == "created"
    assert branch(p) == "superlite/x"


def test_ignore_entry_added_once(repo, tmp_path):
    worktree.ensure("a", repo)
    worktree.ensure("b", repo)
    ex = (repo / ".git/info/exclude").read_text().splitlines()
    assert ex.count(".claude/worktrees/") == 1
    r2 = init(tmp_path / "r2")
    (r2 / ".gitignore").write_text(".claude/worktrees/\n")
    git(r2, "add", ".gitignore")
    git(r2, "commit", "-q", "-m", "ig")
    before = (r2 / ".git/info/exclude").read_text()
    worktree.ensure("a", r2)
    assert (r2 / ".git/info/exclude").read_text() == before


def test_dirty_main_checkout_untouched(repo):
    (repo / "a.txt").write_text("dirty\n")
    p, _ = worktree.ensure("x", repo)
    assert (repo / "a.txt").read_text() == "dirty\n"
    assert (p / "a.txt").read_text() == "one\n"
    assert branch(repo) == "main"


def test_path_taken_by_plain_folder_exits_2(repo):
    d = repo / ".claude/worktrees/superlite-x"
    d.mkdir(parents=True)
    (d / "keep.txt").write_text("k")
    r = cli("ensure", "x", "--repo", repo)
    assert r.returncode == 2
    assert str(d) in r.stderr
    assert count(repo) == 1


def test_no_repo_prints_folder_exit_0(tmp_path):
    plain = tmp_path.resolve() / "plain"
    plain.mkdir()
    r = cli("ensure", "x", "--repo", plain)
    assert r.returncode == 0
    assert r.stdout.strip() == plain.as_posix()
    assert "no git repository" in r.stderr
    empty = init(tmp_path.resolve() / "empty", commit=False)
    r = cli("ensure", "x", "--repo", empty)
    assert r.returncode == 0
    assert r.stdout.strip() == empty.as_posix()
    assert "no commit yet" in r.stderr
    assert worktree.ensure("x", plain) == (plain, "no-repo")


def test_cli_stdout_is_only_the_path(repo):
    r = cli("ensure", "Add Login!", "--repo", repo)
    assert r.returncode == 0
    assert r.stdout.splitlines() == [(repo / ".claude/worktrees/superlite-add-login").as_posix()]
    assert "missing here" not in r.stderr  # nothing ignored in the main checkout: no note
    (repo / ".gitignore").write_text(".env\n", encoding="utf-8")
    (repo / ".env").write_text("K=1\n", encoding="utf-8")
    r = cli("ensure", "Other", "--repo", repo)
    assert r.stdout.splitlines() == [(repo / ".claude/worktrees/superlite-other").as_posix()]
    assert "missing here: .env" in r.stderr


def test_deleted_worktree_folder_is_recreated(repo):
    import shutil
    p, _ = worktree.ensure("x", repo)
    shutil.rmtree(p)
    p2, st = worktree.ensure("x", repo)
    assert (p2, st) == (p, "created")
    assert p2.is_dir() and branch(p2) == "superlite/x"
    assert count(repo) == 2


def test_exclude_written_to_common_dir_from_subdir(repo, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    worktree.ensure("x", repo / "src")
    assert (repo / ".git" / "info" / "exclude").read_text().count(".claude/worktrees/") == 1
    assert not (tmp_path / "info").exists()
