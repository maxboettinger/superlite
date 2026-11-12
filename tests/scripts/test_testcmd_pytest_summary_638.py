"""testcmd.parse_output: pytest's last summary line and short summary ids win (#638)."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402


def triple(r):
    return (r["passed"], r["failed"], r["skipped"])


def test_nested_summary_in_failure_output_loses():
    fails = "".join(f"FAILED tests/f{i}.py::t - boom\n" for i in range(63))
    t = ("=== FAILURES ===\nTests: 1 failed, 2 passed\n1 failed, 2 passed in 0.2s\nFAILED tests/inner.py::t\n"
         "=== short test summary info ===\n" + fails + "=== 63 failed, 7203 passed, 9 skipped in 591.45s (0:09:51) ===\n")
    r = testcmd.parse_output(t, 1)
    assert triple(r) == (7203, 63, 9)
    assert len(r["names"]) == 50 and "tests/inner.py::t" not in r["names"]


def test_errors_count_as_failed():
    t = ("=== short test summary info ===\nFAILED tests/a.py::t - x\nERROR tests/b.py::u - y\nERROR tests/c.py::v\n"
         "=== 1 failed, 5 passed, 2 errors in 3.00s ===\n")
    r = testcmd.parse_output(t, 1)
    assert r["failed"] == 3 and r["passed"] == 5
    assert "tests/b.py::u" in r["names"] and "tests/c.py::v" in r["names"]


def test_param_id_with_spaces():
    t = "=== short test summary info ===\nFAILED tests/a.py::t[a b] - x\n1 failed in 0.1s\n"
    assert testcmd.parse_output(t, 1)["names"] == ["tests/a.py::t[a b]"]


def test_job_slot_line_never_counts():
    r = testcmd.parse_output("job.sh: waiting for a free job slot\n", 1)
    assert r["failed"] == 1 and r["counted"] is False and r["names"] == [] and r["tail"] == []


def test_xfail_xpass_deselected():
    r = testcmd.parse_output("3 passed, 1 xfailed, 1 xpassed, 4 deselected, 2 warnings in 1.00s\n", 0)
    assert triple(r) == (4, 0, 1)


def test_green_with_noise():
    r = testcmd.parse_output("7200 passed, 9 skipped in 591.45s (0:09:51)\njob.sh: waiting for a free job slot\n", 0)
    assert triple(r) == (7200, 0, 9) and r["names"] == []
    assert r["tail"] == ["7200 passed, 9 skipped in 591.45s (0:09:51)"]


def test_example_names():
    t = ("tests/a.py F.\n=== short test summary info ===\n"
         "FAILED tests/a.py::test_x - AssertionError: 1 failed, 2 passed in 0.1s\n1 failed, 1 passed in 0.50s\n")
    r = testcmd.parse_output(t, 1)
    assert triple(r) == (1, 1, 0) and r["names"] == ["tests/a.py::test_x"] and r["counted"] is True


def test_names_without_header_use_run_above_summary():
    t = ("FAILED tests/old.py::t\nnoise line\nFAILED tests/a.py::t1 - x\nERROR tests/b.py::t2\n1 failed, 1 error, 3 passed in 0.5s\n")
    r = testcmd.parse_output(t, 1)
    assert r["names"] == ["tests/a.py::t1", "tests/b.py::t2"] and triple(r) == (3, 2, 0)
