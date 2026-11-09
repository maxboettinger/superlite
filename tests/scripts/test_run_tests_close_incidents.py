"""run_tests: a green task run closes its `-` test-failure incidents, a green full suite every run_tests failure (#380)."""
import json
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

RED = "def test_x():\n    assert 1 == 2\n\n\ndef test_y():\n    assert 1 == 3\n"
GREEN = "def test_x():\n    assert 1 == 1\n\n\ndef test_y():\n    assert 1 == 1\n"


def rt(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, timeout=120)


def write(tmp_path, body, name="test_a.py"):
    (tmp_path / "tests").mkdir(exist_ok=True)
    (tmp_path / "tests" / name).write_text(body, encoding="utf-8")


def log(tmp_path):
    p = tmp_path / ".superlite" / "incidents.jsonl"
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()] if p.exists() else []


def newest(entries):
    out = {}
    for e in entries:
        if e.get("kind") != "verified":
            out[(e["file"], e["line"])] = e
    return out


def dash_repo(tmp_path):
    (tmp_path / "check.sh").write_text('if [ -e red ]; then echo "FAIL testFoo"; exit 1; fi\necho "1 passed"\n', encoding="utf-8")
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "other", "test": "sh check.sh", "test_file": "sh check.sh {files}"}), encoding="utf-8")
    return tmp_path


def dash(tmp_path):
    return newest(log(tmp_path)).get(("-", 0))


def test_green_task_run_closes_its_dash_failures(tmp_path):
    dash_repo(tmp_path)
    (tmp_path / "red").write_text("")
    assert rt(tmp_path, "--full", "--task", "T3").returncode == 1
    e = dash(tmp_path)
    assert e["resolution"] == "open" and e["task"] == "T3"
    (tmp_path / "red").unlink()
    assert rt(tmp_path, "--full", "--task", "T3").returncode == 0
    e = dash(tmp_path)
    assert e["resolution"] == "fixed" and e["context"] == "fixed: a green T3 run"


def test_green_run_of_another_task_keeps_it_open(tmp_path):
    dash_repo(tmp_path)
    (tmp_path / "red").write_text("")
    rt(tmp_path, "--full", "--task", "T3")
    (tmp_path / "red").unlink()
    assert rt(tmp_path, "--full", "--task", "T4").returncode == 0
    assert dash(tmp_path)["resolution"] == "open"
    assert rt(tmp_path, "--full").returncode == 0
    e = dash(tmp_path)
    assert e["resolution"] == "fixed" and e["context"] == "fixed: the full suite passed"


def test_red_runs_close_no_dash_failure(tmp_path):
    dash_repo(tmp_path)
    (tmp_path / "red").write_text("")
    rt(tmp_path, "--full", "--task", "T3")
    rt(tmp_path, "--full", "--task", "T3")
    assert dash(tmp_path)["resolution"] == "open"
    rt(tmp_path, "--full")
    assert dash(tmp_path)["resolution"] == "open"


def test_green_full_suite_closes_run_tests_failures_only(tmp_path):
    write(tmp_path, RED)
    assert rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3").returncode == 1
    reds = [e for e in log(tmp_path) if e["kind"] == "test-failure"]
    assert len(reds) == 2
    p = tmp_path / ".superlite" / "incidents.jsonl"
    with p.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps({"file": "tests/test_a.py", "line": 99, "kind": "test-failure", "agent": "package-reviewer",
                             "resolution": "open", "context": "test_z: missing"}) + "\n")
    write(tmp_path, GREEN)
    assert rt(tmp_path, "--full").returncode == 0
    state = newest(log(tmp_path))
    for e in reds:
        n = state[(e["file"], e["line"])]
        assert n["resolution"] == "fixed" and n["context"] == "fixed: the full suite passed"
    assert state[("tests/test_a.py", 99)]["resolution"] == "open"


def test_green_fast_without_task_closes_nothing(tmp_path):
    write(tmp_path, RED)
    rt(tmp_path, "--fast", "tests/test_a.py", "--task", "T3")
    before = len(log(tmp_path))
    write(tmp_path, GREEN)
    assert rt(tmp_path, "--fast", "tests/test_a.py").returncode == 0
    assert [e for e in log(tmp_path)[before:] if e["kind"] != "verified"] == []


def entry(epoch, kind="test-failure", **kw):
    e = {"file": "-", "line": 0, "kind": kind, "agent": "run_tests", "task": "T3", "resolution": "open",
         "context": "testFoo: failed", "epoch": epoch}
    e.update(kw)
    return e


def seed(tmp_path, *entries):
    p = tmp_path / "incidents.jsonl"
    p.write_text("".join(json.dumps(e) + "\n" for e in entries), encoding="utf-8")
    return p


def lines(p):
    return [json.loads(ln) for ln in p.read_text(encoding="utf-8").splitlines() if ln.strip()]


def test_in_process_closings(tmp_path):
    p = seed(tmp_path, entry(100.0))
    run_tests.resolve_passed(str(p), "T3", [], {}, green=True, full=False, started=200.0)
    got = lines(p)
    assert len(got) == 2 and got[1]["file"] == "-" and got[1]["line"] == 0 and got[1]["kind"] == "test-failure"
    assert got[1]["resolution"] == "fixed" and got[1]["context"] == "fixed: a green T3 run" and got[1]["task"] == "T3"
    p = seed(tmp_path, entry(100.0))
    run_tests.resolve_passed(str(p), None, [], {"tests/test_a.py": [2, 0]}, green=True, full=True, started=200.0)
    got = lines(p)
    assert len(got) == 2 and got[1]["context"] == "fixed: the full suite passed" and "task" not in got[1]


def test_entry_logged_after_start_stays_open(tmp_path):
    p = seed(tmp_path, entry(300.0))
    run_tests.resolve_passed(str(p), "T3", [], {}, green=True, full=False, started=200.0)
    run_tests.resolve_passed(str(p), None, [], {"a": [1, 0]}, green=True, full=True, started=200.0)
    assert len(lines(p)) == 1


def test_newest_no_result_keeps_the_location(tmp_path):
    p = seed(tmp_path, entry(100.0), entry(100.0, kind="no-result"))
    run_tests.resolve_passed(str(p), "T3", [], {}, green=True, started=200.0)
    assert len(lines(p)) == 2


def test_r1_ignores_started(tmp_path):  # R1 (a --task test that passes now) keeps its old behaviour: no start-time gate
    p = seed(tmp_path, entry(300.0, file="tests/test_a.py", context="test_x: failed"))
    run_tests.resolve_passed(str(p), "T3", [], {"tests/test_a.py": [1, 0]}, green=False, started=200.0)
    got = lines(p)
    assert len(got) == 2 and got[1]["context"] == "fixed: passed on a later run"
