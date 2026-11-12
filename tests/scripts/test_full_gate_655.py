"""full_gate (#655): the machine.json admission command and a run through it with a start marker."""
import json
import os
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import full_gate  # noqa: E402

STUB = ('printf \'%s\\n\' "$@" > "$GATE_ARGS"\n'
        'echo $$ > "${GATE_PIDFILE:-/dev/null}"\n'
        'sleep "${GATE_SLEEP:-0}"\n'
        '[ -n "$GATE_FAIL" ] && { echo "gate: refused" >&2; exit "$GATE_FAIL"; }\n'
        'while [ "$1" != "--" ]; do shift; done; shift; exec "$@"\n')


@pytest.fixture
def gate(tmp_path, monkeypatch):
    g = tmp_path / "gate"
    g.write_text("#!/bin/sh\n" + STUB, encoding="utf-8")
    g.chmod(0o755)
    monkeypatch.setenv("GATE_ARGS", str(tmp_path / "args"))
    return str(g)


def machine(home, data):
    (home / "machine.json").write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")


WARN = 'machine.json "admission" must be a non-empty list of strings; running under the full-suite lock'


def test_admission_unset(tmp_path):
    assert full_gate.admission_command(tmp_path) == (None, None)


def test_admission_valid(tmp_path):
    argv = ["/bin/sh", "-c", 'exec "$@"', "gate"]
    machine(tmp_path, {"admission": argv})
    assert full_gate.admission_command(tmp_path) == (argv, None)


def test_admission_not_a_list(tmp_path):
    machine(tmp_path, {"admission": "gate"})
    assert full_gate.admission_command(tmp_path) == (None, WARN)


def test_admission_empty_list(tmp_path):
    machine(tmp_path, {"admission": []})
    assert full_gate.admission_command(tmp_path) == (None, WARN)


def test_admission_missing(tmp_path):
    machine(tmp_path, {"admission": ["/no/such/gate", "run"]})
    assert full_gate.admission_command(tmp_path) == (
        None, 'admission command /no/such/gate not found (machine.json "admission"); running under the full-suite lock')


def test_admission_bare_name_on_path(tmp_path):
    machine(tmp_path, {"admission": ["sh"]})
    assert full_gate.admission_command(tmp_path) == (["sh"], None)


def test_run_records_args_and_runs_command(tmp_path, gate):
    r = full_gate.run_admitted([gate, "run", "--class", "other", "--"], ["/bin/echo", "hi"], env=dict(os.environ))
    assert r.returncode == 0 and r.stdout == "hi\n"
    assert (tmp_path / "args").read_text().split("\n")[:6] == ["run", "--class", "other", "--", "/bin/sh", "-c"]


def test_shell_string_exit_code(gate):
    r = full_gate.run_admitted([gate, "run", "--"], "echo a && exit 7", env=dict(os.environ))
    assert (r.returncode, r.stdout, r.waited) == (7, "a\n", pytest.approx(0.0, abs=1.0))


def test_env_and_cwd_reach_command(tmp_path, gate):
    r = full_gate.run_admitted([gate, "run", "--"], "pwd; echo $FOO", env={**os.environ, "FOO": "bar"}, cwd=str(tmp_path))
    assert os.path.realpath(tmp_path) in r.stdout and "bar" in r.stdout


def test_wait_line_and_note(tmp_path, gate, capsys):
    note = tmp_path / "x.lockwait"
    seen = []

    def watch():
        end = time.time() + 2
        while time.time() < end and not seen:
            if note.exists():
                try:
                    seen.append(json.loads(note.read_text()))
                except ValueError:
                    pass
            time.sleep(0.05)

    t = threading.Thread(target=watch)
    t.start()
    try:
        r = full_gate.run_admitted([gate, "run", "--"], "true", env={**os.environ, "GATE_SLEEP": "2"}, note=note)
    finally:
        t.join()
    assert seen and seen[0]["admission"] == "gate" and seen[0]["pid"] == os.getpid()
    assert isinstance(seen[0]["since"], float)
    assert not note.exists()
    err = capsys.readouterr().err
    assert err.count("waiting for the admission command gate to start the full run") == 1
    assert "admission command gate started the full run after" in err
    assert r.waited >= 1.5


def test_no_wait_line_when_quick(gate, capsys):
    r = full_gate.run_admitted([gate, "run", "--"], "true", env={**os.environ, "GATE_SLEEP": "0"})
    assert "waiting for" not in capsys.readouterr().err
    assert r.waited < 1


def test_not_admitted(gate):
    with pytest.raises(full_gate.NotAdmitted) as e:
        full_gate.run_admitted([gate, "run", "--"], "true", env={**os.environ, "GATE_FAIL": "3"})
    assert e.value.returncode == 3
    assert e.value.reason == "exited 3 before the tests started: gate: refused"


def test_cannot_start(tmp_path):
    f = tmp_path / "plain"
    f.write_text("x")
    with pytest.raises(full_gate.NotAdmitted) as e:
        full_gate.run_admitted([str(f)], "true")
    assert e.value.reason.startswith("could not start:")


def test_wait_limit_kills_gate(tmp_path, gate):
    pidfile = tmp_path / "pid"
    t0 = time.time()
    with pytest.raises(full_gate.AdmissionBusy) as e:
        full_gate.run_admitted([gate, "run", "--"], "true", wait_limit=1,
                               env={**os.environ, "GATE_SLEEP": "30", "GATE_PIDFILE": str(pidfile)})
    assert time.time() - t0 < 5
    assert e.value.seconds == 1 and e.value.name == "gate"
    pid = int(pidfile.read_text())
    for _ in range(20):
        try:
            os.kill(pid, 0)
        except OSError:
            break
        time.sleep(0.1)
    else:
        os.kill(pid, 9)
        pytest.fail("gate still alive")


def test_limit_counts_from_admission(gate):
    t0 = time.time()
    with pytest.raises(subprocess.TimeoutExpired):
        full_gate.run_admitted([gate, "run", "--"], "sleep 10", limit=1, env={**os.environ, "GATE_SLEEP": "2"})
    assert 2.9 <= time.time() - t0 <= 8
