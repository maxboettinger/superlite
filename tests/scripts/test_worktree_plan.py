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

USAGE = "usage: worktree ensure TOPIC [--repo DIR] | inplace --reason TEXT [--plan P]\n"


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
