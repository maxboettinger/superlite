"""B119: parse_output keeps each pytest short-summary id's message and traceback line."""
from __future__ import annotations

import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

PROBE = "bringing up nodes...\n\n.F    [100%]\n=================================== FAILURES ===================================\n___________________________________ test_bad ___________________________________\n[gw1] linux -- Python 3.12.3 /usr/bin/python\n\n    def test_bad():\n>       assert 5.23 < 5\nE       assert 5.23 < 5\n\ntests/test_probe.py:5: AssertionError\n=========================== short test summary info ============================\nFAILED tests/test_probe.py::test_bad - assert 5.23 < 5\n1 failed, 1 passed in 0.31s\nmaxapp remote: command exited 1\n"


def test_reason_and_line_from_section():
    assert testcmd.parse_output(PROBE, 1)["reasons"] == {"tests/test_probe.py::test_bad": ("assert 5.23 < 5", 5)}


def test_two_tests_same_file_get_own_lines():
    text = ("=== FAILURES ===\n____ test_a ____\ntests/t.py:4: AssertionError\n____ test_b ____\ntests/t.py:9: AssertionError\n"
            "=== short test summary info ===\nFAILED tests/t.py::test_a - boom\nFAILED tests/t.py::test_b - bang\n2 failed in 0.1s\n")
    r = testcmd.parse_output(text, 1)["reasons"]
    assert r == {"tests/t.py::test_a": ("boom", 4), "tests/t.py::test_b": ("bang", 9)}


def test_class_param_header():
    text = ("=== FAILURES ===\n____ TestX.test_y[1] ____\ntests/a.py:7: AssertionError\n"
            "=== short test summary info ===\nFAILED tests/a.py::TestX::test_y[1] - no\n1 failed in 0.1s\n")
    assert testcmd.parse_output(text, 1)["reasons"] == {"tests/a.py::TestX::test_y[1]": ("no", 7)}


def test_collection_error_id():
    text = ("=== ERRORS ===\n____ ERROR collecting tests/b.py ____\ntests/b.py:1: in <module>\n    import x\n"
            "=== short test summary info ===\nERROR tests/b.py - ImportError: no module x\n1 error in 0.1s\n")
    assert testcmd.parse_output(text, 1)["reasons"] == {"tests/b.py": ("ImportError: no module x", 1)}


def test_long_message_cut():
    text = f"=== short test summary info ===\nFAILED tests/a.py::t - {'x' * 300}\n1 failed in 0.1s\n"
    msg, line = testcmd.parse_output(text, 1)["reasons"]["tests/a.py::t"]
    assert msg == "x" * 160 and line == 0


def test_no_message_no_section():
    assert testcmd.parse_output("FAILED tests/a.py::TestX::test_y[1]\n1 failed in 0.10s\n", 1)["reasons"] == {"tests/a.py::TestX::test_y[1]": ("", 0)}


def test_green_and_non_pytest_empty():
    assert testcmd.parse_output("3 passed in 0.10s\n", 0)["reasons"] == {}
    assert testcmd.parse_output("--- FAIL: TestX\n", 1)["reasons"] == {}


def test_merge_parsed_keeps_reasons():
    p1 = {"reasons": {"a::t": ("one", 1)}}
    p2 = {"reasons": {"a::t": ("two", 2), "b::t": ("x", 3)}}
    assert testcmd.merge_parsed([("a", p1), ("b", p2)])["reasons"] == {"a::t": ("one", 1), "b::t": ("x", 3)}
