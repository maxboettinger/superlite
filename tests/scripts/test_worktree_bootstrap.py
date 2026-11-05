"""#141: a fresh worktree names the ignored files it lacks; the Wave 0 brief bootstraps dependencies from the lockfile.

Real git in temp repositories, real worktree.py and wave0.py; T3 consumes no other task's code."""
from __future__ import annotations

import sys

import pytest

from test_wave0 import PY, plan
from test_worktree import cli, git, init

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import wave0  # noqa: E402
import worktree  # noqa: E402

LINE = "worktree: ignored in the main checkout, missing here: "


def ignore(repo, *patterns):
    (repo / ".gitignore").write_text("".join(p + "\n" for p in patterns), encoding="utf-8")
    git(repo, "add", ".gitignore")
    git(repo, "commit", "-q", "-m", "ignore")


@pytest.fixture
def repo(tmp_path):
    return init(tmp_path.resolve() / "repo")


def test_ensure_names_missing_ignored(repo):
    ignore(repo, ".env", ".venv/")
    (repo / ".env").write_text("SECRET=1\n")
    (repo / ".venv").mkdir()
    (repo / ".venv" / "pyvenv.cfg").write_text("home\n")
    r = cli("ensure", "x", "--repo", repo)
    assert r.returncode == 0, r.stderr
    assert LINE + ".env, .venv/" in r.stderr.splitlines()
    wt = repo / ".claude/worktrees/superlite-x"
    assert r.stdout.splitlines() == [wt.as_posix()]
    assert not (wt / ".env").exists() and not (wt / ".venv").exists()  # names only: nothing is copied
    assert (repo / ".env").read_text() == "SECRET=1\n"


def test_missing_ignored_skips_internal(repo):
    ignore(repo, ".superlite/", ".claude/", "__pycache__/", ".env", "have.cfg", "src/local.cfg")
    for d in (".superlite", "__pycache__"):
        (repo / d).mkdir()
        (repo / d / "x").write_text("x")
    (repo / ".claude").mkdir(exist_ok=True)
    (repo / ".claude" / "settings.local.json").write_text("{}")
    (repo / ".env").write_text("a")
    (repo / "have.cfg").write_text("a")
    (repo / "src" / "local.cfg").write_text("a")  # nested: not a top-level entry
    wt, _ = worktree.ensure("x", repo)
    (wt / "have.cfg").write_text("b")  # the worktree has it
    assert worktree.missing_ignored(repo, wt) == [".env"]


def test_missing_ignored_over_ten_says_how_many_more(repo):
    names = [f"f{i:02d}.env" for i in range(13)]
    ignore(repo, "*.env")
    for n in names:
        (repo / n).write_text("a")
    wt, _ = worktree.ensure("x", repo)
    assert worktree.missing_ignored(repo, wt) == names
    r = cli("ensure", "y", "--repo", repo)
    line = next(ln for ln in r.stderr.splitlines() if ln.startswith(LINE))
    assert line == LINE + ", ".join(names[:10]) + " (+3 more)"


def test_no_line_when_nothing_missing(repo):
    r = cli("ensure", "x", "--repo", repo)
    assert r.returncode == 0, r.stderr
    assert "ignored in the main checkout" not in r.stderr
    assert "dependencies" not in r.stderr and r.stderr.strip() == ""
    wt = repo / ".claude/worktrees/superlite-x"
    assert worktree.missing_ignored(repo, wt) == []


def test_existing_worktree_prints_no_ignored_line(repo):
    ignore(repo, ".env")
    (repo / ".env").write_text("a")
    cli("ensure", "x", "--repo", repo)
    r = cli("ensure", "x", "--repo", repo)
    assert "ignored in the main checkout" not in r.stderr


LOCKFILES = [("uv.lock", "uv sync"), ("package-lock.json", "npm ci"), ("pnpm-lock.yaml", "pnpm install --frozen-lockfile"),
             ("bun.lock", "bun install --frozen-lockfile"), ("bun.lockb", "bun install --frozen-lockfile"),
             ("yarn.lock", "yarn install --frozen-lockfile")]


def test_bootstrap_command_per_lockfile(repo):
    wt, _ = worktree.ensure("x", repo)
    assert worktree.is_linked(wt) and wave0.bootstrap_command(wt) is None  # no lockfile
    for lock, cmd in LOCKFILES:
        (wt / lock).write_text("")
        assert wave0.bootstrap_command(wt) == cmd, lock
        (wt / lock).unlink()
        (repo / lock).write_text("")
        assert wave0.bootstrap_command(repo) is None, lock  # a main checkout is never bootstrapped
        (repo / lock).unlink()
    # two lockfiles: the first in the ruling's order wins
    for first, second, cmd in [("uv.lock", "yarn.lock", "uv sync"), ("package-lock.json", "pnpm-lock.yaml", "npm ci"),
                               ("pnpm-lock.yaml", "bun.lockb", "pnpm install --frozen-lockfile"),
                               ("bun.lock", "yarn.lock", "bun install --frozen-lockfile")]:
        (wt / second).write_text("")
        (wt / first).write_text("")
        assert wave0.bootstrap_command(wt) == cmd, (first, second)
        (wt / first).unlink()
        (wt / second).unlink()


def brief_of(root):
    p = plan(root, "**Tech stack:** Python 3.12; pytest", "pytest", PY)
    wave0.write_brief(str(p))
    return (root / ".superlite" / "briefs" / "wave0.md").read_text(encoding="utf-8")


def test_wave0_brief_has_bootstrap_step(repo):
    wt, _ = worktree.ensure("x", repo)
    (wt / "package-lock.json").write_text("{}")
    (repo / "package-lock.json").write_text("{}")
    b = brief_of(wt)
    assert "Bootstrap: run `npm ci` in the worktree before anything else (lockfile package-lock.json).\n" in b
    assert b.index("Bootstrap:") < b.index("## Global constraints")
    assert "Bootstrap:" not in brief_of(repo)  # a main checkout: no bootstrap step


def test_wave0_brief_without_lockfile_has_no_bootstrap_step(repo):
    wt, _ = worktree.ensure("x", repo)
    assert "Bootstrap:" not in brief_of(wt)


def test_missing_ignored_skips_ds_store_and_nested_paths(repo):
    ignore(repo, ".DS_Store", "build/out.log", ".env")
    (repo / ".DS_Store").write_text("x")
    (repo / "build").mkdir()
    (repo / "build" / "keep.txt").write_text("x")
    git(repo, "add", "-f", "build/keep.txt")
    git(repo, "commit", "-q", "-m", "tracked")
    (repo / "build" / "out.log").write_text("x")
    (repo / ".env").write_text("K=1\n")
    wt, _ = worktree.ensure("x", repo)
    assert worktree.missing_ignored(repo, wt) == [".env"]
