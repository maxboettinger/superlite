"""Telemetry lines from the test, batch and feedback ledgers (#933)."""
import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import backlog_state  # noqa: E402
import feedback  # noqa: E402
import run_tests  # noqa: E402
import telemetry  # noqa: E402


def rt(cwd, home, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith(("SUPERLITE_FLEET_", "SUPERLITE_STATE_DIR"))}
    env.update(SUPERLITE_HOME=str(home), PYTHONIOENCODING="utf-8")
    return subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), *map(str, args)], cwd=cwd,
                          capture_output=True, text=True, env=env, timeout=120)


def kind(name):
    return [e for e in telemetry.read_events() if e["kind"] == name]


def test_kind_tests_fast_run(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    (tmp_path / "test_a.py").write_text("def test_a():\n    assert True\n\n\ndef test_b():\n    assert True\n")
    cp = rt(tmp_path, home, "--fast", "test_a.py", "--task", "T2")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    (line,) = kind("tests")
    assert telemetry.validate(line) == []
    assert (line["mode"], line["passed"], line["failed"], line["task"]) == ("fast", 2, 0, "T2")
    assert line["seconds"] > 0


def test_tests_stamp_hit_no_line(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.chdir(tmp_path)
    base = {"commit": "c" * 40, "tree": "t" * 40, "platforms": ["ios"], "changed": [], "tests": 3}
    monkeypatch.setattr(run_tests.suite_stamp, "green_base", lambda *a, **k: base)
    monkeypatch.setattr(run_tests, "STAMP", None)
    sd = tmp_path / ".superlite"
    sd.mkdir()
    a = argparse.Namespace(summary=str(sd / "test-summary.json"), log=str(sd / "incidents.jsonl"),
                           ledger=str(sd / "progress.md"), task=None, publish=None, run_id=None)
    assert run_tests.stamp_hit(a, {"command": "maxapp test"}, "full") == 0
    assert kind("tests") == []


def _backlog(tmp_path, state="running"):
    p = tmp_path / "proj" / ".superlite" / "backlog.json"
    p.parent.mkdir(parents=True)
    d = backlog_state.default()
    d["batches"] = [{"id": "B1", "state": state, "lead_model": "opus"}]
    p.write_text(json.dumps(d))
    return p


def test_kind_batch_state_change(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    p = _backlog(tmp_path)
    backlog_state.update(p, lambda d: backlog_state.batch(d, "B1").update({"state": "shipped", "pr": 12}))
    (line,) = kind("batch")
    assert telemetry.validate(line) == []
    assert (line["batch"], line["state"], line["pr"]) == ("B1", "shipped", 12)
    backlog_state.update(p, lambda d: backlog_state.batch(d, "B1").update({"state": "shipped"}))
    assert len(kind("batch")) == 1


def test_kind_run_end_shipped_from_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    p = _backlog(tmp_path)
    key = telemetry.batch_key(tmp_path / "proj", "B1")
    assert telemetry.defer_run_end(key, {"wall_s": 5})
    backlog_state.update(p, lambda d: backlog_state.batch(d, "B1").update({"state": "shipped", "pr": 12}))
    (line,) = kind("run_end")
    assert telemetry.validate(line) == []
    assert line["outcome"] == "shipped"


def test_kind_run_end_done_from_no_change_batch(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    p = _backlog(tmp_path)
    key = telemetry.batch_key(tmp_path / "proj", "B1")
    assert telemetry.defer_run_end(key, {"wall_s": 5})
    backlog_state.update(p, lambda d: backlog_state.batch(d, "B1").update({"state": "shipped", "no_change": "nothing to do"}))
    (line,) = kind("run_end")
    assert telemetry.validate(line) == []
    assert line["outcome"] == "done"


def test_kind_batch_real_keys(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    p = _backlog(tmp_path)
    key = telemetry.batch_key(tmp_path / "proj", "B1")
    assert telemetry.defer_run_end(key, {"wall_s": 5})
    backlog_state.update(p, lambda d: backlog_state.batch(d, "B1").update(
        {"state": "parked", "reason": "ci red", "leads": [{"id": "x", "phase": "build", "model": "sonnet"}]}))
    (line,) = kind("batch")
    assert (line["lead_model"], line["reason"]) == ("sonnet", "ci red")
    (end,) = kind("run_end")
    assert (end["outcome"], end["reason"]) == ("parked", "ci red")


def test_kind_feedback_add(tmp_path, monkeypatch):
    home = tmp_path / "home"
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    a = argparse.Namespace(file=None, text="secret-words-xyz", kind="bug", plan=None)
    assert feedback.cmd_add(a) == 0
    (line,) = kind("feedback")
    assert telemetry.validate(line) == []
    assert (line["fkind"], line["reason"]) == ("bug", None)
    assert "secret-words-xyz" not in (home / "events.jsonl").read_text()


def test_kind_feedback_auto(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    assert feedback.add_auto("block-unsafe-kill", "pattern-kill", "pkill foo", "1.0")
    (line,) = kind("feedback")
    assert telemetry.validate(line) == []
    assert (line["fkind"], line["reason"]) == ("auto", "pattern-kill")


def test_run_tests_summary_unchanged(tmp_path, monkeypatch):
    home = tmp_path / "home"
    (tmp_path / "test_a.py").write_text("def test_a():\n    assert True\n")
    cp = rt(tmp_path, home, "--fast", "test_a.py")
    assert cp.stdout.split()[:3] == ["1", "0", "0"] and len(cp.stdout.split()) == 4


def test_tests_emit_failure_keeps_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(run_tests, "STAMP", None)
    for name in ("write_summary", "publish_summary", "add_incidents", "resolve_passed"):
        monkeypatch.setattr(run_tests, name, lambda *a, **k: None)
    monkeypatch.setattr(run_tests.ct, "append_ledger", lambda *a, **k: None)
    a = argparse.Namespace(summary=None, log=None, ledger=None, task=None, publish=None, run_id=None)
    counts = {"passed": 1, "failed": 0, "skipped": 0, "skipped_tests": []}
    assert run_tests.finish_run(a, "fast", counts, [], {}, 1.0, 0) == 0
