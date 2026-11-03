"""Tests for pt_review packet: stale test-failure incidents, fast-summary label, wait on an older full run."""
from __future__ import annotations

import importlib.util
import json
import subprocess
import sys
import threading
import time
from pathlib import Path

import pytest

HERE = Path(__file__).resolve().parent
SCRIPT = HERE.parent.parent / "skills" / "subagent-driven-development" / "scripts" / "pt_review.py"
_spec = importlib.util.spec_from_file_location("pt_review_stale", SCRIPT)
pt = importlib.util.module_from_spec(_spec)
sys.modules["pt_review_stale"] = pt
_spec.loader.exec_module(pt)

PLAN = "# p\n\n### T1 thing · Complexity 1\n**Owns:** src/a.py\n\n## Review Focus\n- none\n"


@pytest.fixture()
def proj(tmp_path: Path) -> Path:
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "plan.md").write_text(PLAN, encoding="utf-8")
    return tmp_path


def inc(kind: str, ctx: str, file: str = "tests/a.py", line: int = 1) -> dict:
    return {"kind": kind, "file": file, "line": line, "context": ctx, "resolution": "", "agent": "T1"}


def write_log(proj: Path, entries: list[dict]) -> None:
    (proj / ".superlite" / "incidents.jsonl").write_text(
        "\n".join(json.dumps(e) for e in entries) + "\n", encoding="utf-8")


def write_summary(path: Path, **kw) -> None:
    d = {"passed": 3, "failed": 0, "skipped": 0, "seconds": 1.0, "mode": "full",
         "failures": [], "skipped_tests": [], "files": {"tests/a.py": [3, 0]}}
    d.update(kw)
    path.write_text(json.dumps(d), encoding="utf-8")


def packet(proj: Path, *extra: str) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(SCRIPT), "packet", "--plan", str(proj / "plan.md"),
                           "--root", str(proj), "--out", str(proj / "packet.md"), *extra],
                          capture_output=True, text=True, timeout=60)


def text(proj: Path) -> str:
    return (proj / "packet.md").read_text(encoding="utf-8")


def test_packet_drops_green_tdd_red_incidents(proj):
    write_log(proj, [inc("test-failure", f"test_{n}: AssertionError", line=n) for n in "xyz"]
              + [inc("exception", "boom happened", file="src/a.py", line=7)])
    write_summary(proj / ".superlite" / "test-summary.json")
    r = packet(proj)
    assert r.returncode == 0, r.stderr
    t = text(proj)
    assert "boom happened" in t
    assert "test_x" not in t and "test_y" not in t and "test_z" not in t
    assert "dropped 3 stale test-failure incident(s)" in t


def test_packet_keeps_still_failing_incident(proj):
    write_log(proj, [inc("test-failure", "test_x: AssertionError")])
    write_summary(proj / ".superlite" / "test-summary.json", passed=2, failed=1,
                  failures=["tests/a.py::test_x: AssertionError"], files={"tests/a.py": [2, 1]})
    packet(proj)
    t = text(proj)
    assert "test_x: AssertionError" in t
    assert "dropped" not in t


def test_fast_summary_labelled_and_failures_count(proj):
    write_summary(proj / ".superlite" / "test-summary.json", mode="fast", passed=2, failed=1,
                  failures=["tests/a.py::test_x: bad"], files={"tests/a.py": [2, 1]})
    packet(proj)
    t = text(proj)
    sec = t.split("## 4. Test summary")[1].split("## 5.")[0]
    assert "full suite not run yet" in sec
    assert "FAILING: tests/a.py::test_x: bad" in sec
    assert "REVIEW REQUIRED" in t


def test_full_summary_unchanged(proj):
    write_summary(proj / ".superlite" / "test-summary.json")
    packet(proj)
    sec = text(proj).split("## 4. Test summary")[1].lstrip("\n")
    assert sec.startswith("- passed 3")


def write_pointer(proj: Path, started: float, mode: str = "full") -> Path:
    target = proj / ".superlite" / "test-summary-run1.json"
    (proj / ".superlite" / "test-summary.latest").write_text(
        json.dumps({"id": "run1", "summary": str(target), "started": started, "mode": mode}), encoding="utf-8")
    return target


def test_packet_waits_for_older_full_run(proj):
    target = write_pointer(proj, time.time() - 10)
    threading.Timer(1.0, lambda: write_summary(target, passed=42)).start()
    r = packet(proj, "--wait-timeout", "5")
    assert r.returncode == 0, r.stderr
    assert "- passed 42" in text(proj)


