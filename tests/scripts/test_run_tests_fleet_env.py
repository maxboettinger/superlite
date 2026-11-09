"""run_tests drops every SUPERLITE_FLEET_* variable from the test subprocess environment (#219)."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

FLEET = {"SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_FLEET_PARENT_DIR": "/nowhere/.superlite",
         "SUPERLITE_FLEET_WORKER": "W9", "SUPERLITE_FLEET_AGENT": "lead", "SUPERLITE_FLEET_ACCOUNTS": "claude1"}
PYTEST_BODY = '''import os


def test_no_fleet_env():
    assert sorted(k for k in os.environ if k.startswith("SUPERLITE_FLEET_")) == []
    assert os.environ.get("KEEP_ME") == "1"
'''
CHECK = '''import json, os, sys
fleet = sorted(k for k in os.environ if k.startswith("SUPERLITE_FLEET_"))
if len(sys.argv) > 1:
    with open(sys.argv[1], "w", encoding="utf-8") as fh:
        fh.write(json.dumps(fleet))
    sys.exit(0)
ok = fleet == ["SUPERLITE_FLEET_CONFIG"] and os.environ.get("SUPERLITE_FLEET_CONFIG") == "kept" and os.environ.get("KEEP_ME") == "1"
print("fleet:", fleet)
print("1 passed" if ok else "1 failed")
sys.exit(0 if ok else 1)
'''


def rt(cwd, *args):
    env = {**os.environ, **FLEET, "KEEP_ME": "1", "PYTHONIOENCODING": "utf-8"}
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, env=env,
                          capture_output=True, text=True, timeout=120)


def counts(cp):
    return cp.stdout.strip().splitlines()[-1].split()[:2]


def test_pytest_run_drops_fleet_env(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_env.py").write_text(PYTEST_BODY, encoding="utf-8")
    cp = rt(tmp_path, "--fast", "tests/test_env.py")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert counts(cp) == ["1", "0"], cp.stdout


def test_runner_command_and_setup_drop_fleet_env(tmp_path):
    (tmp_path / "check.py").write_text(CHECK, encoding="utf-8")
    run = f"{shlex.quote(sys.executable)} {shlex.quote(str(tmp_path / 'check.py'))}"
    out = tmp_path / "setup-env.json"
    spec = {"language": "go", "test": run, "setup": f"{run} {shlex.quote(str(out))}",
            "env": {"SUPERLITE_FLEET_CONFIG": "kept"}}
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(spec), encoding="utf-8")
    cp = rt(tmp_path, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert counts(cp) == ["1", "0"], cp.stdout
    assert json.loads(out.read_text(encoding="utf-8")) == ["SUPERLITE_FLEET_CONFIG"]


def test_child_env_strips_only_the_fleet_prefix(monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_ROLE", "lead")
    monkeypatch.setenv("SUPERLITE_STATE_DIR", "/x/.superlite")
    monkeypatch.setenv("XSUPERLITE_FLEET_Y", "1")
    env = run_tests.child_env({"SUPERLITE_FLEET_CONFIG": "kept"})
    assert "SUPERLITE_FLEET_ROLE" not in env
    assert env["SUPERLITE_STATE_DIR"] == "/x/.superlite" and env["XSUPERLITE_FLEET_Y"] == "1"
    assert env["SUPERLITE_FLEET_CONFIG"] == "kept"
    assert run_tests.child_env() == {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_FLEET_")}
    assert os.environ["SUPERLITE_FLEET_ROLE"] == "lead"
