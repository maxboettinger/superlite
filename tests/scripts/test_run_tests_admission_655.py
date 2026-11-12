"""B153 (#655): run_tests.full_run_gate runs a full run through the machine's admission command, or under the lock."""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_plan_tools import SCRIPTS, run
from test_toolchain_lock_550 import hold, shell_project, stop

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="flock is POSIX only")

RUN_TESTS = SCRIPTS / "run_tests.py"
STUB = ('printf \'%s\\n\' "$@" > "$GATE_ARGS"\n'
        'echo $$ > "${GATE_PIDFILE:-/dev/null}"\n'
        'sleep "${GATE_SLEEP:-0}"\n'
        '[ -n "$GATE_FAIL" ] && { echo "gate: refused" >&2; exit "$GATE_FAIL"; }\n'
        'while [ "$1" != "--" ]; do shift; done; shift; exec "$@"\n')


@pytest.fixture(autouse=True)
def _no_outer_lock(monkeypatch):
    monkeypatch.delenv(run_tests.LOCK_ENV, raising=False)


@pytest.fixture
def gate(tmp_path, monkeypatch):
    g = tmp_path / "gate"
    g.write_text("#!/bin/sh\n" + STUB, encoding="utf-8")
    g.chmod(0o755)
    monkeypatch.setenv("GATE_ARGS", str(tmp_path / "args"))
    return str(g)


def machine(gate_path):
    home = Path(os.environ["SUPERLITE_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / "machine.json").write_text(json.dumps({"admission": [gate_path, "run", "--class", "other", "--"]}), encoding="utf-8")


def args(tmp_path, lock_wait=30.0):
    return SimpleNamespace(lock_wait=lock_wait, task=None, run_id=None, summary=str(tmp_path / ".superlite" / "test-summary.json"))


def lock_holder_pid():
    h = run_tests.lock_holder(run_tests.full_lock_path("python"))
    return h["pid"] if h else None


def test_gate_runs_through_admission(tmp_path, gate, capsys):
    machine(gate)
    (tmp_path / ".superlite").mkdir()
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True) as g:
        r = g.run(["/bin/echo", "x"])
        assert lock_holder_pid() != os.getpid()
    assert r.stdout == "x\n"
    assert (tmp_path / "args").exists()
    assert "full run through the admission command gate" in capsys.readouterr().err


def test_shell_full_run_through_admission(tmp_path, monkeypatch, gate, capsys):
    machine(gate)
    shell_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    proc = hold("shell", 60)
    try:
        assert run_tests.main(["--full", "--lock-wait", "5"]) == 0
    finally:
        stop(proc)
    assert "waiting for the shell full-suite lock" not in capsys.readouterr().err


def test_missing_admission_falls_back_to_lock(tmp_path, capsys):
    machine("/no/such/gate")
    (tmp_path / ".superlite").mkdir()
    proc = hold("python", 30)
    try:
        with pytest.raises(run_tests.LockBusy):
            with run_tests.full_run_gate(args(tmp_path, 1), "full", "python", True):
                pass
    finally:
        stop(proc)
    err = capsys.readouterr().err
    assert err.count("admission command /no/such/gate not found") == 1


def test_failing_admission_falls_back_once(tmp_path, monkeypatch, gate, capsys):
    machine(gate)
    monkeypatch.setenv("GATE_FAIL", "3")
    (tmp_path / ".superlite").mkdir()
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True) as g:
        r1 = g.run(["/bin/echo", "a"])
        r2 = g.run(["/bin/echo", "b"])
    assert (r1.returncode, r2.returncode) == (0, 0)
    err = capsys.readouterr().err
    assert err.count("admission command gate exited 3 before the tests started") == 1
    assert "running under the python full-suite lock" in err
    assert (tmp_path / "args").read_text(encoding="utf-8").count("run\n") == 1


def test_nested_run_skips_admission(tmp_path, monkeypatch, gate):
    machine(gate)
    monkeypatch.setenv(run_tests.LOCK_ENV, str(os.getppid()))
    (tmp_path / ".superlite").mkdir()
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True) as g:
        assert g.run(["/bin/echo", "x"]).stdout == "x\n"
        assert lock_holder_pid() is None
    assert not (tmp_path / "args").exists()


def test_lock_false_skips_admission(tmp_path, gate, capsys):
    machine(gate)
    (tmp_path / ".superlite").mkdir()
    with run_tests.full_run_gate(args(tmp_path), "full", "python", False) as g:
        g.run(["/bin/echo", "x"])
    assert "no full-suite lock" in capsys.readouterr().err
    assert not (tmp_path / "args").exists()


def test_admission_busy_is_red_exit_2(tmp_path, monkeypatch, gate, capsys):
    machine(gate)
    shell_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GATE_SLEEP", "30")
    assert run_tests.main(["--full", "--lock-wait", "1"]) == 2
    data = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert data["error"] == "admission: gate did not start the full run after 1 s (run_tests --lock-wait S; 0 = no limit)"
    assert not (tmp_path / ".superlite" / "incidents.jsonl").exists()


def test_wait_reports_admission_note(tmp_path):
    mine = tmp_path / ".superlite" / "test-summary-r1.json"
    mine.parent.mkdir()
    mine.write_text("", encoding="utf-8")
    mine.with_suffix(".lockwait").write_text(json.dumps({"admission": "gate", "pid": os.getpid(), "since": time.time()}), encoding="utf-8")
    w = run(RUN_TESTS, "--wait", str(mine), "--timeout", "1", cwd=tmp_path)
    assert "is waiting for the admission command gate (since " in w.err, w.err


def test_waited_left_out_of_seconds(tmp_path, monkeypatch, gate):
    machine(gate)
    monkeypatch.setenv("GATE_SLEEP", "2")
    (tmp_path / ".superlite").mkdir()
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True) as g:
        g.run(["/bin/echo", "x"])
    assert g.waited >= 1.5


def test_limit_hit_from_admitted_run_keeps_output(tmp_path, gate):
    machine(gate)
    (tmp_path / ".superlite").mkdir()
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True) as g:
        with pytest.raises(run_tests.LimitHit) as ei:
            g.run("echo kept-output; sleep 10", limit=1, shell=True)
    assert "kept-output" in ei.value.text
