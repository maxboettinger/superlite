"""worktree.main accepts and ignores --plan P / --plan=P anywhere (#336)."""
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

USAGE = "usage: worktree ensure TOPIC [--repo DIR] [--branch NAME] [--dir NAME] | inplace --reason TEXT [--plan P]\n"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def init(path, commit=True):
    path.mkdir(parents=True, exist_ok=True)
    git(path, "init", "-q", "-b", "main")
    git(path, "config", "user.name", "t")
    git(path, "config", "user.email", "t@t")
    if commit:
        (path / "a.txt").write_text("one\n")
        git(path, "add", ".")
        git(path, "commit", "-q", "-m", "init")
    return path


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def repo(tmp_path):
    return init(tmp_path.resolve() / "repo")


@pytest.fixture
def wt(repo):
    return repo / ".claude" / "worktrees" / "superlite-topic"


@pytest.mark.parametrize("shape", [0, 1, 2])
def test_ensure_accepts_plan_anywhere(shape, repo, wt, capsys):
    argv = [
        ["ensure", "topic", "--repo", str(repo), "--plan", ".superlite"],
        ["--plan", ".superlite", "ensure", "topic", "--repo", str(repo)],
        ["ensure", "--plan=/elsewhere/.superlite", "topic", "--repo", str(repo)],
    ][shape]
    assert worktree.main(argv) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == wt.as_posix()
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD").strip() == "superlite/topic"
    names = [p.name for p in wt.parent.iterdir()]
    assert names == ["superlite-topic"]


def test_ensure_with_plan_inside_linked_worktree(repo, wt, capsys):
    assert worktree.main(["ensure", "topic", "--repo", str(repo)]) == 0
    capsys.readouterr()
    assert worktree.main(["ensure", "other", "--repo", str(wt), "--plan", ".superlite"]) == 0
    assert capsys.readouterr().out == wt.as_posix() + "\n"


@pytest.mark.parametrize("shape", [0, 1])
def test_valueless_plan_is_usage_error_and_creates_nothing(shape, repo, wt, capsys):
    argv = [
        ["ensure", "topic", "--repo", str(repo), "--plan"],
        ["ensure", "topic", "--plan", "--repo", str(repo)],
    ][shape]
    assert worktree.main(argv) == 2
    assert capsys.readouterr().err == USAGE
    assert not wt.exists()
    lines = [x for x in git(repo, "worktree", "list", "--porcelain").splitlines() if x.startswith("worktree ")]
    assert len(lines) == 1