def test_packet_ignores_fresh_full_run(proj):
    write_pointer(proj, time.time())
    write_summary(proj / ".superlite" / "test-summary.json", passed=7)
    t0 = time.time()
    packet(proj, "--wait-timeout", "30")
    assert time.time() - t0 < 5
    assert "- passed 7" in text(proj)


def test_wait_timeout_falls_back(proj):
    write_pointer(proj, time.time() - 10)
    r = packet(proj, "--wait-timeout", "1")
    assert r.returncode == 0
    assert "timed out" in r.stderr
    assert (proj / "packet.md").is_file()


def test_fast_pointer_never_waits(proj):
    write_pointer(proj, time.time() - 10, mode="fast")
    t0 = time.time()
    packet(proj, "--wait-timeout", "30")
    assert time.time() - t0 < 5


def test_stale_test_failure_cases():
    e = {"kind": "test-failure", "file": "tests/a.py", "context": "test_x: AssertionError"}
    assert pt.stale_test_failure(e, {"files": {"tests/a.py": [3, 0]}, "failures": []}) is True
    red = {"files": {"tests/a.py": [2, 1]}, "failures": ["tests/a.py::test_x: AssertionError"]}
    assert pt.stale_test_failure(e, red) is False
    other = {"files": {"tests/a.py": [2, 1]}, "failures": ["tests/a.py::test_y: boom"]}
    assert pt.stale_test_failure(e, other) is True
    n = {"kind": "test-failure", "file": "tests/a.py", "context": "next_tasks fails; shared state"}
    assert pt.stale_test_failure(n, {"files": {"tests/a.py": [4, 0]}}) is True
    assert pt.stale_test_failure(n, {"files": {"tests/a.py": [3, 1]}}) is False
    assert pt.stale_test_failure(e, {"files": {"tests/b.py": [4, 0]}}) is False
    assert pt.stale_test_failure({**e, "kind": "exception"}, {"files": {"tests/a.py": [3, 0]}}) is False
    assert pt.stale_test_failure(e, None) is False
    assert pt.stale_test_failure(e, {"passed": 3}) is False


def rt(ctx: str, file: str = "-", line: int = 0) -> dict:
    """A test-failure incident as run_tests logs it (`-` when the runner wrote no JUnit)."""
    return {"kind": "test-failure", "file": file, "line": line, "context": ctx, "resolution": "open", "agent": "run_tests"}


def full(**kw) -> dict:
    d = {"mode": "full", "passed": 10, "failed": 0, "skipped": 0, "failures": [], "files": {}}
    d.update(kw)
    return d


def test_full_run_closes_run_tests_failure_it_does_not_list():
    """#81: a later full run supersedes every run_tests failure it does not list, `-` (no JUnit) entries included."""
    e = rt("frontend: failed")
    assert pt.stale_in_run(e, [full()])
    assert pt.stale_in_run(e, [full(failed=1, failures=["-::backend: failed"])])
    assert not pt.stale_in_run(e, [full(failed=1, failures=["-::frontend: failed"])])
    junit = rt("testBar(): XCTAssertEqual failed", file="Tests/AppTests/FooTests.swift", line=12)
    assert pt.stale_in_run(junit, [full(files={"AppTests.FooTests": [10, 0]})])  # the full run keys the file differently


def test_newest_covering_summary_still_decides():
    """#81: a newer run that lists the failure keeps it open; a newer fast run that says nothing does not decide."""
    e = rt("frontend: failed")
    red_fast = {"mode": "fast", "passed": 0, "failed": 1, "failures": ["-::frontend: failed"], "files": {}}
    green_fast = {"mode": "fast", "passed": 3, "failed": 0, "failures": [], "files": {"tests/b.py": [3, 0]}}
    assert not pt.stale_in_run(e, [red_fast, full()])
    assert pt.stale_in_run(e, [green_fast, full()])
    assert not pt.stale_in_run(e, [green_fast])


def test_full_run_rule_only_for_run_tests_entries():
    """#81: an agent's own test-failure note is closed by its file's run only, as before; a crashed full run decides nothing."""
    agent = dict(rt("test_x: boom", file="src/a.py", line=3), agent="T3")
    assert not pt.stale_in_run(agent, [full()])
    crashed = full(passed=0, failed=1, failures=["no test command found"])
    assert not pt.stale_in_run(rt("frontend: failed"), [crashed])


