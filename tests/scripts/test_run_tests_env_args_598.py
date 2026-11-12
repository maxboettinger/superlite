"""#598: run_tests --env K=V and pass-through args after `--` reach the test command."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import run_tests  # noqa: E402

RUN_TESTS = Path(run_tests.__file__)
RUNNER = 'echo "$@" > .superlite/args.txt\necho "FOO=$FOO" > .superlite/env.txt\necho "1 passed"\n'


def child_env(tmp_path):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k != "FOO"}
    env.update(SUPERLITE_HOME=os.environ.get("SUPERLITE_HOME") or str(tmp_path / "home"), PYTHONIOENCODING="utf-8")
    env.update(SUPERLITE_DISK_FLOOR_GB="0", SUPERLITE_DISK_WARN_GB="0", SUPERLITE_MACHINE_LIMIT="0")
    if "SUPERLITE_USER_TEST_CMD" in os.environ:
        env["SUPERLITE_USER_TEST_CMD"] = os.environ["SUPERLITE_USER_TEST_CMD"]
    return env


def run(tmp_path, *args):
    env = child_env(tmp_path)
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(RUN_TESTS), "--log", str(sl / "incidents.jsonl"),
                         "--ledger", str(sl / "ledger.md"), "--summary", str(sl / "test-summary.json"), *map(str, args)],
                        capture_output=True, cwd=tmp_path, env=env, timeout=120, text=True)
    cp.both = cp.stdout + cp.stderr
    return cp


def project(tmp_path, cfg_env=None):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "runner.sh").write_text(RUNNER, encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    cfg = {"language": "shell", "test": "sh runner.sh"}
    if cfg_env:
        cfg["env"] = cfg_env
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def read(tmp_path, name):
    return (tmp_path / ".superlite" / name).read_text(encoding="utf-8").strip()


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_with_args_xcodebuild_pipe():
    assert run_tests.with_args("xcodebuild test -scheme A | xcpretty", ["-test-iterations", "3"]) == "xcodebuild test -scheme A -test-iterations 3 | xcpretty"


def test_with_args_after_cd():
    assert run_tests.with_args("cd P && swift test", ["--parallel"]) == "cd P && swift test --parallel"


def test_with_args_quotes_and_empty():
    assert run_tests.with_args("npm test", ["--", "-t", "a b"]) == "npm test -- -t 'a b'"
    assert run_tests.with_args("x", []) == "x"


def test_with_args_before_first_pipe():
    assert run_tests.with_args("make test | tee out || true", ["-j2"]) == "make test -j2 | tee out || true"


def test_env_reaches_test_command(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--full", "--env", "FOO=bar")
    assert cp.returncode == 0, cp.both
    assert read(tmp_path, "env.txt") == "FOO=bar"


def test_env_overrides_config_env(tmp_path):
    project(tmp_path, cfg_env={"FOO": "cfg"})
    assert run(tmp_path, "--full").returncode == 0
    assert read(tmp_path, "env.txt") == "FOO=cfg"
    assert run(tmp_path, "--full", "--env", "FOO=cli").returncode == 0
    assert read(tmp_path, "env.txt") == "FOO=cli"


def test_env_bad_value_exit_2(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--full", "--env", "NOVALUE")
    assert cp.returncode == 2
    assert "--env needs K=V, got NOVALUE" in cp.both


def test_passthrough_appended_to_command(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--full", "--", "--flag", "a b")
    assert cp.returncode == 0, cp.both
    assert read(tmp_path, "args.txt") == "--flag a b"


def test_passthrough_makes_run_fast(tmp_path):
    project(tmp_path)
    assert run(tmp_path, "--full", "--", "-x").returncode == 0
    assert summary(tmp_path)["mode"] == "fast"


def test_passthrough_with_wait_refused(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--wait", "--", "-x")
    assert cp.returncode == 2
    assert "pass-through args (after --) need a test run" in cp.both


def test_passthrough_to_pytest(tmp_path):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_a.py").write_text("def test_one():\n    pass\n\n\ndef test_two():\n    pass\n", encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    cp = run(tmp_path, "--fast", "tests/test_a.py", "--", "-k", "one")
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert (s["passed"], s["mode"]) == (1, "fast")


def test_passthrough_background_keeps_args(tmp_path):
    project(tmp_path)
    cp = run(tmp_path, "--fast", "tests/test_x.py", "--background", "--", "--flag")
    assert cp.returncode == 0, cp.both
    wait = cp.stdout.strip().splitlines()[-1].split()[-1]
    done = run(tmp_path, "--wait", wait)
    assert done.returncode == 0, done.both
    seen = read(tmp_path, "args.txt")
    assert "--flag" in seen
    assert "--summary" not in seen and "--run-id" not in seen


def test_helper_env_pins_disk_guard(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "100000")
    monkeypatch.setenv("SUPERLITE_OTHER", "x")
    env = child_env(tmp_path)
    assert env["SUPERLITE_DISK_FLOOR_GB"] == "0" and env["SUPERLITE_DISK_WARN_GB"] == "0"
    assert env["SUPERLITE_MACHINE_LIMIT"] == "0" and "SUPERLITE_OTHER" not in env
    assert env["SUPERLITE_HOME"]
