"""Gate events from the six decision hooks (#933): one `gate` line per decision, the hook's own output unchanged."""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import telemetry  # noqa: E402

HOOKS = ROOT / "hooks"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
SID = "s933"


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@t", *a], cwd=cwd, check=True, capture_output=True, env=env)


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "proj"
    (p / ".superlite").mkdir(parents=True)
    (p / ".superlite" / "pool.json").write_text("{}")
    return p


def env_for(proj, **extra):
    e = {k: v for k, v in os.environ.items()
         if not k.startswith("SUPERLITE_") or k == "SUPERLITE_HOME"}
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "CLAUDE_CODE_SESSION_ID"):
        e.pop(k, None)
    e.update({"CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_STATE_DIR": str(proj / ".superlite")})
    e.update(extra)
    return e


def run_hook(name, payload, env):
    return subprocess.run([BASH, str(HOOKS / name)], input=json.dumps(payload), capture_output=True, text=True, env=env)


def gate(name, payload, env, rc=None):
    """Run the hook with telemetry on, then off: output must match; returns the gate lines of the first run."""
    before = len(telemetry.read_events())
    on = run_hook(name, payload, env)
    lines = telemetry.read_events()[before:]
    off = run_hook(name, payload, {**env, "SUPERLITE_TELEMETRY": "0"})
    assert (on.returncode, on.stdout, on.stderr) == (off.returncode, off.stdout, off.stderr)
    assert len(telemetry.read_events()) == before + len(lines)  # the off run wrote nothing
    if rc is not None:
        assert on.returncode == rc, on.stderr
    return lines, on


def one(lines, hook):
    assert len(lines) == 1, lines
    line = lines[0]
    assert telemetry.validate(line) == []
    assert line["kind"] == "gate" and line["hook"] == hook and line["session"] == SID
    return line


def test_kind_gate_block_coordinator_edits(proj):
    payload = {"session_id": SID, "tool_name": "Write", "tool_input": {"file_path": str(proj / "app.py"), "content": "x"},
               "cwd": str(proj)}
    lines, _ = gate("block-coordinator-edits", payload, env_for(proj), rc=2)
    line = one(lines, "block-coordinator-edits")
    assert (line["decision"], line["rule"], line["tool"]) == ("block", "code", "Write")
    assert line["target"].endswith("app.py")


def test_kind_gate_block_unsafe_kill(proj):
    payload = {"session_id": SID, "tool_name": "Bash", "tool_input": {"command": "pkill -f node"}, "cwd": str(proj)}
    lines, _ = gate("block-unsafe-kill", payload, env_for(proj), rc=2)
    line = one(lines, "block-unsafe-kill")
    assert (line["decision"], line["rule"], line["tool"], line["target"]) == ("block", "kill-pattern", "Bash", "pkill -f node")


def test_kind_gate_rewrite_test_runs_rewrite(proj):
    payload = {"session_id": SID, "tool_name": "Bash", "tool_input": {"command": "pytest"}, "cwd": str(proj)}
    lines, _ = gate("rewrite-test-runs", payload, env_for(proj), rc=0)
    line = one(lines, "rewrite-test-runs")
    assert (line["decision"], line["rule"], line["tool"]) == ("rewrite", "raw-test-run", "Bash")
    assert line["target"].startswith("pytest -> ") and "run_tests" in line["target"]


def test_kind_gate_rewrite_test_runs_deny(proj):
    payload = {"session_id": SID, "tool_name": "Bash", "tool_input": {"command": "pytest"}, "agent_id": "a1", "cwd": str(proj)}
    lines, _ = gate("rewrite-test-runs", payload, env_for(proj), rc=2)
    line = one(lines, "rewrite-test-runs")
    assert (line["decision"], line["rule"], line["tool"], line["target"]) == ("deny", "subagent-full-suite", "Bash", "pytest")


