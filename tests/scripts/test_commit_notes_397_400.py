"""#397 a file another committed task owns, changed after its checkpoint, is noted; #400 call-wide notes print once."""
import json
import re
import sys
import types
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
  T3
  T4
```

### T1 a · Complexity 2 · Est. context 20k
**Owns:** src/a.py

### T2 b · Complexity 2 · Est. context 20k
**Owns:** src/b.py, tests/test_b.py

### T3 c · Complexity 2 · Est. context 20k
**Owns:** src/c.py

### T4 d · Complexity 2 · Est. context 20k
**Owns:** src/d.py
"""
NOTE = "left uncommitted (owned by T2, changed after its checkpoint; run commit_task T2): "


def setup(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "plan.md", PLAN)
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    return repo


def ck(repo, *args):
    return run("commit_task", *args, "--plan", "plan.md", cwd=repo, env=ENV)


def pool(repo, agents):
    p = repo / ".superlite" / "pool.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": agents}), encoding="utf-8")


def test_reviewer_edit_to_committed_task_file_noted(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "tests/test_b.py", "def test_b():\n    assert 1\n")
    assert ck(repo, "T2").returncode == 0
    write(repo, "tests/test_b.py", "def test_b():\n    assert 2\n")
    write(repo, "src/c.py", "C = 1\n")
    r = ck(repo, "T3")
    assert r.returncode == 0, r.stdout + r.stderr
    sha = r.stdout.strip()
    assert re.fullmatch(r"[0-9a-f]{40}", sha)
    assert NOTE + "tests/test_b.py" in r.stderr
    assert "assert 1" in git(repo, "show", f"{sha}:tests/test_b.py")
    r2 = ck(repo, "T2")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "assert 2" in git(repo, "show", f"{r2.stdout.strip()}:tests/test_b.py")


def test_running_owner_silent(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/b.py", "B = 1\n")
    assert ck(repo, "T2").returncode == 0
    pool(repo, [{"busy": True, "current": "T2"}])
    write(repo, "src/b.py", "B = 2\n")
    write(repo, "src/c.py", "C = 1\n")
    r = ck(repo, "T3")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "owned by" not in r.stderr


def test_uncommitted_owner_silent(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "src/c.py", "C = 1\n")
    r = ck(repo, "T3")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "owned by" not in r.stderr


def test_unchanged_since_checkpoint_silent(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/b.py", "B = 1\n")
    assert ck(repo, "T2").returncode == 0
    write(repo, "src/c.py", "C = 1\n")
    r = ck(repo, "T3")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "owned by" not in r.stderr


def test_owner_in_same_call_silent(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/b.py", "B = 1\n")
    assert ck(repo, "T2").returncode == 0
    write(repo, "src/b.py", "B = 2\n")
    write(repo, "src/c.py", "C = 1\n")
    r = ck(repo, "T3", "T2")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "owned by" not in r.stderr
    lines = r.stdout.strip().splitlines()
    assert lines[0].startswith("T3 ") and lines[1].startswith("T2 ")
    assert git(repo, "show", f"{lines[1].split()[1]}:src/b.py") == "B = 2"


def test_owned_note_once_per_call(tmp_path):
    repo = setup(tmp_path)
    write(repo, "src/b.py", "B = 1\n")
    assert ck(repo, "T2").returncode == 0
    write(repo, "src/b.py", "B = 2\n")
    write(repo, "src/c.py", "C = 1\n")
    write(repo, "src/d.py", "D = 1\n")
    r = ck(repo, "T3", "T4")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stderr.count(NOTE + "src/b.py") == 1


def test_claimed_line_once_per_call(tmp_path):
    repo = setup(tmp_path)
    assert ck(repo, "T4", "--claim", "notes/x.md", "--ruling", "needed").returncode == 0
    write(repo, "notes/x.md", "x\n")
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "src/b.py", "B = 1\n")
    write(repo, "src/c.py", "C = 1\n")
    r = ck(repo, "T1", "T2", "T3")
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stderr.count("left uncommitted (claimed by T4; commit_task T4 commits it once T4 is done): notes/x.md") == 1


def test_note_once_in_process(capsys):
    ns = types.SimpleNamespace()
    assert commit_task.note_once(ns, "x") is True
    assert capsys.readouterr().err == "x\n"
    assert commit_task.note_once(ns, "x") is False
    assert capsys.readouterr().err == ""


def test_committed_owners_examples():
    info = {
        "T1": {"owns": ["src/shared.py"]},
        "T2": {"owns": ["src/b.py", "src/shared.py"]},
        "T3": {"owns": ["src/c.py"]},
    }
    assert commit_task.committed_owners("src/b.py", info, ["T3"], {"T2"}, []) == ["T2"]
    assert commit_task.committed_owners("src/shared.py", info, ["T3"], {"T1", "T2"}, ["T2"]) == []
    assert commit_task.committed_owners("src/shared.py", info, ["T3"], {"T1", "T2"}, []) == ["T1", "T2"]
    assert commit_task.committed_owners("src/b.py", info, ["T3", "T2"], {"T2"}, []) == []
    assert commit_task.committed_owners("src/b.py", info, ["T3"], set(), []) == []
