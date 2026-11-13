"""`sl run active` (#671): is a run active, for third-party Stop hooks."""
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
SL = SCRIPTS / "sl"


def env_for(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k != "CLAUDE_CODE_SESSION_ID"}
    env.update(SUPERLITE_HOME=str(tmp_path / "home"), SUPERLITE_CACHE_DIR=str(tmp_path / "cache"))
    return env


def sl(tmp_path, cwd, *args):
    return subprocess.run(["bash", str(SL), "run", *args], capture_output=True, text=True, cwd=cwd, env=env_for(tmp_path))


def git(cwd, *args):
    return subprocess.run(["git", *args], cwd=cwd, capture_output=True, text=True, check=True).stdout


def make_repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.name", "T")
    git(path, "config", "user.email", "t@example.com")
    git(path, "config", "commit.gpgsign", "false")
    (path / "README.md").write_text("x\n")
    git(path, "add", "-A")
    git(path, "commit", "-q", "-m", "base")
    return path


def jwrite(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data), encoding="utf-8")


def repo(tmp_path):
    return make_repo(tmp_path / "repo")


def test_no_run_exit_1(tmp_path):
    r = repo(tmp_path)
    p = sl(tmp_path, r, "active")
    assert (p.returncode, p.stdout) == (1, f"run active: none in {r}/.superlite\n")
    p = sl(tmp_path, r, "active", "--json")
    d = json.loads(p.stdout)
    assert p.returncode == 1 and d["active"] is False and d["kind"] is None


def test_plan_run(tmp_path):
    r = repo(tmp_path)
    jwrite(r / ".superlite/stable.json", {})
    jwrite(r / ".superlite/pool.json", {"agents": [{"id": "a1", "busy": True}]})
    p = sl(tmp_path, r, "active", "--json")
    d = json.loads(p.stdout)
    assert p.returncode == 0
    assert d["kind"] == "plan run" and d["markers"] == ["stable.json", "pool.json"]
    assert d["worktrees"][0]["busy"] == ["a1"]


def test_backlog_main_running_batch(tmp_path):
    r = repo(tmp_path)
    wt = tmp_path / "wt"
    jwrite(wt / ".superlite/fleet.json", {"workers": {"W2": {"state": "busy"}}})
    jwrite(r / ".superlite/backlog.json", {"batches": [
        {"id": "B1", "state": "running", "worktree": str(wt)}, {"id": "B2", "state": "shipped"}]})
    p = sl(tmp_path, r, "active", "--json")
    d = json.loads(p.stdout)
    assert p.returncode == 0 and d["kind"] == "backlog main"
    assert [w["path"] for w in d["worktrees"]] == [str(r), str(wt)]
    assert d["worktrees"][1]["busy"] == ["W2"]


def test_lead_worktree(tmp_path):
    r = repo(tmp_path)
    wt = tmp_path / "lead-wt"
    git(r, "worktree", "add", "-q", "-b", "lead", str(wt))
    jwrite(r / ".superlite/backlog.json", {"batches": [{"id": "B7", "state": "running", "worktree": str(wt)}]})
    p = sl(tmp_path, wt, "active", "--json")
    d = json.loads(p.stdout)
    assert p.returncode == 0 and d["kind"] == "lead" and d["batch"] == "B7"


def test_checkpoint_files_listed(tmp_path):
    r = repo(tmp_path)
    jwrite(r / ".superlite/orchestrator.json", {"mode": "ai"})
    (r / "a.py").write_text("a = 1\n")
    (r / "b.py").write_text("b = 1\n")
    code = (f"import sys; sys.path.insert(0, {str(SCRIPTS)!r}); import autocommit; "
            f"autocommit.record('T1', 't', ['a.py', 'b.py'], {str(r / 'plan.md')!r})")
    env = {**env_for(tmp_path), "SUPERLITE_AUTOCOMMIT": "0"}
    subprocess.run([sys.executable, "-c", code], cwd=r, env=env, check=True, capture_output=True)
    (r / "b.py").write_text("b = 2\n")
    d = json.loads(sl(tmp_path, r, "active", "--json").stdout)
    assert d["checkpoint_files"] == ["a.py"] and d["edited_after_checkpoint"] == ["b.py"]
    out = sl(tmp_path, r, "active").stdout
    assert "checkpoint files: 1: a.py" in out and "edited after checkpoint: 1: b.py" in out


def test_plan_flag(tmp_path):
    r = repo(tmp_path)
    p = sl(tmp_path, tmp_path, "active", "--plan", str(r / ".superlite"), "--json")
    assert json.loads(p.stdout)["state_dir"] == str(r / ".superlite")


def test_session_flag(tmp_path):
    r = repo(tmp_path)
    other = make_repo(tmp_path / "other")
    jwrite(other / ".superlite/pool.json", {"agents": [{"id": "a1", "busy": True}]})
    b = tmp_path / "home/sessions/s1"
    b.parent.mkdir(parents=True)
    b.write_text(f"{other}/.superlite\n")
    p = sl(tmp_path, r, "active", "--session", "s1", "--json")
    d = json.loads(p.stdout)
    assert d["state_dir"] == f"{other}/.superlite" and d["kind"] == "plan run"


def test_bad_session_exit_2(tmp_path):
    p = sl(tmp_path, repo(tmp_path), "active", "--session", "../x")
    assert (p.returncode, p.stderr.strip()) == (2, "run: bad session id: ../x")


def test_usage_exit_2(tmp_path):
    r = repo(tmp_path)
    for args in ([], ["nope"]):
        p = sl(tmp_path, r, *args)
        assert p.returncode == 2 and "active" in p.stderr


def test_docs_name_command():
    hooks = (ROOT / "docs/hooks.md").read_text(encoding="utf-8")
    sec = hooks.split("## Detecting an active run", 1)[1]
    for w in ("sl run active", "orchestrator.json", "backlog.json", "--session", "checkpoint_files", "edited_after_checkpoint"):
        assert w in sec
    assert "sl run active [--plan P] [--session SID] [--json]" in (ROOT / "docs/tools.md").read_text(encoding="utf-8")
