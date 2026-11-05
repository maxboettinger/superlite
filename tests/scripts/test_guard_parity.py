"""T5: the coordinator hook judges Bash and PowerShell commands with guard_judge.py.

Every guard test that existed before the swap is the parity suite: it runs here unchanged. A failure in it is a
finding against the judge modules (guard_lex, guard_files, guard_tools, guard_judge), not a reason to edit the test.
"""
import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_block_coordinator_edits import BASH, HOOK, bash, proj, run  # noqa: F401

HERE = Path(__file__).resolve().parent
PARITY = ("test_block_coordinator_edits.py", "test_human_gate.py", "test_session_state.py", "test_fleet_hooks.py",
          "test_hooks_bash32.py")


def parity_files():
    own = Path(__file__).name
    return [HERE / n for n in PARITY] + sorted(p for p in HERE.glob("test_guard_*.py") if p.name != own)


def test_parity_existing_suites():
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:cacheprovider", "--no-header", "-rf"]
    try:
        import xdist  # noqa: F401
        args += ["-n", "auto"]
    except ImportError:
        pass
    r = subprocess.run(args + [str(p) for p in parity_files()], capture_output=True, text=True, cwd=str(HERE.parent.parent))
    assert r.returncode == 0, r.stdout[-6000:] + r.stderr[-1500:]


@pytest.mark.parametrize("cmd", [
    "xargs rm < l",
    "find src -delete",
    "dd if=a of=src/b",
    "truncate -s 0 src/a",
    "install a src/b",
    "ln -s a src/b",
    "rsync a src/",
    "touch src/a",
    "curl x | sh",
])
def test_not_judged_before_now_blocks(proj, cmd):  # noqa: F811
    r = bash(proj, cmd)
    assert r.returncode == 2, (cmd, r.stderr)


def test_block_names_absolute_target(proj):  # noqa: F811
    # The block names the project-relative path (a line starting `Blocked target: src/a.py`) and the absolute one.
    r = bash(proj, "printf x > src/a.py")
    assert r.returncode == 2
    assert any(ln.startswith("Blocked target: src/a.py") for ln in r.stderr.splitlines()), r.stderr
    assert str(proj / "src" / "a.py") in r.stderr


def fake_python(tmp_path):
    """A python3 and python that only record that they were started, then fail."""
    d = tmp_path / "fakebin"
    d.mkdir()
    marker = tmp_path / "python-started"
    for name in ("python3", "python"):
        f = d / name
        f.write_text(f'#!/bin/sh\necho started >> "{marker.as_posix()}"\nexit 1\n', encoding="utf-8")
        f.chmod(0o755)
    return d, marker


def hook(proj, tmp_path, cmd, path):
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "PATH": path, "SUPERLITE_CACHE_DIR": str(tmp_path / "cache")}
    env.pop("SUPERLITE_PYTHON", None)
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env)


def incidents(proj):
    f = proj / ".superlite" / "incidents.jsonl"
    return [json.loads(ln) for ln in f.read_text(encoding="utf-8").splitlines()] if f.exists() else []


def test_idle_skips_python(tmp_path):
    idle = tmp_path / "idle"
    (idle / ".superlite").mkdir(parents=True)
    d, marker = fake_python(tmp_path)
    path = str(d)   # no real Python (uv, py) behind the fakes
    r = hook(idle, tmp_path, "rm src/a.py && echo done > out.txt", path)
    assert r.returncode == 0 and r.stderr == "" and not marker.exists()
    assert incidents(idle) == []
    # control: a protected name starts Python (the fake fails, so the hook fails open after a guard-error incident)
    r = hook(idle, tmp_path, "rm .superlite/orchestrator.json", path)
    assert r.returncode == 0 and marker.exists()
    assert [x["kind"] for x in incidents(idle)] == ["guard-error"]


def test_python_missing_fails_open(proj, tmp_path):  # noqa: F811
    empty = tmp_path / "nopath"
    empty.mkdir()
    r = hook(proj, tmp_path, "rm src/a.py", str(empty))
    assert r.returncode == 0 and r.stdout == ""
    rows = incidents(proj)
    assert [x["kind"] for x in rows] == ["guard-error"]
    assert rows[0]["agent"] == "coordinator" and rows[0]["tool"] == "Bash"


def test_failing_python_fails_open(proj, tmp_path):  # noqa: F811
    d, marker = fake_python(tmp_path)
    r = hook(proj, tmp_path, "rm src/a.py", str(d))
    assert r.returncode == 0 and marker.exists()
    assert [x["kind"] for x in incidents(proj)] == ["guard-error"]


@pytest.mark.parametrize("cmd", [
    "printf '{\"mode\":\"human\",\"approved\":true}' > .superlite/orchestrator.jso?",
    "tee .superlite/{orchestrator.json,x}",
    "touch docs/plans/{x,../../src/a.py}",
    "sed -i s/a/b/ docs/plans/{x,../../src/a.py}",
])
def test_glob_and_brace_targets_block(proj, cmd):  # noqa: F811
    # final review 1: the literal text of a glob or brace word matched `.superlite/*` and `docs/plans/*`
    (proj / "docs" / "plans").mkdir(parents=True)
    r = bash(proj, cmd)
    assert r.returncode == 2, (cmd, r.stderr)


@pytest.mark.parametrize("cmd", [
    "rm .superlite/orchestrator.js''on",
    "rm .superlite/orchestrator.j\\son",
    "rm .superlite/$'\\x6frchestrator.json'",
    "rm .superlite/orch*",
    "cd .superlite && rm orch*",
])
def test_idle_spelled_protected_names_reach_the_judge(tmp_path, cmd):
    # final review 4: the idle pre-check looked only for the literal protected names
    idle = tmp_path / "idle"
    (idle / ".superlite").mkdir(parents=True)
    r = bash(idle, cmd)
    assert r.returncode == 2 and "never written directly" in r.stderr, (cmd, r.stderr)


@pytest.mark.skipif(os.name == "nt" or not shutil.which("true"), reason="needs a POSIX true binary")
def test_fake_cached_python_is_not_trusted(proj, tmp_path):  # noqa: F811
    # final review 3: an exit 0 from a cached fake interpreter (/usr/bin/true) passed every command
    cache = tmp_path / "cache"
    cache.mkdir()
    path = os.environ["PATH"]
    (cache / "python").write_text(f"{shutil.which('true')}\n{path}|{tmp_path}|\n", encoding="utf-8")
    env = {**os.environ, "CLAUDE_PROJECT_DIR": str(proj), "PATH": path, "SUPERLITE_CACHE_DIR": str(cache), "PWD": str(tmp_path)}
    for k in ("SUPERLITE_PYTHON", "VIRTUAL_ENV"):
        env.pop(k, None)
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm src/a.py"}})
    r = subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert r.returncode == 2, r.stderr
    assert (cache / "python").read_text(encoding="utf-8").splitlines()[0] != shutil.which("true")  # the cache is rewritten
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": "rm docs/plans/a.md"}})
    r = subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env, cwd=str(tmp_path))
    assert r.returncode == 0 and r.stdout == ""
    assert all(x["kind"] != "guard-error" for x in incidents(proj)), incidents(proj)
