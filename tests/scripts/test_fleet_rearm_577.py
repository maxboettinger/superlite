# tests/scripts/test_fleet_rearm_577.py
import json, os, sys, time
from pathlib import Path
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_rearm as fr  # noqa: E402


def pointer(sd, name, summary):
    (sd / name).write_text(json.dumps({"id": "r1", "summary": str(summary)}), encoding="utf-8")


def summary(sd, name="test-summary-r1.json", age_s=3600, data=None):
    p = sd / name
    p.write_text(json.dumps(data or {"mode": "full", "passed": 7, "failed": 0}), encoding="utf-8")
    t = time.time() - age_s
    os.utime(p, (t, t))
    return p


def pidfile(p, pid, age_s=60):
    f = p.with_suffix(".pid")
    f.write_text(str(pid), encoding="utf-8")
    t = time.time() - age_s
    os.utime(f, (t, t))


def test_ended_run_line(tmp_path):
    s = summary(tmp_path)
    pointer(tmp_path, "test-summary.latest", s)
    assert fr.test_run_lines(tmp_path) == [f"test run ended: {s} tests (full): 7 passed, 0 failed"]


def test_running_run_line(tmp_path):
    s = tmp_path / "test-summary-r1.json"
    pointer(tmp_path, "test-summary.latest", s)
    pidfile(s, os.getpid())
    out = fr.test_run_lines(tmp_path)
    assert out == [f"test run running: {s}; re-arm: {fr.SL} run_tests --wait {s}"]
    assert Path(fr.SL).is_absolute()


def test_died_run_line(tmp_path):
    s = tmp_path / "test-summary-r1.json"
    pointer(tmp_path, "test-summary.latest", s)
    pidfile(s, 999999)
    assert fr.test_run_lines(tmp_path) == [f"test run died: {s} (no summary, pid gone)"]


def test_old_runs_left_out(tmp_path):
    s = summary(tmp_path, age_s=13 * 3600)
    pointer(tmp_path, "test-summary.latest", s)
    d = tmp_path / "test-summary-r2.json"
    pointer(tmp_path, "test-summary-T2.latest", d)
    pidfile(d, 999999, age_s=13 * 3600)
    assert fr.test_run_lines(tmp_path) == []
    assert fr.test_run_lines(tmp_path, now_s=time.time() - 20 * 3600) == fr.test_run_lines(tmp_path, now_s=time.time() - 20 * 3600)
    assert fr.test_run_lines(tmp_path / "none") == []


def test_task_pointers_and_dedupe(tmp_path):
    a = summary(tmp_path, "test-summary-r1.json")
    b = summary(tmp_path, "test-summary-a0.json")
    pointer(tmp_path, "test-summary.latest", a)
    pointer(tmp_path, "test-summary-T3.latest", a)
    pointer(tmp_path, "test-summary-T4.latest", b)
    out = fr.test_run_lines(tmp_path)
    assert len(out) == 2
    assert out == sorted(out, key=lambda l: l.split(" ")[3])
    assert str(b) in out[0] and str(a) in out[1]


def test_bad_pointer_ignored(tmp_path):
    (tmp_path / "test-summary.latest").write_text("{nope", encoding="utf-8")
    (tmp_path / "test-summary-T1.latest").write_text('{"id": "x"}', encoding="utf-8")
    (tmp_path / "test-summary-T2.latest").write_text('[1]', encoding="utf-8")
    assert fr.test_run_lines(tmp_path) == []
