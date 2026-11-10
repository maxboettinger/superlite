"""#419 a claimed file prints no line when its claimer is in the call or the file is in a checkpoint; else the line says what to do."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_autocommit import ENV, git, make_repo, run, write  # noqa: E402

PLAN = """# Plan
**Goal:** x.

```mermaid
%% taskgraph
flowchart LR
  T1
  T2
  T3
  T4
```

### T1 a · Complexity 2 · Est. context 20k
**Owns:** src/a.py

### T2 b · Complexity 2 · Est. context 20k
**Owns:** src/b.py

### T3 c · Complexity 2 · Est. context 20k
**Owns:** src/c.py

### T4 d · Complexity 2 · Est. context 20k
**Owns:** src/d.py
"""
X = "notes/x.md"


def setup(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "plan.md", PLAN)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    return repo


def ck(repo, *args):
    return run("commit_task", *args, "--plan", "plan.md", cwd=repo, env=ENV)


def shas(r):
    return dict(ln.split()[:2] for ln in r.stdout.strip().splitlines())


def last_files(repo):
    return json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))["entries"][-1]["files"]


def test_claimer_earlier_in_call_prints_nothing(tmp_path):
    repo = setup(tmp_path)
    write(repo, X, "x\n")
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    r = ck(repo, "T1", "T2", "--also", X, "--ruling", "needed")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "claimed by" not in r.stderr
    assert git(repo, "show", f"{shas(r)['T1']}:{X}") == "x"


def test_claimer_later_in_call_prints_nothing(tmp_path):
    repo = setup(tmp_path)
    assert ck(repo, "T4", "--claim", X, "--ruling", "needed").returncode == 0
    write(repo, X, "x\n")
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/d.py", "D = 1\n")
    r = ck(repo, "T1", "T4")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "claimed by" not in r.stderr
    assert git(repo, "show", f"{shas(r)['T4']}:{X}") == "x"


def test_file_in_claimers_checkpoint_prints_nothing(tmp_path):
    repo = setup(tmp_path)
    write(repo, X, "x\n")
    write(repo, "src/a.py", "A = 1\n")
    assert ck(repo, "T1", "--also", X, "--ruling", "needed").returncode == 0
    write(repo, "src/b.py", "B = 1\n")
    r = ck(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "claimed by" not in r.stderr
    assert last_files(repo) == ["src/b.py"]


def test_claimer_recheckpoint_in_call_prints_nothing(tmp_path):
    repo = setup(tmp_path)
    write(repo, X, "x\n")
    write(repo, "src/a.py", "A = 1\n")
    assert ck(repo, "T1", "--also", X, "--ruling", "needed").returncode == 0
    write(repo, X, "x2\n")
    write(repo, "src/a.py", "A = 2\n")
    write(repo, "src/b.py", "B = 1\n")
    r = ck(repo, "T1", "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "claimed by" not in r.stderr
    assert git(repo, "show", f"{shas(r)['T1']}:{X}") == "x2"


def test_changed_after_claimers_checkpoint_says_run(tmp_path):
    repo = setup(tmp_path)
    write(repo, X, "x\n")
    write(repo, "src/a.py", "A = 1\n")
    assert ck(repo, "T1", "--also", X, "--ruling", "needed").returncode == 0
    write(repo, X, "x2\n")
    write(repo, "src/b.py", "B = 1\n")
    r = ck(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"left uncommitted (claimed by T1, changed after its checkpoint; run commit_task T1): {X}" in r.stderr
    assert r.stderr.count("claimed by") == 1
    assert last_files(repo) == ["src/b.py"]


def test_uncommitted_claimer_says_once_done(tmp_path):
    repo = setup(tmp_path)
    assert ck(repo, "T4", "--claim", X, "--ruling", "needed").returncode == 0
    write(repo, X, "x\n")
    write(repo, "src/a.py", "A = 1\n")
    r = ck(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"left uncommitted (claimed by T4; commit_task T4 commits it once T4 is done): {X}" in r.stderr
    assert last_files(repo) == ["src/a.py"]


def test_running_claimer_says_once_done(tmp_path):
    repo = setup(tmp_path)
    write(repo, X, "x\n")
    write(repo, "src/a.py", "A = 1\n")
    assert ck(repo, "T1", "--also", X, "--ruling", "needed").returncode == 0
    (repo / ".superlite" / "pool.json").write_text(json.dumps({"agents": [{"busy": True, "current": "T1"}]}), encoding="utf-8")
    write(repo, X, "x2\n")
    write(repo, "src/b.py", "B = 1\n")
    r = ck(repo, "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"left uncommitted (claimed by T1; commit_task T1 commits it once T1 is done): {X}" in r.stderr
    assert "changed after" not in r.stderr


def test_directory_claim_names_the_file(tmp_path):
    repo = setup(tmp_path)
    assert ck(repo, "T4", "--claim", "notes/", "--ruling", "needed").returncode == 0
    write(repo, "notes/y.md", "y\n")
    write(repo, "src/a.py", "A = 1\n")
    r = ck(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "left uncommitted (claimed by T4; commit_task T4 commits it once T4 is done): notes/y.md" in r.stderr
    assert last_files(repo) == ["src/a.py"]
