"""#399: a file this task owns that a running sibling also owns, changed since the newest checkpoint, is held out."""
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_autocommit import ENV, SCRIPTS, git, make_repo, run, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

PLAN = """# Plan
**Goal:** x.

```mermaid
%% taskgraph
flowchart LR
  T1
  T2
```

### T1 a · Complexity 2 · Est. context 20k
**Owns:** src/a.py, src/shared.py

### T2 b · Complexity 2 · Est. context 20k
**Owns:** src/b.py, src/shared.py
"""
HOLD = "left uncommitted (shared with running T2; commit_task T1 again once it is done): src/shared.py"


def setup(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "plan.md", PLAN)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    return repo


def ck(repo, *args, env=None):
    return run("commit_task", *args, "--plan", "plan.md", cwd=repo, env=env or ENV)


def pool(repo, agents):
    p = repo / ".superlite" / "pool.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": agents}), encoding="utf-8")


def entries(repo):
    f = repo / ".superlite" / "checkpoints.json"
    return json.loads(f.read_text(encoding="utf-8"))["entries"] if f.is_file() else []


def first_case(repo):
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/shared.py", "S = 1\n")
    s1 = ck(repo, "T1").stdout.strip()
    pool(repo, [{"busy": True, "current": "T2"}])
    write(repo, "src/shared.py", "S = 1\nT2 = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "src/a.py", "A = 2\n")
    return s1, ck(repo, "T1")


def test_fixer_checkpoint_leaves_running_siblings_shared_file(tmp_path):
    repo = setup(tmp_path)
    s1, r = first_case(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    s2 = r.stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", s2) and s2 != s1
    assert HOLD in r.stderr
    assert git(repo, "show", f"{s2}:src/shared.py") == "S = 1"
    assert git(repo, "show", f"{s2}:src/a.py") == "A = 2"
    assert "src/b.py" not in git(repo, "ls-tree", "-r", "--name-only", s2)


def test_all_held_fails_with_reason(tmp_path):
    repo = setup(tmp_path)
    pool(repo, [{"busy": True, "current": "T2"}])
    write(repo, "src/shared.py", "S = 2\n")
    r = ck(repo, "T1")
    assert r.returncode == 1
    assert "T1 FAILED: nothing to commit; held for running T2: src/shared.py" in r.stdout
    assert HOLD in r.stderr
    assert entries(repo) == []


def test_held_after_own_checkpoint_says_no_change(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    s1 = ck(repo, "T1").stdout.strip()
    pool(repo, [{"busy": True, "current": "T2"}])
    write(repo, "src/shared.py", "S = 2\n")
    r = ck(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout == f"T1: no change since its last checkpoint {s1}\n"
    assert HOLD in r.stderr


def test_unchanged_shared_file_not_held(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/shared.py", "S = 1\n")
    assert ck(repo, "T1").returncode == 0
    pool(repo, [{"busy": True, "current": "T2"}])
    write(repo, "src/a.py", "A = 2\n")
    r = ck(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "shared with running" not in r.stderr


def test_no_running_sibling_commits_shared(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/shared.py", "S = 1\n")
    r = ck(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "show", f"{r.stdout.strip()}:src/shared.py") == "S = 1"
    assert "shared with running" not in r.stderr


def test_sibling_in_same_call_not_held(tmp_path):
    repo = setup(tmp_path)
    pool(repo, [{"busy": True, "current": "T1,T2"}])
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/shared.py", "S = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    r = ck(repo, "T1", "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "shared with running" not in r.stderr
    t1 = r.stdout.strip().splitlines()[0].split()[1]
    assert git(repo, "show", f"{t1}:src/shared.py") == "S = 1"


def test_also_file_never_held(tmp_path):
    repo = setup(tmp_path)
    pool(repo, [{"busy": True, "current": "T2"}])
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/shared.py", "S = 1\n")
    r = ck(repo, "T1", "--also", "src/shared.py", "--ruling", "fixer owns the fix")
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "show", f"{r.stdout.strip()}:src/shared.py") == "S = 1"
    assert "shared with running" not in r.stderr


def test_sibling_commit_takes_held_file(tmp_path):
    repo = setup(tmp_path)
    first_case(repo)
    pool(repo, [{"busy": False}])
    r = ck(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert git(repo, "show", f"{r.stdout.strip()}:src/shared.py") == "S = 1\nT2 = 1"
    assert "src/shared.py" in entries(repo)[-1]["files"]


def test_hold_with_autocommit_on(tmp_path):
    repo = setup(tmp_path)
    env = {**ENV, "SUPERLITE_AUTOCOMMIT": "1"}
    pool(repo, [{"busy": True, "current": "T2"}])
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/shared.py", "S = 1\n")
    r = ck(repo, "T1", env=env)
    assert r.returncode == 0, r.stdout + r.stderr
    assert HOLD in r.stderr
    assert git(repo, "show", "--name-only", "--format=", "HEAD") == "src/a.py"
    assert "src/shared.py" in git(repo, "status", "--porcelain")


def test_stray_file_with_batch_mate_running(tmp_path):
    repo = setup(tmp_path)
    pool(repo, [{"busy": True, "current": "T1,T2"}])
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "stray/new.txt", "x\n")
    r = ck(repo, "T1", "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "left uncommitted (another task is running: T2): stray/new.txt" in r.stderr
    assert "out-of-scope" not in r.stdout


def test_running_shared_examples():
    info = {"T1": {"owns": ["src/a.py", "src/shared.py"]}, "T2": {"owns": ["src/b.py", "src/shared.py"]}}
    assert commit_task.running_shared(["src/a.py", "src/shared.py"], info, ["T2"]) == {"src/shared.py": ["T2"]}
    assert commit_task.running_shared(["src/shared.py"], info, ["T9", "review P1"]) == {}
    assert commit_task.running_shared(["src/a.py"], info, []) == {}


def test_hold_in_repo_without_commits(tmp_path):
    repo = tmp_path / "bare"
    repo.mkdir()
    git(repo, "init", "-q")
    git(repo, "config", "user.name", "Test")
    git(repo, "config", "user.email", "test@example.com")
    git(repo, "config", "commit.gpgsign", "false")
    write(repo, "plan.md", PLAN)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/shared.py", "S = 1\n")
    pool(repo, [{"busy": True, "current": "T2"}])
    r = ck(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert HOLD in r.stderr
    assert git(repo, "show", f"{r.stdout.strip()}:src/a.py") == "A = 1"


def test_docstring_describes_hold():
    doc = commit_task.__doc__
    assert "shared with running" in doc
    assert "are left uncommitted" in doc
