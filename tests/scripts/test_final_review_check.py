import json
import os
import shutil
import subprocess
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "final-review-check"
STOP = ROOT / "hooks" / "capture-agent-stop"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


def git(cwd, *a):
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, check=True,
                   capture_output=True)


def commit_files(cwd, names, lines=1, msg="c"):
    for n in names:
        p = Path(cwd) / n
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n" * lines)
    git(cwd, "add", "-A")
    git(cwd, "commit", "-m", msg)


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-b", "main")
    commit_files(tmp_path, ["base.txt"])
    git(tmp_path, "switch", "-c", "feat")
    return tmp_path


def run(proj, payload=None, env=None, hook=HOOK):
    e = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_STATE_DIR": "", **(env or {})}
    e.pop("SUPERLITE_FINAL_REVIEW", None) if not env or "SUPERLITE_FINAL_REVIEW" not in env else None
    return subprocess.run([BASH, str(hook)], input=json.dumps(payload or {}), capture_output=True,
                          text=True, env=e)


def big(repo):
    commit_files(repo, [f"src/f{i}.py" for i in range(6)])


def test_blocks_once_on_big_branch(repo):
    big(repo)
    r = run(repo)
    assert r.returncode == 0
    out = json.loads(r.stdout)
    assert out["decision"] == "block" and "feat" in out["reason"]
    assert "superlite:final-reviewer" in out["reason"] and len(out["reason"]) < 300
    r2 = run(repo)
    assert r2.returncode == 0 and r2.stdout == ""


def test_silent_on_default_branch(repo):
    git(repo, "switch", "main")
    commit_files(repo, [f"src/f{i}.py" for i in range(6)])
    assert run(repo).stdout == ""


def test_silent_on_small_diff(repo):
    commit_files(repo, ["a.py", "b.py"], lines=10)
    assert run(repo).stdout == ""


def test_blocks_on_many_lines(repo):
    commit_files(repo, ["a.py"], lines=200)
    assert json.loads(run(repo).stdout)["decision"] == "block"


def test_docs_only_diff_is_small(repo):
    commit_files(repo, [f"docs/d{i}.md" for i in range(8)])
    assert run(repo).stdout == ""


def metrics(repo, rec):
    d = repo / ".superlite"
    d.mkdir(exist_ok=True)
    (d / "metrics.jsonl").write_text(json.dumps(rec) + "\n")


def test_silent_when_reviewer_stopped_after_base(repo):
    big(repo)
    metrics(repo, {"ev": "stop", "t": time.time() * 1000 + 5000, "type": "superlite:final-reviewer"})
    assert run(repo).stdout == ""


def test_blocks_when_reviewer_stop_is_older_than_base(repo):
    big(repo)
    metrics(repo, {"ev": "stop", "t": (time.time() - 3600) * 1000, "type": "superlite:final-reviewer"})
    assert json.loads(run(repo).stdout)["decision"] == "block"


def test_other_agent_type_does_not_count(repo):
    big(repo)
    metrics(repo, {"ev": "stop", "t": time.time() * 1000 + 5000, "type": "implementer"})
    assert json.loads(run(repo).stdout)["decision"] == "block"


def test_unreadable_metrics_is_no_record(repo):
    big(repo)
    d = repo / ".superlite" / "metrics.jsonl"
    d.parent.mkdir()
    d.mkdir()  # a directory: cannot be read as a file
    assert json.loads(run(repo).stdout)["decision"] == "block"


def test_silent_when_stop_hook_active(repo):
    big(repo)
    assert run(repo, {"stop_hook_active": True}).stdout == ""


def test_silent_when_env_off(repo):
    big(repo)
    assert run(repo, env={"SUPERLITE_FINAL_REVIEW": "off"}).stdout == ""


def test_silent_on_detached_head(repo):
    big(repo)
    git(repo, "checkout", "--detach")
    assert run(repo).stdout == ""


def test_silent_outside_git(tmp_path):
    r = run(tmp_path)
    assert r.returncode == 0 and r.stdout == ""


