"""autocommit.held_files: checkpointed files a hook can skip, read-only (#671)."""
import subprocess
import sys

import pytest

from test_autocommit import SCRIPTS, git, make_repo, write

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = make_repo(tmp_path)
    monkeypatch.chdir(r)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    return r


def test_no_state_is_empty(repo):
    assert autocommit.held_files(repo) == {"covered": [], "edited": []}


def test_covered_and_edited(repo):
    write(repo, "a.py", "a = 1\n")
    write(repo, "b.py", "b = 1\n")
    autocommit.record("T1", "t", ["a.py", "b.py"], "plan.md")
    write(repo, "b.py", "b = 2\n")
    assert autocommit.held_files(repo) == {"covered": ["a.py"], "edited": ["b.py"]}


def test_two_tasks_union(repo):
    write(repo, "a.py", "a = 1\n")
    write(repo, "c.py", "c = 1\n")
    autocommit.record("T1", "t", ["a.py"], "plan.md")
    autocommit.record("T2", "t", ["c.py"], "plan.md")
    assert autocommit.held_files(repo) == {"covered": ["a.py", "c.py"], "edited": []}


def test_deleted_after_checkpoint_is_edited(repo):
    write(repo, "a.py", "a = 1\n")
    autocommit.record("T1", "t", ["a.py"], "plan.md")
    (repo / "a.py").unlink()
    assert autocommit.held_files(repo) == {"covered": [], "edited": ["a.py"]}


def snapshot(repo):
    st = repo / ".superlite/checkpoints.json"
    return (git(repo, "status", "--porcelain"), git(repo, "for-each-ref", "refs/superlite"), st.read_bytes())


def test_read_only(repo):
    write(repo, "a.py", "a = 1\n")
    autocommit.record("T1", "t", ["a.py"], "plan.md")
    write(repo, "a.py", "a = 2\n")
    before = snapshot(repo)
    autocommit.held_files(repo)
    assert snapshot(repo) == before
    assert not (repo / ".superlite/checkpoint.index").exists()


def test_corrupt_state_is_empty(repo):
    write(repo, ".superlite/checkpoints.json", "{")
    assert autocommit.held_files(repo) == {"covered": [], "edited": []}


def test_other_cwd(repo, tmp_path, monkeypatch):
    write(repo, "a.py", "a = 1\n")
    write(repo, "b.py", "b = 1\n")
    autocommit.record("T1", "t", ["a.py", "b.py"], "plan.md")
    write(repo, "b.py", "b = 2\n")
    here = autocommit.held_files(repo)
    (tmp_path / "elsewhere").mkdir()
    monkeypatch.chdir(tmp_path / "elsewhere")
    assert autocommit.held_files(repo) == here == {"covered": ["a.py"], "edited": ["b.py"]}
