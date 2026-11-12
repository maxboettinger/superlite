"""B154 (#659): run_tests.full_run_gate acts on machine.json "admission" per toolchain."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

from test_plan_tools import SCRIPTS
from test_toolchain_lock_550 import hold, shell_project, stop

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

pytestmark = pytest.mark.skipif(os.name == "nt", reason="flock is POSIX only")

STUB = ('printf \'%s\\n\' "$@" > "$GATE_ARGS"\n'
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


def machine(adm):
    home = Path(os.environ["SUPERLITE_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / "machine.json").write_text(json.dumps({"admission": adm}), encoding="utf-8")


def args(tmp_path, lock_wait=30.0):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    return SimpleNamespace(lock_wait=lock_wait, task=None, run_id=None, summary=str(tmp_path / ".superlite" / "test-summary.json"))


def test_self_restores_lock_env(tmp_path):
    machine({"python": "self"})
    assert run_tests.LOCK_ENV not in os.environ
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True):
        assert os.environ[run_tests.LOCK_ENV] == str(os.getpid())
    assert run_tests.LOCK_ENV not in os.environ
    with pytest.raises(RuntimeError):
        with run_tests.full_run_gate(args(tmp_path), "full", "python", True):
            raise RuntimeError("x")
    assert run_tests.LOCK_ENV not in os.environ


def test_self_skips_a_held_lock(tmp_path):
    machine({"xcode": "self"})
    proc = hold("xcode", 60)
    try:
        with run_tests.full_run_gate(args(tmp_path, 1), "full", "xcode", True) as g:
            assert g is not None
    finally:
        stop(proc)
    assert not (tmp_path / "args").exists()


# shell_project's test-cmd.json language is bash, so lock_toolchain names the toolchain bash
def test_note_printed_once(tmp_path, monkeypatch, capsys):
    machine({"bash": "self"})
    shell_project(tmp_path)
    monkeypatch.chdir(tmp_path)
    proc = hold("bash", 60)
    try:
        assert run_tests.main(["--full", "--lock-wait", "5"]) == 0
    finally:
        stop(proc)
    err = capsys.readouterr().err
    assert err.count("full run admitted by the machine itself") == 1
    assert "waiting for the bash full-suite lock" not in err


def test_dict_command_for_python(tmp_path, gate, capsys):
    machine({"python": [gate, "run", "--"]})
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True) as g:
        r = g.run(["/bin/echo", "x"])
    assert r.stdout == "x\n" and (tmp_path / "args").exists()
    assert 'machine.json "admission" for python' in capsys.readouterr().err


def test_dict_lock_entry_waits(tmp_path, capsys):
    machine({"python": "lock"})
    proc = hold("python", 30)
    try:
        with pytest.raises(run_tests.LockBusy):
            with run_tests.full_run_gate(args(tmp_path, 1), "full", "python", True):
                pass
    finally:
        stop(proc)
    err = capsys.readouterr().err
    assert err.count('(machine.json "admission" for python: "lock")') == 1


def test_missing_entry_takes_lock(tmp_path, capsys):
    machine({"xcode": "self"})
    proc = hold("python", 30)
    try:
        with pytest.raises(run_tests.LockBusy):
            with run_tests.full_run_gate(args(tmp_path, 1), "full", "python", True):
                pass
    finally:
        stop(proc)
    assert 'has no "python" or "default" entry' in capsys.readouterr().err


def test_invalid_entry_warns_once_and_locks(tmp_path, capsys):
    machine({"python": 7})
    proc = hold("python", 30)
    try:
        with pytest.raises(run_tests.LockBusy):
            with run_tests.full_run_gate(args(tmp_path, 1), "full", "python", True):
                pass
    finally:
        stop(proc)
    assert capsys.readouterr().err.count('"admission" for python must be a non-empty list') == 1


def test_list_form_unchanged(tmp_path, gate, capsys):
    machine([gate, "run", "--"])
    with run_tests.full_run_gate(args(tmp_path), "full", "xcode", True) as g:
        g.run(["/bin/echo", "x"])
    assert (tmp_path / "args").exists()
    assert 'full run through the admission command gate (machine.json "admission"); no full-suite lock' in capsys.readouterr().err


def test_unset_prints_no_note(tmp_path, capsys):
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True):
        pass
    assert 'machine.json "admission"' not in capsys.readouterr().err


def test_nested_self_prints_nothing(tmp_path, monkeypatch, capsys):
    machine({"python": "self"})
    monkeypatch.setenv(run_tests.LOCK_ENV, str(os.getppid()))
    with run_tests.full_run_gate(args(tmp_path), "full", "python", True):
        pass
    assert 'machine.json "admission"' not in capsys.readouterr().err
