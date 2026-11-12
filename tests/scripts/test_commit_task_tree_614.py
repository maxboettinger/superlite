"""#614: commit_task drops the test tree of every task it checkpointed, unless a run uses it."""
import sys

import pytest

from test_run_scripts import SCRIPTS, git, make_repo, write

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402
import trees  # noqa: E402

PLAN = """# P

## 9. Implementation plan

### T1 · one · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/a.py`

### T2 · two · Complexity 2 · Est. context 10k · Est. time 1 min

**Owns:** `src/b.py`
"""


@pytest.fixture
def run(tmp_path, monkeypatch):
    repo = make_repo(tmp_path)
    write(repo, "docs/plans/p.md", PLAN)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    monkeypatch.chdir(repo)
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(commit_task, "spawn_background", lambda cmd: None)
    (repo / ".superlite").mkdir(exist_ok=True)
    return repo, str(repo / "docs/plans/p.md")


def tree(repo, key):
    return repo / ".superlite" / "trees" / key


def test_checkpoint_drops_the_tree(run, capsys):
    repo, plan = run
    trees.prepare(repo, "T1", [])
    assert tree(repo, "T1").is_dir()
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    assert not tree(repo, "T1").exists()
    assert "commit_task: removed test tree(s) nothing needs: T1" in capsys.readouterr().err


def test_busy_tree_stays(run, capsys):
    repo, plan = run
    trees.prepare(repo, "T1", [])
    write(repo, "src/a.py", "X = 1\n")
    with trees.busy(repo, "T1"):
        assert commit_task.main(["T1", "--plan", plan]) == 0
    assert tree(repo, "T1").is_dir()
    assert "removed test tree" not in capsys.readouterr().err


def test_failed_task_keeps_its_tree(run, capsys):
    repo, plan = run
    trees.prepare(repo, "T2", [])
    # T2 has no change: nothing to checkpoint, so it fails and its tree stays
    assert commit_task.main(["T2", "--plan", plan]) != 0
    assert tree(repo, "T2").is_dir()
    assert "removed test tree" not in capsys.readouterr().err


def test_stdout_unchanged(run, capsys):
    repo, plan = run
    trees.prepare(repo, "T1", [])
    write(repo, "src/a.py", "X = 1\n")
    assert commit_task.main(["T1", "--plan", plan]) == 0
    out = capsys.readouterr().out
    assert len(out.splitlines()) == 1 and len(out.strip()) >= 7 and " " not in out.strip()
