"""commit_task: a tracked, modified test under tests/ that no task owns joins the committing task."""
import json
import os
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import (SCRIPTS, ENV, git, make_repo, run, write)  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402

SHARED = "tests/test_shared.py"
SRC_ENV_OFF = {**ENV, "SUPERLITE_AUTOCOMMIT": "0"}


def repo_with_shared(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, SHARED, "def test_s():\n    assert True\n")
    write(repo, "src/other.py", "Y = 1\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "shared")
    return repo


def commit(repo, env=ENV):
    return run("commit_task", "T1", "--plan", "plan.md", cwd=repo, env=env)


def incidents(repo):
    p = repo / ".superlite" / "incidents.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []


def test_modified_shared_test_joins_task(tmp_path):
    repo = repo_with_shared(tmp_path)
    write(repo, "src/a.py", "X = 1\n")
    write(repo, SHARED, "def test_s():\n    assert 1 == 1\n")
    r = commit(repo)
    assert r.returncode == 0, r.stdout + r.stderr
    assert r.stdout.strip() == git(repo, "rev-parse", "HEAD")
    assert f"shared-test {SHARED}" in r.stderr
    assert f"shared-test" not in r.stdout
    assert git(repo, "show", "--name-only", "--format=", "HEAD").splitlines() == ["src/a.py", SHARED]
    inc = [i for i in incidents(repo) if i.get("kind") == "workaround"]
    assert len(inc) == 1 and "T1: shared test adjusted" in json.dumps(inc[0])
    assert inc[0].get("resolution") == "accepted"


def test_shared_test_joins_checkpoint(tmp_path):
    repo = repo_with_shared(tmp_path)
    write(repo, "src/a.py", "X = 1\n")
    write(repo, SHARED, "def test_s():\n    assert 1 == 1\n")
    r = commit(repo, SRC_ENV_OFF)
    assert r.returncode == 0, r.stdout + r.stderr
    sha = r.stdout.strip()
    assert git(repo, "show", "--name-only", "--format=", sha).splitlines() == ["src/a.py", SHARED]
    assert git(repo, "show", f"{sha}:{SHARED}") == "def test_s():\n    assert 1 == 1"
    state = json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))
    assert set(state["entries"][-1]["files"]) == {"src/a.py", SHARED}


def test_new_unowned_test_still_blocks(tmp_path):
    repo = repo_with_shared(tmp_path)
    write(repo, "src/a.py", "X = 1\n")
    write(repo, "tests/test_new.py", "def test_n():\n    pass\n")
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope tests/test_new.py" in r.stdout


def test_deleted_shared_test_still_blocks(tmp_path):
    repo = repo_with_shared(tmp_path)
    write(repo, "src/a.py", "X = 1\n")
    os.remove(repo / SHARED)
    r = commit(repo)
    assert r.returncode == 1
    assert f"out-of-scope {SHARED}" in r.stdout


def test_unowned_source_still_blocks(tmp_path):
    repo = repo_with_shared(tmp_path)
    write(repo, "src/a.py", "X = 1\n")
    write(repo, "src/other.py", "Y = 2\n")
    r = commit(repo)
    assert r.returncode == 1
    assert "out-of-scope src/other.py" in r.stdout


def test_shared_test_cases():
    st = commit_task.shared_test
    assert st("tests/scripts/test_a.py", " M") is True
    assert st("tests/scripts/test_a.py", "M ") is True
    assert st("tests/scripts/test_a.py", "MM") is True
    assert st("tests/x.py", "??") is False
    assert st("tests/x.py", "A ") is False
    assert st("tests/x.py", " D") is False
    assert st("src/a.py", " M") is False
    assert st("pkg/tests/t.py", " M") is True


def test_changed_entries(tmp_path, monkeypatch):
    repo = repo_with_shared(tmp_path)
    write(repo, SHARED, "x\n")
    write(repo, "src/new.py", "N\n")
    monkeypatch.chdir(repo)
    assert commit_task.changed_entries() == [("src/new.py", "??"), (SHARED, " M")]
    assert commit_task.changed_files() == ["src/new.py", SHARED]


def test_t0_never_takes_shared_test(tmp_path):
    repo = repo_with_shared(tmp_path)
    plan = (repo / "plan.md").read_text(encoding="utf-8")
    plan += "\n### T0 · setup · Complexity 1 · Est. context 5k · Est. time 1 min\n\n**Owns:** `cfg/x.txt`\n"
    (repo / "plan.md").write_text(plan, encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    write(repo, "cfg/x.txt", "1\n")
    write(repo, SHARED, "def test_s():\n    assert 2 == 2\n")
    r = run("commit_task", "T0", "--plan", "plan.md", cwd=repo, env=ENV)
    assert r.returncode == 1, r.stdout + r.stderr
    assert f"out-of-scope {SHARED}" in r.stdout
    assert "shared-test" not in r.stderr


def test_changed_entries_path_with_space(tmp_path, monkeypatch):
    repo = repo_with_shared(tmp_path)
    write(repo, "tests/my test.py", "x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "sp")
    write(repo, "tests/my test.py", "y\n")
    monkeypatch.chdir(repo)
    assert commit_task.changed_entries() == [("tests/my test.py", " M")]


def _t(repo, tid):
    return run("commit_task", tid, "--plan", "plan.md", cwd=repo, env=SRC_ENV_OFF)


def test_checkpointed_shared_test_not_retaken(tmp_path):
    repo = repo_with_shared(tmp_path)
    write(repo, "src/a.py", "X = 1\n")
    write(repo, SHARED, "def test_s():\n    assert 1 == 1\n")
    r1 = _t(repo, "T1")
    assert r1.returncode == 0 and f"shared-test {SHARED}" in r1.stderr
    write(repo, "src/b.py", "B = 1\n")
    r2 = _t(repo, "T2")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert "shared-test" not in r2.stderr
    state = json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))
    assert SHARED not in state["entries"][-1]["files"]
    inc = [i for i in incidents(repo) if "shared test adjusted" in json.dumps(i)]
    assert len(inc) == 1


def test_shared_test_changed_again_is_retaken(tmp_path):
    repo = repo_with_shared(tmp_path)
    write(repo, "src/a.py", "X = 1\n")
    write(repo, SHARED, "def test_s():\n    assert 1 == 1\n")
    assert _t(repo, "T1").returncode == 0
    write(repo, "src/b.py", "B = 1\n")
    write(repo, SHARED, "def test_s():\n    assert 2 == 2\n")
    r2 = _t(repo, "T2")
    assert r2.returncode == 0, r2.stdout + r2.stderr
    assert f"shared-test {SHARED}" in r2.stderr
    state = json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))
    assert SHARED in state["entries"][-1]["files"]