def test_kind_gate_inline_worktree_guard(tmp_path):
    repo = tmp_path / "repo"
    (repo / ".superlite").mkdir(parents=True)
    (repo / "src").mkdir()
    git(repo, "init", "-q", "-b", "main")
    (repo / ".superlite" / "inline-flow.json").write_text(json.dumps({"flow": "small", "at": 1, "inplace": None}))
    payload = {"session_id": SID, "tool_name": "Edit", "tool_input": {"file_path": str(repo / "src" / "a.py")}, "cwd": str(repo)}
    env = env_for(repo, SUPERLITE_STATE_DIR=str(repo / ".superlite"))
    lines, _ = gate("inline-worktree-guard", payload, env, rc=2)
    line = one(lines, "inline-worktree-guard")
    assert (line["decision"], line["rule"], line["tool"], line["target"]) == ("block", "inline-main-checkout", "Edit", "src/a.py")


def test_kind_gate_deny_worker_permission(proj):
    payload = {"session_id": SID, "hook_event_name": "PermissionRequest", "tool_name": "Bash", "cwd": str(proj)}
    lines, r = gate("deny-worker-permission", payload, env_for(proj, SUPERLITE_FLEET_WORKER="W1"), rc=0)
    line = one(lines, "deny-worker-permission")
    assert (line["decision"], line["rule"], line["tool"]) == ("deny", "worker-permission", "Bash")


def test_kind_gate_final_review_check(tmp_path):
    repo = tmp_path / "fr"
    repo.mkdir()
    git(repo, "init", "-b", "main")
    (repo / "base.txt").write_text("x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "c")
    git(repo, "switch", "-c", "feat")
    for i in range(6):
        (repo / f"f{i}.py").write_text("x\n")
    git(repo, "add", "-A")
    git(repo, "commit", "-m", "big")
    payload = {"session_id": SID, "cwd": str(repo)}
    env = env_for(repo, SUPERLITE_STATE_DIR="")
    # the warning is shown once per branch: the off run only compares after the on run, so run on a copy of the marker state
    on = run_hook("final-review-check", payload, env)
    lines = telemetry.read_events()
    line = one(lines, "final-review-check")
    assert on.returncode == 0 and json.loads(on.stdout)["decision"] == "block"
    assert (line["decision"], line["rule"], line["target"]) == ("warn", "final-review-missing", "feat")
    warned = [p for p in repo.rglob("final-review-warned")]
    assert warned
    for p in warned:
        p.unlink()
    off = run_hook("final-review-check", payload, {**env, "SUPERLITE_TELEMETRY": "0"})
    assert (on.returncode, on.stdout, on.stderr) == (off.returncode, off.stdout, off.stderr)
    assert len(telemetry.read_events()) == 1


def test_kind_gate_outputs_unchanged(proj):
    """Every decision case above compares its exit code, stdout and stderr with SUPERLITE_TELEMETRY=0 inside gate()."""
    payload = {"session_id": SID, "tool_name": "Bash", "tool_input": {"command": "pkill -f node"}, "cwd": str(proj)}
    lines, on = gate("block-unsafe-kill", payload, env_for(proj), rc=2)
    assert lines and "kills processes by name" in on.stderr
    # an unwritable home changes nothing either
    bad = env_for(proj, SUPERLITE_HOME=str(proj / ".superlite" / "pool.json" / "nope"))
    r = run_hook("block-unsafe-kill", payload, bad)
    assert (r.returncode, r.stdout, r.stderr) == (on.returncode, on.stdout, on.stderr)


def test_kind_gate_allow_writes_nothing(proj):
    before = len(telemetry.read_events())
    docs = {"session_id": SID, "tool_name": "Write", "tool_input": {"file_path": str(proj / "docs" / "plans" / "p.md"), "content": "x"},
            "cwd": str(proj)}
    assert run_hook("block-coordinator-edits", docs, env_for(proj)).returncode == 0
    ls = {"session_id": SID, "tool_name": "Bash", "tool_input": {"command": "ls"}, "cwd": str(proj)}
    assert run_hook("block-unsafe-kill", ls, env_for(proj)).returncode == 0
    r = run_hook("rewrite-test-runs", ls, env_for(proj))
    assert (r.returncode, r.stdout) == (0, "")
    assert run_hook("deny-worker-permission", {"session_id": SID}, env_for(proj)).returncode == 0
    assert len(telemetry.read_events()) == before