def test_inplace_accepts_plan(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert worktree.main(["inplace", "--reason", "r", "--plan", ".superlite"]) == 0
    assert "no inline flow is marked here" in capsys.readouterr().err


def test_help_names_plan(capsys):
    with pytest.raises(SystemExit) as ex:
        worktree.main(["--help"])
    assert ex.value.code == 0
    assert "--plan P (anywhere): accepted and ignored" in capsys.readouterr().out


def test_sl_worktree_ensure_with_plan(repo, wt):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    r = subprocess.run(["bash", str(SL), "worktree", "ensure", "topic", "--plan", ".superlite"],
                       cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert "unrecognized arguments" not in r.stderr
    assert r.stdout.strip().splitlines()[-1] == wt.as_posix()


B = "feat/KEY-1-slug"


@pytest.fixture
def bwt(repo):
    return repo / ".claude" / "worktrees" / "superlite-feat-key-1-slug"


def wt_count(repo):
    return sum(1 for ln in git(repo, "worktree", "list", "--porcelain").splitlines() if ln.startswith("worktree "))


def test_branch_names_branch_and_folder(repo, bwt, capsys):
    assert worktree.main(["ensure", "topic", "--repo", str(repo), "--branch", B]) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == bwt.as_posix()
    assert git(bwt, "rev-parse", "--abbrev-ref", "HEAD").strip() == B
    assert subprocess.run(["git", "-C", str(repo), "show-ref", "--verify", "-q", "refs/heads/superlite/topic"]).returncode != 0
    assert git(repo, "rev-parse", "--abbrev-ref", "HEAD").strip() == "main"
    assert ".claude/worktrees/" in (repo / ".git" / "info" / "exclude").read_text().splitlines()


def test_branch_found_again(repo, bwt, capsys):
    args = ["ensure", "topic", "--repo", str(repo), "--branch", B]
    assert worktree.main(args) == 0
    first = capsys.readouterr().out.strip().splitlines()[-1]
    assert worktree.main(args) == 0
    assert capsys.readouterr().out.strip().splitlines()[-1] == first == bwt.as_posix()
    assert wt_count(repo) == 2


def test_branch_reuses_existing_branch(repo, capsys):
    git(repo, "branch", "feat/KEY-2-x")
    (repo / "b.txt").write_text("two\n")
    git(repo, "add", ".")
    git(repo, "commit", "-q", "-m", "second")
    assert worktree.main(["ensure", "t", "--repo", str(repo), "--branch", "feat/KEY-2-x"]) == 0
    p = Path(capsys.readouterr().out.strip().splitlines()[-1])
    assert p.name == "superlite-feat-key-2-x"
    assert git(p, "rev-parse", "HEAD") == git(repo, "rev-parse", "feat/KEY-2-x")
    assert git(p, "rev-parse", "HEAD") != git(repo, "rev-parse", "main")


@pytest.mark.parametrize("tail,name", [
    (["--branch", "a..b"], "a..b"),
    (["--branch=-x"], "-x"),
    (["--branch", "HEAD"], "HEAD"),
    (["--branch", ""], ""),
    (["--branch", "@{-1}"], "@{-1}"),
])
def test_invalid_branch_is_exit_2(tail, name, repo, capsys):
    assert worktree.main(["ensure", "topic", "--repo", str(repo), *tail]) == 2
    c = capsys.readouterr()
    assert c.err == f"worktree: invalid branch name: {name}\n"
    assert c.out == ""
    assert not (repo / ".claude").exists()
    assert wt_count(repo) == 1


def test_branch_slug_collision_refused(repo, capsys):
    assert worktree.main(["ensure", "t", "--repo", str(repo), "--branch", "feat/KEY-1"]) == 0
    capsys.readouterr()
    assert worktree.main(["ensure", "t", "--repo", str(repo), "--branch", "feat-KEY-1"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("worktree: ")
    assert "is a worktree on feat/KEY-1, not feat-KEY-1" in err
    assert subprocess.run(["git", "-C", str(repo), "show-ref", "--verify", "-q", "refs/heads/feat-KEY-1"]).returncode != 0


def test_branch_inside_linked_worktree(repo, wt, capsys):
    assert worktree.main(["ensure", "topic", "--repo", str(repo)]) == 0
    capsys.readouterr()
    assert worktree.main(["ensure", "x", "--repo", str(wt), "--branch", "feat/other"]) == 0
    c = capsys.readouterr()
    assert c.out == wt.as_posix() + "\n"
    assert c.err == "worktree: linked worktree is on superlite/topic, not feat/other; --branch ignored\n"
    assert worktree.main(["ensure", "x", "--repo", str(wt), "--branch", "superlite/topic"]) == 0
    c = capsys.readouterr()
    assert c.out == wt.as_posix() + "\n"
    assert c.err == ""


def test_branch_checked_out_elsewhere_is_exit_1(repo, capsys):
    assert worktree.main(["ensure", "t", "--repo", str(repo), "--branch", "main"]) == 1
    assert capsys.readouterr().err.startswith("worktree: git worktree add failed:")


def test_long_branch_folder_is_cut(repo, capsys):
    long = "feat/" + "a" * 60
    assert worktree.main(["ensure", "t", "--repo", str(repo), "--branch", long]) == 0
    p = Path(capsys.readouterr().out.strip().splitlines()[-1])
    assert p.name == "superlite-feat-" + "a" * 35
    assert git(p, "rev-parse", "--abbrev-ref", "HEAD").strip() == long


def test_ensure_default_branch_none(repo, wt):
    assert worktree.ensure("topic", repo) == (wt, "created")
    assert git(wt, "rev-parse", "--abbrev-ref", "HEAD").strip() == "superlite/topic"


def test_help_names_branch(capsys):
    with pytest.raises(SystemExit) as ex:
        worktree.main(["ensure", "--help"])
    assert ex.value.code == 0
    assert "--branch NAME" in capsys.readouterr().out


def test_sl_worktree_ensure_with_branch(repo, bwt):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    r = subprocess.run(["bash", str(SL), "worktree", "ensure", "topic", "--branch", B, "--plan", ".superlite"],
                       cwd=repo, capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1] == bwt.as_posix()
