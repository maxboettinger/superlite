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

XCODE = "/Applications/Xcode.app/Contents/MacOS/Xcode"
SHARED = (
    "Xcode", "Simulator", "mcpbridge", "SourceKitService", "com.apple.dt.SKAgent",
    "com.apple.dt.Xcode.sourcekit", "com.apple.CoreSimulator.CoreSimulatorService",
    "com.apple.CoreSimulator.SimulatorTrampoline", "herdr", "claude", "launchd",
    "WindowServer", "Finder", "Dock", "loginwindow",
)


@pytest.fixture
def fake_ps(tmp_path):
    """A `ps` on PATH that logs its arguments and prints $PS_OUT (ps is the environment, not a producer)."""
    bindir = tmp_path / "bin"
    bindir.mkdir()
    log = tmp_path / "ps.log"
    ps = bindir / "ps"
    ps.write_text('#!/bin/sh\necho "$*" >> "$PS_LOG"\nprintf \'%s\\n\' "$PS_OUT"\n', encoding="utf-8")
    ps.chmod(0o755)
    state = {"out": ""}

    def set_out(out):
        state["out"] = out

    return {"path": str(bindir), "log": log, "set": set_out, "state": state}


def run(cmd, fake, tool="Bash", path=None):
    env = dict(os.environ)
    env["PATH"] = fake["path"] if path is None else path
    env["PS_LOG"] = str(fake["log"])
    env["PS_OUT"] = fake.get("state", {}).get("out", "")
    raw = json.dumps({"tool_name": tool, "tool_input": {"command": cmd}})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def calls(fake):
    p = fake["log"]
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else []


def test_kill_xcode_pid_blocked(fake_ps):
    fake_ps["set"](XCODE)
    for cmd in ("kill 4242", "kill -9 4242"):
        r = run(cmd, fake_ps)
        assert r.returncode == 2, cmd
        assert "Xcode" in r.stderr, cmd
        assert "ask" in r.stderr.lower(), cmd
    assert calls(fake_ps) == ["-o comm= -p 4242", "-o comm= -p 4242"]
    fake_ps["set"]("/usr/bin/python3")
    r = run("kill 4242", fake_ps)
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""


def test_each_shared_name(fake_ps):
    for name in SHARED:
        fake_ps["set"](f"/System/Library/{name}.app/Contents/MacOS/{name}")
        r = run("kill 77", fake_ps)
        assert r.returncode == 2, name
        assert name in r.stderr, name
        fake_ps["set"](name)  # a bare comm, as ps prints for a kernel or login process
        assert run("kill -TERM 77", fake_ps).returncode == 2, name
    fake_ps["set"]("/usr/bin/XCODE")  # case-insensitive
    assert run("kill 77", fake_ps).returncode == 2


def test_other_names_pass(fake_ps):
    for out in ("/usr/bin/python3", "/opt/claudette", "/usr/bin/Xcode-helper", "/x/dockerd", "node",
                "/Applications/Some App.app/Contents/MacOS/Some App"):
        fake_ps["set"](out)
        assert run("kill 77", fake_ps).returncode == 0, out


def test_jobs_and_probes_do_not_call_ps(fake_ps):
    fake_ps["set"](XCODE)
    for cmd in ("kill %1", "kill -9 %2", "kill -0 4242", "kill -s 0 4242", "kill -l", "kill -n 0 4242",
                "ls -la", "echo kill 4242x"):
        r = run(cmd, fake_ps)
        assert r.returncode == 0, cmd
        assert r.stdout == "" and r.stderr == "", cmd
    assert calls(fake_ps) == []


def test_one_ps_call_for_all_pids(fake_ps):
    fake_ps["set"]("/usr/bin/python3\n" + XCODE)
    r = run("kill -9 11 22; echo ok && kill %3 33", fake_ps)
    assert r.returncode == 2
    assert "Xcode" in r.stderr
    assert calls(fake_ps) == ["-o comm= -p 11,22,33"]


def test_pid_forms(fake_ps):
    fake_ps["set"](XCODE)
    for cmd in ("kill -s KILL 4242", "kill -KILL 4242", "kill -- 4242", "kill 4242 2>/dev/null",
                "kill 4242 &", "echo a\nkill 4242", "bash -c \"kill 4242\"", "x && /bin/kill 4242 || true",
                "KILL 4242", "kill '4242'"):
        r = run(cmd, fake_ps)
        assert r.returncode == 2, cmd
    assert calls(fake_ps) == ["-o comm= -p 4242"] * 10
    # `2>file` is an fd redirect, not the PID 2.
    fake_ps["log"].unlink()
    assert run("kill 99 2>/dev/null", fake_ps).returncode == 2
    assert calls(fake_ps) == ["-o comm= -p 99"]


def test_non_pid_args_skipped(fake_ps):
    fake_ps["set"](XCODE)
    r = run("kill $(pgrep foo) $PID abc", fake_ps)
    assert r.returncode == 0
    assert calls(fake_ps) == []


def test_ps_missing_passes(fake_ps, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    r = run("kill 4242", fake_ps, path=str(empty))
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""


def test_ps_failure_or_empty_passes(fake_ps, tmp_path):
    fake_ps["set"]("")
    assert run("kill 4242", fake_ps).returncode == 0
    bad = tmp_path / "bad"
    bad.mkdir()
    ps = bad / "ps"
    ps.write_text("#!/bin/sh\necho 'ps: illegal option' >&2\nexit 1\n", encoding="utf-8")
    ps.chmod(0o755)
    r = run("kill 4242", fake_ps, path=str(bad))
    assert r.returncode == 0
    assert r.stdout == "" and r.stderr == ""


def test_name_kills_still_blocked_without_ps(fake_ps, tmp_path):
    empty = tmp_path / "empty"
    empty.mkdir()
    assert run("pkill -f x", fake_ps, path=str(empty)).returncode == 2
    assert run("kill -9 -1", fake_ps, path=str(empty)).returncode == 2


def test_powershell_kill_alias(fake_ps):
    fake_ps["set"](XCODE)
    assert run("kill 4242", fake_ps, tool="PowerShell").returncode == 2
