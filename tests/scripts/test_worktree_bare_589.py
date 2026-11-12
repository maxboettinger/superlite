"""#589: a main checkout flagged core.bare=true is refused, not used as a lead's home."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import worktree  # noqa: E402


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path, monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    r = (tmp_path / "repo").resolve()
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.name", "t")
    git(r, "config", "user.email", "t@t")
    (r / "a.txt").write_text("one\n")
    git(r, "add", "a.txt")
    git(r, "commit", "-q", "-m", "one")
    return r


def test_bare_flag_values(repo, tmp_path):
    assert worktree.bare_flag(repo) == ""
    git(repo, "config", "core.bare", "true")
    assert worktree.bare_flag(repo) == f"core.bare=true in {repo / '.git' / 'config'}"
    real = tmp_path / "x.git"
    git(tmp_path, "init", "-q", "--bare", str(real))
    assert worktree.bare_flag(real) == ""


def test_ensure_refuses_bare_flagged_checkout(repo):
    git(repo, "config", "core.bare", "true")
    with pytest.raises(worktree.BareCheckout) as ex:
        worktree.ensure("topic", repo)
    assert "core.bare=true" in str(ex.value) and "config core.bare false" in str(ex.value)


def test_main_exits_2_on_bare_flag(repo, capsys):
    git(repo, "config", "core.bare", "true")
    assert worktree.main(["ensure", "topic", "--repo", str(repo)]) == 2
    assert "worktree: " in capsys.readouterr().err


def test_linked_worktree_of_bare_flagged_main_still_works(repo):
    wt = repo / ".claude" / "worktrees" / "lw"
    git(repo, "worktree", "add", "-q", "-b", "lw", str(wt))
    git(repo, "config", "core.bare", "true")
    assert worktree.bare_flag(wt) == ""
    assert worktree.ensure("topic", wt) == (wt.resolve(), "linked")


def test_real_bare_repo_unchanged(tmp_path):
    real = tmp_path / "x.git"
    git(tmp_path, "init", "-q", "--bare", str(real))
    assert worktree.ensure("topic", real) == (real.resolve(), "no-repo")
