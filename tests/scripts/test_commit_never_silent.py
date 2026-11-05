"""#179: a task that is not checkpointed always prints `Tn FAILED: <reason>` and exits non-zero; an unrelated dirty file
outside every Owns no longer blocks another task's checkpoint (it is listed, never staged). #178: the log and ledger
defaults follow `--plan`, not the session's binding."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import SCRIPTS, ENV, git, make_repo, run, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402

PLAN = """# Plan
**Goal:** x.

```mermaid
%% taskgraph
flowchart LR
  T5
```

### T5 parser · Complexity 2 · Est. context 20k
**Owns:** src/a.py
"""
SID = "never-silent-1"


def setup(tmp_path, baseline=None, name="run"):
    """A repo whose plan has T5 owning src/a.py; `baseline` is the run's stable.json `baseline_dirty` (None: no run file)."""
    (tmp_path / name).mkdir()
    repo = make_repo(tmp_path / name)
    write(repo, "plan.md", PLAN)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    if baseline is not None:
        write(repo, ".superlite/stable.json", json.dumps({"baseline_dirty": baseline}))
    return repo


def commit(repo, *args, env=None):
    return run("commit_task", "T5", *args, "--plan", "plan.md", cwd=repo, env=env or ENV)


def log_text(repo):
    f = repo / ".superlite" / "incidents.jsonl"
    return f.read_text(encoding="utf-8") if f.is_file() else ""


def test_unowned_dirty_file_does_not_block(tmp_path):
    repo = setup(tmp_path, baseline=[])
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "notes/x.txt", "mine\n")
    r = commit(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    lines = r.stdout.strip().splitlines()
    assert "left uncommitted (outside every Owns): notes/x.txt" in r.stderr
    assert not any("out-of-scope" in ln or "FAILED" in ln for ln in lines)
    sha = lines[-1]  # one task: the SHA stays the last line
    assert sha == git(repo, "rev-parse", "HEAD")
    assert git(repo, "show", "--name-only", "--format=", sha).split() == ["src/a.py"]
    assert "notes/x.txt" in git(repo, "status", "--porcelain", "--untracked-files=all")  # still in the tree, never staged
    assert "notes/x.txt" in log_text(repo)  # one workaround incident for the dropped file


def test_unowned_dirty_file_listed_once_for_several_tasks(tmp_path):
    repo = setup(tmp_path, baseline=[])
    write(repo, "plan.md", PLAN + "\n### T6 lexer · Complexity 2 · Est. context 20k\n**Owns:** src/b.py\n")
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "notes/x.txt", "mine\n")
    r = run("commit_task", "T5", "T6", "--plan", "plan.md", cwd=repo, env=ENV)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stderr.splitlines().count("left uncommitted (outside every Owns): notes/x.txt") == 1
    assert sum(ln.startswith(("T5 ", "T6 ")) and "FAILED" not in ln for ln in r.stdout.splitlines()) == 2


def test_dirty_before_the_run_keeps_blocking(tmp_path):
    repo = setup(tmp_path, baseline=["notes/x.txt"])
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "notes/x.txt", "mine\n")
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope notes/x.txt (dirty before the run)" in r.stdout
    assert "T5 FAILED: out-of-scope notes/x.txt" in r.stdout
    assert "left uncommitted (outside every Owns)" not in r.stdout


def test_unknown_baseline_keeps_blocking(tmp_path):
    repo = setup(tmp_path, baseline=None)  # no stable.json: nobody knows the file is unrelated
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "notes/x.txt", "mine\n")
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope notes/x.txt" in r.stdout and "T5 FAILED: out-of-scope notes/x.txt" in r.stdout


def test_single_task_failure_prints_failed(tmp_path):
    repo = setup(tmp_path, baseline=[])
    write(repo, "src/a.py", "def broken(:\n")
    r = commit(repo)
    assert r.returncode == 1
    failed = [ln for ln in r.stdout.splitlines() if ln.startswith("T5 FAILED: ")]
    assert len(failed) == 1 and "src/a.py:1" in failed[0] and "SyntaxError" in failed[0], r.stdout
    assert git(repo, "rev-list", "--count", "HEAD") == "2"  # nothing committed


def test_nothing_to_commit_prints_failed(tmp_path):
    repo = setup(tmp_path, baseline=[])
    r = commit(repo)
    assert r.returncode == 1
    assert "T5 FAILED: nothing to commit" in r.stdout.splitlines()


def test_several_tasks_name_the_reason_per_task(tmp_path):
    repo = setup(tmp_path, baseline=[])
    write(repo, "src/a.py", "A = 1\n")
    r = run("commit_task", "T5", "T9", "--plan", "plan.md", cwd=repo, env=ENV)
    assert r.returncode != 0
    assert any(ln.startswith("T5 ") and "FAILED" not in ln for ln in r.stdout.splitlines()), r.stdout
    assert "T9 FAILED: unknown task" in r.stdout.splitlines()


def test_defaults_follow_plan(tmp_path, monkeypatch):
    """The session is bound to run A's folder; `commit_task T5 --plan B` writes B's ledger and log (#178)."""
    a = tmp_path / "runA" / ".superlite"
    a.mkdir(parents=True)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    state.bind(a)
    env = {**ENV, "SUPERLITE_HOME": os.environ["SUPERLITE_HOME"], "CLAUDE_CODE_SESSION_ID": SID}
    repo = setup(tmp_path, baseline=[], name="runB")  # B holds a run marker (stable.json)
    write(repo, "src/a.py", "A = 1\n")
    r = commit(repo, env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "- commit T5 " in (repo / ".superlite" / "progress.md").read_text(encoding="utf-8")
    write(repo, "src/a.py", "def broken(:\n")
    r = commit(repo, env=env)
    assert r.returncode == 1
    assert "SyntaxError" in log_text(repo)
    assert not (a / "progress.md").exists() and not (a / "incidents.jsonl").exists()  # the bound run A stays untouched