def test_listed_survives_200_char_cuts():
    """#81 review: a red full run whose failure line was cut at 200 chars still lists a long test."""
    name = "test_" + "x" * 210
    cut = rt((name + ": AssertionError")[:199] + "\u2026", file="tests/test_long.py")  # make_entry's 200-char cut
    line = f"tests/test_long.py::{name}: AssertionError"[:200]  # write_summary's 200-char cut
    assert not pt.stale_in_run(cut, [full(failed=1, failures=[line])])
    deep = "/".join(["pkg"] * 15) + "/test_deep.py"
    long_head = rt("test_" + "y" * 140 + ": boom", file=deep)
    line = f"{deep}::test_{'y' * 140}: boom"[:200]
    assert len(line) == 200
    assert not pt.stale_in_run(long_head, [full(failed=1, failures=[line])])
    assert pt.stale_in_run(long_head, [full()])


def test_listed_under_another_file_key():
    """#81 review: a red full run that keys the same test under another file keeps it open."""
    e = rt("testBar(): XCTAssertEqual failed", file="Tests/AppTests/FooTests.swift", line=12)
    red = full(failed=1, failures=["AppTests.FooTests::testBar(): XCTAssertEqual failed"], files={"AppTests.FooTests": [9, 1]})
    assert not pt.stale_in_run(e, [red])


def test_crash_with_double_colons_decides_nothing():
    """#81 review: a crashed full run is known by its error key, even when the message holds `::`."""
    msg = "error: Foo::bar panicked"
    assert not pt.stale_in_run(rt("frontend: failed"), [full(passed=0, failed=1, failures=[msg], error=msg)])


def test_packet_drops_unfiled_failure_after_green_full_run(proj):
    """#81 end to end: a mid-build `-` failure from a run without JUnit is dropped once a full run is green."""
    write_log(proj, [rt("frontend: failed"), inc("exception", "boom happened", file="src/a.py", line=7)])
    write_summary(proj / ".superlite" / "test-summary.json", files={})
    r = packet(proj)
    assert r.returncode == 0, r.stderr
    t = text(proj)
    assert "frontend: failed" not in t and "boom happened" in t
    assert "dropped 1 stale test-failure incident(s)" in t


def test_read_test_summary_fast_label(tmp_path):
    p = tmp_path / "s.json"
    write_summary(p, mode="fast", passed=16)
    assert pt.read_test_summary(p) == (
        "- full suite not run yet (it runs alongside this review); newest fast run:\n"
        "- passed 16 · failed 0 · skipped 0", 0)


def test_stale_name_match_is_exact():
    e = {"kind": "test-failure", "file": "tests/a.py", "context": "test_x: boom"}
    f2 = {"files": {"tests/a.py": [2, 1]}, "failures": ["tests/a.py::test_x2: boom"]}
    assert pt.stale_test_failure(e, f2) is True  # test_x is green, only test_x2 fails
    e2 = {**e, "context": "test_x2: boom"}
    assert pt.stale_test_failure(e2, {"files": {"tests/a.py": [2, 1]},
                                      "failures": ["tests/a.py::test_x: boom"]}) is True
    param = {"files": {"tests/a.py": [2, 1]}, "failures": ["tests/a.py::test_x[1]: boom"]}
    assert pt.stale_test_failure(e, param) is False


def test_corrupt_summary_and_pointer_do_not_crash(tmp_path):
    s = tmp_path / "test-summary.json"
    s.write_text("{not json", encoding="utf-8")
    (tmp_path / "test-summary.latest").write_text("[1,2", encoding="utf-8")
    assert pt.load_summary(s) is None
    pt.wait_for_full(s, 1)
    assert pt.newest_summary_path(s) == s
    (tmp_path / "test-summary.latest").write_text('{"summary": "x", "mode": "full", "started": "bad"}',
                                                  encoding="utf-8")
    pt.wait_for_full(s, 1)
    s.write_text("[1]", encoding="utf-8")
    assert pt.load_summary(s) is None


@pytest.mark.parametrize("val", ["none", "-", "`none`", "N/A", ""])
def test_produces_none_values_are_empty(val: str):
    plan = f"# p\n\n### T1 docs · Complexity 1\n**Owns:** docs/x.md\n**Produces:** {val}\n"
    (p := Path(__import__("tempfile").mkdtemp()) / "plan.md").write_text(plan, encoding="utf-8")
    assert pt.parse_plan(p).tasks["T1"].produces() == []


def test_contract_produces_none_passes(proj: Path):
    (proj / "docs").mkdir()
    (proj / "docs" / "x.md").write_text("x\n", encoding="utf-8")
    (proj / "plan.md").write_text(
        "# p\n\n### T1 docs · Complexity 1\n**Owns:** docs/x.md\n**Produces:** none\n", encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPT), "contract", "--plan", str(proj / "plan.md"),
                        "--root", str(proj)], capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr
    assert "MISMATCH" not in r.stdout.upper() and "MISSED" not in r.stdout.upper()
