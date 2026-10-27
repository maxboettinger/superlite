"""commit_task: an unowned file while another task runs is left uncommitted, not a block."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import (SCRIPTS, ENV, git, make_repo, run, write)  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import commit_task  # noqa: E402


def commit(repo, *args):
    return run("commit_task", *args, "--plan", "plan.md", cwd=repo, env=ENV)


def pool(repo, agents):
    p = repo / ".superlite" / "pool.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"agents": agents}), encoding="utf-8")
    return p


def test_others_running(tmp_path):
    p = pool(tmp_path, [{"busy": True, "current": "T1"}, {"busy": False}])
    assert commit_task.others_running(str(p), ["T5"]) == ["T1"]
    assert commit_task.others_running(str(p), ["T1"]) == []


def test_missing_pool_means_none_running(tmp_path):
    assert commit_task.others_running(str(tmp_path / "nope.json"), ["T5"]) == []
    bad = tmp_path / "bad.json"
    bad.write_text("{", encoding="utf-8")
    assert commit_task.others_running(str(bad), ["T5"]) == []


def test_unowned_file_warns_while_other_task_runs(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "stray/new.txt", "x\n")
    pool(repo, [{"busy": True, "current": "T2"}])
    r = commit(repo, "T1")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "left uncommitted (another task is running: T2): stray/new.txt" in r.stderr
    assert "out-of-scope" not in r.stdout
    log = repo / ".superlite" / "incidents.jsonl"
    assert not log.exists() or "stray/new.txt" not in log.read_text(encoding="utf-8")
    assert "stray/new.txt" in git(repo, "status", "--porcelain", "--untracked-files=all")


def test_unowned_file_blocks_when_none_running(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "stray/new.txt", "x\n")
    pool(repo, [{"busy": False}])
    r = commit(repo, "T1")
    assert r.returncode == 1
    assert "out-of-scope stray/new.txt" in r.stdout


def test_own_files_still_committed(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "stray/new.txt", "x\n")
    pool(repo, [{"busy": True, "current": "T2"}])
    r = commit(repo, "T1")
    sha = r.stdout.strip().splitlines()[-1]
    assert sorted(git(repo, "show", "--name-only", "--format=", sha).split()) == ["src/a.py"]


def test_own_busy_agent_does_not_count_as_other_running(tmp_path):
    repo = make_repo(tmp_path)
    write(repo, "src/a.py", "A = 1\n")
    write(repo, "stray/new.txt", "x\n")
    pool(repo, [{"busy": True, "current": "T1"}])
    r = commit(repo, "T1")
    assert r.returncode == 1
    assert "out-of-scope stray/new.txt" in r.stdout
    assert "left uncommitted" not in r.stderr
