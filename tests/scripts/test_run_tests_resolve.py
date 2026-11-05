"""run_tests --task Tn: a green run resolves the task's open test-failure incidents (#180); a run without results logs no-result (#140)."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"

RED = "def test_x():\n    assert 1 == 2\n\n\ndef test_y():\n    assert 1 == 3\n"
GREEN = "def test_x():\n    assert 1 == 1\n\n\ndef test_y():\n    assert 1 == 1\n"
HALF = "def test_x():\n    assert 1 == 2\n\n\ndef test_y():\n    assert 1 == 1\n"


def rt(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def write(tmp_path, body, name="test_a.py"):
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / name).write_text(body, encoding="utf-8")


def log(tmp_path):
    p = tmp_path / ".superlite" / "incidents.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []


def newest(entries):
    """Newest non-verified entry per location, as the packet and `finish` count open."""
    out = {}
    for e in entries:
        if e.get("kind") != "verified":
            out[(e["file"], e["line"])] = e
    return out


def test_green_run_resolves_red_incidents(tmp_path):
    write(tmp_path, RED)
    assert rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3").returncode == 1
    red = [e for e in log(tmp_path) if e["kind"] == "test-failure"]
    assert len(red) == 2 and {e["task"] for e in red} == {"T3"} and {e["resolution"] for e in red} == {"open"}
    assert {e["agent"] for e in red} == {"run_tests"}
    write(tmp_path, GREEN)
    assert rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3").returncode == 0
    entries = log(tmp_path)
    assert len(entries) == 4
    closed = [e for e in entries[2:]]
    assert {(e["file"], e["line"]) for e in closed} == {(e["file"], e["line"]) for e in red}
    assert {e["resolution"] for e in closed} == {"fixed"} and {e["context"] for e in closed} == {"fixed: passed on a later run"}
    assert {e["kind"] for e in closed} == {"test-failure"}
    assert {e["resolution"] for e in newest(entries).values()} == {"fixed"}


def test_other_task_not_resolved(tmp_path):
    write(tmp_path, RED)
    rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3")
    write(tmp_path, GREEN)
    assert rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T4").returncode == 0
    entries = log(tmp_path)
    assert len(entries) == 2 and {e["resolution"] for e in newest(entries).values()} == {"open"}
    assert rt(tmp_path, "--fast", "tests/test_a.py").returncode == 0  # no --task: nothing is resolved either
    assert len(log(tmp_path)) == 2


def test_only_passing_tests_are_resolved(tmp_path):
    write(tmp_path, RED)
    rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3")
    write(tmp_path, HALF)
    assert rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3").returncode == 1
    state = [e for e in newest(log(tmp_path)).values() if e["kind"] == "test-failure"]
    done = [e for e in state if e["resolution"] == "fixed"]
    still = [e for e in state if e["resolution"] == "open"]
    assert len(done) == 1 and len(still) == 1 and still[0]["context"].startswith("test_x")


def test_other_file_is_left_open(tmp_path):
    write(tmp_path, RED)
    rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3")
    write(tmp_path, GREEN, name="test_b.py")
    assert rt(tmp_path, "--fast", "tests/test_b.py", "--task", "T3").returncode == 0
    assert {e["resolution"] for e in newest(log(tmp_path)).values() if e["file"].endswith("test_a.py")} == {"open"}


def test_no_result_logs_incident(tmp_path):
    write(tmp_path, GREEN)
    r = rt(tmp_path, "--fast", "tests/test_missing.py")
    assert r.returncode == 2 and "produced no results" in r.stderr, r.stdout + r.stderr
    hits = [e for e in log(tmp_path) if e["kind"] == "no-result"]
    assert len(hits) == 1 and hits[0]["agent"] == "run_tests" and hits[0]["resolution"] == "open"
    assert "produced no results" in hits[0]["context"]
