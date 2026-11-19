import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "block-unsafe-kill"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
MSG = "fleet workers never run git checkout, git restore or git stash"
WORKER = {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_ROLE": "fixer"}


@pytest.fixture(autouse=True)
def fake_ps(tmp_path, monkeypatch):
    """A harmless `ps` first on PATH, so no test reaches the real process table."""
    bindir = tmp_path / "fakebin"
    bindir.mkdir()
    ps = bindir / "ps"
    ps.write_text("#!/bin/sh\necho /usr/bin/true\n", encoding="utf-8")
    ps.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))


def run(command, tool="Bash", env=WORKER, home=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_FLEET_")}
    e.update(env)
    if home is not None:
        e["SUPERLITE_HOME"] = str(home)
    raw = json.dumps({"tool_name": tool, "tool_input": {"command": command}})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=e)


BLOCKED = [
    "git checkout -- a.py",
    "git -C /tmp/x checkout -- a.py",
    "git -C /tmp/x restore a.py",
    "git -C /tmp/x stash",
    "git -C a -C b stash pop",
    "git -c core.x=1 restore --staged a.py",
    "git --git-dir=/tmp/x/.git --work-tree=/tmp/x checkout main",
    "git --git-dir /tmp/x/.git checkout main",
    "git --no-pager -P stash list",
    "/usr/bin/git -C d restore .",
    "cd /tmp && git -C d checkout x",
    "echo $(git -C d stash)",
    "bash -c 'git -C d restore a'",
    "env GIT_DIR=x git checkout y",
    "sudo git -C d restore a",
]


@pytest.mark.parametrize("command", BLOCKED)
def test_worker_git_forms_blocked(command):
    r = run(command)
    assert r.returncode == 2, command
    assert MSG in r.stderr


def test_worker_git_forms_blocked_monitor():
    r = run("git -C d checkout x", tool="Monitor")
    assert r.returncode == 2
    assert MSG in r.stderr


@pytest.mark.parametrize(
    "command",
    [
        "git -C /tmp/x status",
        "git -C /tmp/x diff -- a.py",
        "git -C d log --oneline",
        'git add a.py && git commit -m "fix checkout"',
        "git -C d show HEAD:a.py",
        "git branch --list",
        "git -c x=1 rev-parse HEAD",
    ],
)
def test_worker_git_allowed_forms(command):
    r = run(command)
    assert (r.returncode, r.stderr) == (0, ""), command


@pytest.mark.parametrize(
    "command",
    [
        'echo "git checkout x"',
        'grep -n "git restore" a.md',
        "printf '%s\\n' 'git -C d stash'",
        "cat <<'EOF'\ngit stash\nEOF",
        "ls # git checkout x",
    ],
)
def test_git_words_in_data_never_block(command):
    assert run(command).returncode == 0, command


@pytest.mark.parametrize("command", ["git -C d checkout x", "git stash"])
@pytest.mark.parametrize(
    "env", [{"SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_FLEET_WORKER": "L1"}, {}], ids=["lead", "no-fleet"]
)
def test_lead_and_coordinator_not_blocked(command, env):
    assert run(command, env=env).returncode == 0


def test_kill_rules_unchanged_for_worker():
    r = run("pkill -f x")
    assert r.returncode == 2 and "kills processes by name or pattern" in r.stderr
    assert run("kill 123").returncode == 0


def test_worker_git_block_telemetry(tmp_path):
    r = run("git -C d checkout x", home=tmp_path)
    assert r.returncode == 2
    lines = [json.loads(x) for x in (tmp_path / "events.jsonl").read_text().splitlines()]
    assert len(lines) == 1
    assert (lines[0]["kind"], lines[0]["decision"], lines[0]["rule"]) == ("gate", "block", "worker-git")


def test_powershell_worker_git_blocked():
    r = run("git -C d checkout x", tool="PowerShell")
    assert r.returncode == 2
    assert MSG in r.stderr
