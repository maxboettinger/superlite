"""A run_tests no-result stop names the command, the exit code and a kept log (#330)."""
from __future__ import annotations

import json
import os
import sys

from test_plan_tools import SCRIPTS, run
from test_run_tests_plan_fallback import RUN_TESTS, setup

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402
import run_tests  # noqa: E402


def swift_zero(tmp_path):
    zero = "Executed 0 tests, with 0 failures (0 unexpected) in 0.0 (0.0) seconds"
    cmd = f'{sys.executable} -c "print(\'{zero}\'); print(\'nothing here\')"'
    spec = {"language": "swift", "test": cmd, "test_file": cmd}
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(spec), encoding="utf-8")
    return cmd


def incidents(tmp_path):
    f = tmp_path / ".superlite" / "incidents.jsonl"
    rows = [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines() if x.strip()]
    return [r for r in rows if r.get("kind") == "no-result"]


def zero_run(tmp_path):
    cmd = swift_zero(tmp_path)
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    return cmd, cp


def test_zero_count_stop_names_command_exit_and_log(tmp_path):
    cmd, cp = zero_run(tmp_path)
    assert cp.returncode == 1, cp.both
    (inc,) = incidents(tmp_path)
    assert inc["exit"] == 0
    assert inc["command"] == cmd
    log = inc["log"]
    assert os.path.isfile(log) and os.path.dirname(log).endswith(".superlite")
    text = open(log, encoding="utf-8").read()
    assert "command: " in text and "exit: 0" in text and "nothing here" in text
    assert inc["target"] == f"exit 0 from `{cmd}`; log {log}"
    assert f"run_tests: no-result log {log}" in cp.err


def test_pytest_no_result_names_the_exit(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_x.py").write_text("def test_a():\n    import os; os._exit(3)\n", encoding="utf-8")
    (tmp_path / "pyproject.toml").write_text("[tool.pytest.ini_options]\n", encoding="utf-8")
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    assert cp.returncode == 2, cp.both
    (inc,) = incidents(tmp_path)
    assert inc["exit"] == 3 and "pytest" in inc["command"]
    s = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert s["error"].startswith("pytest produced no results (exit 3): ")
    assert "exit: 3" in open(inc["log"], encoding="utf-8").read()


def test_auto_entry_carries_the_target(tmp_path, monkeypatch):
    zero_run(tmp_path)
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    stops = finish.read_stops(tmp_path / ".superlite" / "incidents.jsonl")
    assert finish.log_auto(stops) == 1
    rows = [json.loads(x) for x in (home / "feedback.jsonl").read_text(encoding="utf-8").splitlines()]
    (e,) = rows
    assert e["tool"] == "run_tests" and e["reason"] == "no-result"
    assert "exit 0 from `" in e["text"] and "; log " in e["text"]


def test_tree_stop_names_the_tree(tmp_path):
    plan = setup(tmp_path)
    cmd = swift_zero(tmp_path)
    spec = {"language": "swift", "test": cmd, "test_file": cmd, "isolate": True}
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(spec), encoding="utf-8")
    cp = run(RUN_TESTS, "--fast", "src/a.txt", "--task", "T1", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 1, cp.both
    (inc,) = incidents(tmp_path)
    assert inc["cwd"].replace("\\", "/").endswith(".superlite/trees/T1")
    (stop,) = finish.read_stops(tmp_path / ".superlite" / "incidents.jsonl")
    assert stop[2].endswith(f"(cwd {inc['cwd']})")


def test_no_result_logs_keep_the_newest_20(tmp_path):
    paths = [run_tests.no_result_log(str(tmp_path / "s.json"), "c", "/r", 1, ["x"]) for _ in range(22)]
    assert all(paths)
    left = sorted(p.name for p in tmp_path.glob("no-result-*.log"))
    assert len(left) == 20
    assert not os.path.exists(paths[0]) and not os.path.exists(paths[1])
    assert os.path.exists(paths[-1])


def test_unwritable_log_returns_empty(tmp_path):
    (tmp_path / "f").write_text("x", encoding="utf-8")
    assert run_tests.no_result_log(str(tmp_path / "f" / "s.json"), "c", "/r", 1, ["x"]) == ""


def test_target_text():
    assert run_tests.no_result_target("x", 3, "") == "exit 3 from `x`; log not written"
