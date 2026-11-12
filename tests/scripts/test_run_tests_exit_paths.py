"""Every run_tests exit path writes a summary and names its error (GitHub #330)."""
from __future__ import annotations

import json
import os
import subprocess
import sys
import time

import pytest

from test_plan_tools import SCRIPTS, run
from test_run_tests_plan_fallback import RUN_TESTS, setup, summary

import run_tests  # noqa: E402

ZERO = "0 0 0 0.0"


def pytest_project(tmp_path):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / "test_ok.py").write_text("def test_ok():\n    assert True\n", encoding="utf-8")
    (tmp_path / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")


def old_summary(tmp_path, **kw):
    data = {"passed": 5, "failed": 0, "skipped": 0, "seconds": 1.0, "mode": "full", "failures": []}
    data.update(kw)
    (tmp_path / ".superlite" / "test-summary.json").write_text(json.dumps(data), encoding="utf-8")


def test_unknown_task_writes_a_summary(tmp_path):
    plan = setup(tmp_path)
    cp = run(RUN_TESTS, "--fast", "src/a.c", "--task", "T9", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 2, cp.both
    assert cp.out.splitlines()[-1] == ZERO
    assert summary(tmp_path)["error"] == f"unknown task T9 in {plan}"
    assert f"run_tests: unknown task T9 in {plan}" in cp.err


def test_pytest_unavailable_replaces_an_old_summary(tmp_path, monkeypatch, capsys):
    pytest_project(tmp_path)
    old_summary(tmp_path)
    monkeypatch.chdir(tmp_path)

    def gone():
        raise run_tests.pyrun.PytestUnavailable("pytest is not installed")
    monkeypatch.setattr(run_tests.pyrun, "pytest_cmd", gone)
    assert run_tests.main(["--full"]) == 2
    data = summary(tmp_path)
    assert data["failed"] == 1
    assert "pytest is not installed" in data["error"]


def test_tree_prepare_failure_is_named(tmp_path, monkeypatch):
    plan = setup(tmp_path)
    monkeypatch.chdir(tmp_path)
    cmd = (tmp_path / ".superlite" / "test-cmd.json")
    spec = json.loads(cmd.read_text(encoding="utf-8"))
    spec["isolate"] = True
    cmd.write_text(json.dumps(spec), encoding="utf-8")

    def boom(*a, **k):
        raise RuntimeError("git worktree add failed: boom")
    monkeypatch.setattr(run_tests.trees, "prepare", boom)
    assert run_tests.main(["--fast", "src/a.c", "--task", "T1", "--plan", str(plan)]) == 2
    assert summary(tmp_path)["error"] == "isolated tree for T1 not prepared: git worktree add failed: boom"


def test_crash_writes_a_summary_and_the_line(tmp_path, monkeypatch, capsys):
    pytest_project(tmp_path)
    old_summary(tmp_path)
    monkeypatch.chdir(tmp_path)

    def bad(*a, **k):
        raise ValueError("bad test-cmd.json")
    monkeypatch.setattr(run_tests.testcmd, "resolve", bad)
    assert run_tests.main(["--full"]) == 2
    assert summary(tmp_path)["error"] == "run_tests crashed: ValueError('bad test-cmd.json')"
    cap = capsys.readouterr()
    assert cap.out.splitlines()[-1] == ZERO
    assert "Traceback" in cap.err
    assert "run_tests: crashed: ValueError('bad test-cmd.json')" in cap.err


def test_crash_after_the_result_keeps_it(tmp_path, monkeypatch):
    pytest_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    def full(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(run_tests.ct, "append_ledger", full)
    assert run_tests.main(["--full"]) == 2
    data = summary(tmp_path)
    assert data["passed"] == 1
    assert "error" not in data


def test_keyboard_interrupt_still_writes_a_summary(tmp_path, monkeypatch):
    pytest_project(tmp_path)
    monkeypatch.chdir(tmp_path)

    def stop(a):
        raise KeyboardInterrupt
    monkeypatch.setattr(run_tests, "run", stop)
    with pytest.raises(KeyboardInterrupt):
        run_tests.main(["--full"])
    assert summary(tmp_path)["error"].startswith("run_tests crashed: KeyboardInterrupt")


def test_background_records_the_child_pid(tmp_path):
    pytest_project(tmp_path)
    cp = run(RUN_TESTS, "--full", "--background", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    path = cp.out.splitlines()[0].split("summary: ", 1)[1]
    pid = int(open(path[:-5] + ".pid", encoding="utf-8").read().strip())
    assert pid > 0
    wait = [ln for ln in cp.out.splitlines() if ln.startswith("wait: ")][0][len("wait: "):]
    done = subprocess.run(wait, shell=True, capture_output=True, text=True, cwd=tmp_path, timeout=120)
    assert done.returncode == 0, done.stdout + done.stderr


@pytest.mark.skipif(os.name == "nt", reason="pid probing is POSIX only")
def test_wait_names_a_dead_background_run(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    mine = sl / "test-summary-x.json"
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    mine.with_suffix(".pid").write_text(str(child.pid), encoding="utf-8")
    mine.with_suffix(".log").write_text("boom", encoding="utf-8")
    t0 = time.monotonic()
    cp = run(RUN_TESTS, "--wait", mine, "--timeout", "30", cwd=tmp_path)
    assert cp.returncode == 1, cp.both
    assert time.monotonic() - t0 < 10
    msg = f"background run ended without a summary (pid {child.pid}); log {mine.with_suffix('.log')}"
    assert f"run_tests: {msg}" in cp.err
    data = json.loads(mine.read_text(encoding="utf-8"))
    assert data["failed"] == 1
    assert data["error"] == msg


def test_wait_timeout_names_the_log(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    mine = sl / "test-summary-y.json"
    mine.with_suffix(".pid").write_text(str(os.getpid()), encoding="utf-8")
    cp = run(RUN_TESTS, "--wait", mine, "--timeout", "0.5", cwd=tmp_path)
    assert cp.returncode == 2, cp.both
    assert f"run_tests: timed out waiting for {mine}; log {mine.with_suffix('.log')}" in cp.err


@pytest.mark.skipif(os.name == "nt", reason="pid probing is POSIX only")
def test_dead_run_error_reaches_the_published_summary(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    mine = sl / "test-summary-x.json"
    published = sl / "test-summary.json"
    published.write_text(json.dumps({"passed": 5, "failed": 0, "skipped": 0}), encoding="utf-8")
    (sl / "test-summary.latest").write_text(json.dumps({"id": "x", "summary": str(mine)}), encoding="utf-8")
    child = subprocess.Popen([sys.executable, "-c", "pass"])
    child.wait()
    mine.with_suffix(".pid").write_text(str(child.pid), encoding="utf-8")
    cp = run(RUN_TESTS, "--wait", cwd=tmp_path)
    assert cp.returncode == 1, cp.both
    data = json.loads(published.read_text(encoding="utf-8"))
    assert data["failed"] == 1
    assert "ended without a summary" in data["error"]
