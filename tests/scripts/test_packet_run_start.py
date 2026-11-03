"""A test run closes an incident only when it started after the incident was logged (#101)."""
import importlib.util
import json
import subprocess
import sys
import time
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import incident  # noqa: E402

_spec = importlib.util.spec_from_file_location("pt_review_run_start", SCRIPTS / "pt_review.py")
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_run_start"] = pt
_spec.loader.exec_module(pt)


def rt(ctx: str = "frontend: failed", file: str = "-", **kw) -> dict:
    return {"kind": "test-failure", "file": file, "line": 0, "context": ctx, "resolution": "open", "agent": "run_tests", **kw}


def full(**kw) -> dict:
    return {"mode": "full", "passed": 10, "failed": 0, "skipped": 0, "failures": [], "files": {}, **kw}


def test_full_run_started_before_the_incident_keeps_it_open():
    e = rt(epoch=10.0)
    assert not pt.stale_in_run(e, [full(started=5.0)])  # started before, finished after: never ran the failing code
    assert pt.stale_in_run(e, [full(started=15.0)])


def test_file_run_started_before_the_incident_keeps_it_open():
    e = rt("test_x: boom", file="tests/a.py", epoch=10.0)
    green = {"mode": "fast", "passed": 3, "failed": 0, "failures": [], "files": {"tests/a.py": [3, 0]}}
    assert not pt.stale_in_run(e, [{**green, "started": 5.0}])
    assert pt.stale_in_run(e, [{**green, "started": 15.0}])


def test_an_earlier_started_newer_summary_does_not_decide():
    e = rt("test_x: boom", file="tests/a.py", epoch=10.0)
    green_fast = {"mode": "fast", "passed": 3, "failed": 0, "failures": [], "files": {"tests/a.py": [3, 0]}, "started": 15.0}
    assert pt.stale_in_run(e, [full(started=5.0), green_fast])  # newest by mtime started too early: the next one decides
    assert not pt.stale_in_run(e, [full(started=5.0)])


def test_entries_or_summaries_without_the_fields_keep_todays_rule():
    assert pt.stale_in_run(rt(), [full(started=5.0)])  # an entry logged before epoch existed
    assert pt.stale_in_run(rt(epoch=10.0), [full()])  # a summary written before started existed
    assert pt.stale_in_run(rt(epoch=True), [full(started=5.0)])  # not a number: ignored
    assert pt.stale_in_run(rt(epoch=10.0), [full(started="5")])


def test_incident_entries_carry_an_epoch():
    before = time.time()
    e = incident.make_entry("a.py", 1, "ctx")
    assert before <= e["epoch"] <= time.time() + 0.001
    assert e["time"] == time.strftime("%H:%M:%S", time.localtime(e["epoch"]))


def test_run_tests_summary_records_its_start(tmp_path):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "test_ok.py").write_text("def test_ok():\n    assert True\n")
    before = time.time()
    r = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--full"], cwd=tmp_path,
                       capture_output=True, text=True, timeout=120)
    assert r.returncode == 0, r.stdout + r.stderr
    s = json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))
    assert before <= s["started"] <= time.time()