def test_falls_back_to_master(tmp_path):
    git(tmp_path, "init", "-b", "master")
    commit_files(tmp_path, ["base.txt"])
    assert run(tmp_path).stdout == ""  # on the default branch
    git(tmp_path, "switch", "-c", "feat")
    big(tmp_path)
    assert json.loads(run(tmp_path).stdout)["decision"] == "block"


def test_capture_stop_records_final_reviewer_without_run(tmp_path):
    payload = {"agent_id": "a1", "agent_type": "superlite:final-reviewer", "last_assistant_message": "ok"}
    r = run(tmp_path, payload, hook=STOP)
    assert r.returncode == 0
    lines = (tmp_path / ".superlite" / "metrics.jsonl").read_text().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["type"] == "superlite:final-reviewer"


def test_capture_stop_ignores_other_type_without_run(tmp_path):
    run(tmp_path, {"agent_id": "a1", "agent_type": "implementer"}, hook=STOP)
    assert not (tmp_path / ".superlite" / "metrics.jsonl").exists()


def test_untracked_files_count(repo):
    for i in range(6):
        (repo / f"new{i}.py").write_text("x\n")
    assert json.loads(run(repo).stdout)["decision"] == "block"


def test_untracked_docs_do_not_count(repo):
    (repo / "docs").mkdir()
    for i in range(6):
        (repo / "docs" / f"n{i}.md").write_text("x\n")
    assert run(repo).stdout == ""


def test_origin_head_default_branch(tmp_path):
    up = tmp_path / "up"
    up.mkdir()
    git(up, "init", "-b", "trunk")
    commit_files(up, ["base.txt"])
    cl = tmp_path / "cl"
    subprocess.run(["git", "clone", str(up), str(cl)], check=True, capture_output=True)
    assert run(cl).stdout == ""
    git(cl, "switch", "-c", "feat")
    big(cl)
    assert json.loads(run(cl).stdout)["decision"] == "block"
    git(cl, "switch", "trunk")
    assert run(cl).stdout == ""


def _status(cwd):
    return subprocess.run(["git", "status", "--porcelain"], cwd=cwd, capture_output=True, text=True).stdout


def test_block_does_not_litter_git_status(repo):
    big(repo)
    assert json.loads(run(repo).stdout)["decision"] == "block"
    assert (repo / ".superlite" / "final-review-warned").exists()
    assert ".superlite" not in _status(repo)


def test_capture_stop_without_run_does_not_litter_git_status(repo):
    run(repo, {"agent_id": "a", "agent_type": "superlite:final-reviewer"}, hook=STOP)
    assert (repo / ".superlite" / "metrics.jsonl").exists()
    assert ".superlite" not in _status(repo)
    run(repo, {"agent_id": "b", "agent_type": "superlite:final-reviewer"}, hook=STOP)
    assert (repo / ".git" / "info" / "exclude").read_text().count(".superlite") == 1


def test_reads_metrics_from_state_dir_override(repo, tmp_path_factory):
    big(repo)
    sd = tmp_path_factory.mktemp("sd")
    run(repo, {"agent_id": "a", "agent_type": "superlite:final-reviewer"}, env={"SUPERLITE_STATE_DIR": str(sd)}, hook=STOP)
    assert (sd / "metrics.jsonl").exists()
    assert run(repo, env={"SUPERLITE_STATE_DIR": str(sd)}).stdout == ""


def test_run_markers_not_created_by_hooks(repo):
    big(repo)
    run(repo)
    run(repo, {"agent_id": "a", "agent_type": "superlite:final-reviewer"}, hook=STOP)
    for m in ("pool.json", "prime.md", "stable.json"):
        assert not (repo / ".superlite" / m).exists()


def test_branch_with_slash_blocks_once(repo):
    git(repo, "switch", "-c", "topic/a-b")
    big(repo)
    assert json.loads(run(repo).stdout)["decision"] == "block"
    assert run(repo).stdout == ""
