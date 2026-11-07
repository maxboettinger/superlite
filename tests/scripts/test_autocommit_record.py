"""autocommit.record reuses a task's checkpoint when nothing changed (#294)."""
import json
import sys

import pytest

from test_autocommit import SCRIPTS, git, make_repo, run, write, two_tasks  # noqa: F401

sys.path.insert(0, str(SCRIPTS))
import autocommit  # noqa: E402


@pytest.fixture
def repo(tmp_path, monkeypatch):
    r = make_repo(tmp_path)
    monkeypatch.chdir(r)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    write(r, "src/a.py", "a = 1\n")
    write(r, "src/b.py", "b = 1\n")
    return r


def entries(repo):
    return json.loads((repo / ".superlite/checkpoints.json").read_text())["entries"]


def run_name(repo):
    return json.loads((repo / ".superlite/checkpoints.json").read_text())["run"]


def nrefs(repo):
    return len(git(repo, "for-each-ref", "refs/superlite").splitlines())


def test_first_record_commits(repo):
    sha, reused = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    assert reused is False
    assert git(repo, "cat-file", "-t", sha) == "commit"
    assert len(entries(repo)) == 1


def test_unchanged_rerecord_reuses(repo):
    s1, _ = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    n = nrefs(repo)
    assert autocommit.record("T1", "parser", ["src/a.py"], "plan.md") == (s1, True)
    assert len(entries(repo)) == 1
    assert git(repo, "rev-parse", f"refs/superlite/{run_name(repo)}/T1") == s1
    assert nrefs(repo) == n


def test_reuse_names_the_tasks_own_sha(repo):
    s1, _ = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    s2, f = autocommit.record("T2", "lexer", ["src/b.py"], "plan.md")
    assert f is False
    assert autocommit.record("T1", "parser", ["src/a.py"], "plan.md") == (s1, True)
    assert [e["task"] for e in entries(repo)] == ["T1", "T2"]


def test_changed_file_commits_again(repo):
    s1, _ = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    write(repo, "src/a.py", "a = 2\n")
    s3, reused = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    assert reused is False and s3 != s1
    assert git(repo, "rev-parse", f"{s3}^") == s1


def test_first_record_of_a_task_with_same_tree_still_commits(repo):
    s1, _ = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    s9, reused = autocommit.record("T9", "x", ["src/a.py"], "plan.md")
    assert reused is False and s9 != s1
    assert git(repo, "rev-parse", f"{s9}^{{tree}}") == git(repo, "rev-parse", f"{s1}^{{tree}}")
    assert len(entries(repo)) == 2


def test_deletion_counts_as_change(repo):
    s1, _ = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    (repo / "src/a.py").unlink()
    _, reused = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    assert reused is False


def test_checkpoint_returns_the_sha(repo):
    s1, _ = autocommit.record("T1", "parser", ["src/a.py"], "plan.md")
    assert autocommit.checkpoint("T1", "parser", ["src/a.py"], "plan.md") == s1
    assert len(entries(repo)) == 1
