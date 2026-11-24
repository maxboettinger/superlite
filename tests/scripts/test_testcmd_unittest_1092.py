"""#1092: run_tests reads python -m unittest's `Ran N tests` and its OK / FAILED verdict, summed over chained runs."""
from __future__ import annotations

import json
import os
import shlex
import subprocess
import sys

from _fixtures import DISK_FREE
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

EQ, SEP = "=" * 70, "-" * 70
GREEN = f"......\n{SEP}\nRan 64 tests in 0.512s\n\nOK\n"
MIXED = "\n".join([
    "FE.sxu", EQ, "ERROR: test_err (test_a.A.test_err)", SEP, "Traceback (most recent call last):",
    '  File "/p/t/test_a.py", line 5, in test_err', '    raise ValueError("x")', "ValueError: x", "",
    EQ, "FAIL: test_bad (test_a.A.test_bad)", SEP, "Traceback (most recent call last):",
    '  File "/p/t/test_a.py", line 4, in test_bad', "    self.assertEqual(1, 2)", "AssertionError: 1 != 2", "",
    EQ, "UNEXPECTED SUCCESS: test_xp (test_a.A.test_xp)", SEP, "Ran 6 tests in 0.002s", "",
    "FAILED (failures=1, errors=1, skipped=1, expected failures=1, unexpected successes=1)", ""])


def triple(r):
    return (r["passed"], r["failed"], r["skipped"])


def test_green_run_counts():
    r = testcmd.parse_output(GREEN, 0)
    assert triple(r) == (64, 0, 0) and r["counted"] is True and r["names"] == [] and r["empty"] == ""


def test_ok_with_skips_and_expected_failures():
    r = testcmd.parse_output("Ran 10 tests in 0.100s\n\nOK (skipped=2, expected failures=1)\n", 0)
    assert triple(r) == (7, 0, 3)


def test_mixed_verdict_columns():
    r = testcmd.parse_output(MIXED, 1)
    assert triple(r) == (1, 3, 2)
    assert r["names"] == ["test_a.A.test_err", "test_a.A.test_bad", "test_a.A.test_xp"]
    assert r["reasons"]["test_a.A.test_err"] == ("ValueError: x", 0)
    assert r["reasons"]["test_a.A.test_bad"] == ("AssertionError: 1 != 2", 0)
    assert r["reasons"]["test_a.A.test_xp"] == ("unexpected success", 0)


def test_errors_only():
    r = testcmd.parse_output("Ran 3 tests in 0.010s\n\nFAILED (errors=1)\n", 1)
    assert triple(r) == (2, 1, 0)


def test_chained_runs_are_summed():
    r = testcmd.parse_output(GREEN + "Ran 5 tests in 0.100s\n\nOK (skipped=1)\n", 0)
    assert triple(r) == (68, 0, 1)


def test_chained_red_second_run():
    r = testcmd.parse_output(GREEN + "Ran 4 tests in 0.100s\n\nFAILED (failures=2)\n", 1)
    assert triple(r) == (66, 2, 0)


def test_python_310_ids_get_the_method():
    text = "\n".join([EQ, "FAIL: test_bad (pkg.mod.Case)", SEP, "AssertionError: no", "", SEP, "Ran 1 test in 0.001s", "", "FAILED (failures=1)", ""])
    r = testcmd.parse_output(text, 1)
    assert triple(r) == (0, 1, 0) and r["names"] == ["pkg.mod.Case.test_bad"]


def test_names_only_on_a_red_exit():
    text = "\n".join([EQ, "FAIL: test_bad (pkg.mod.Case.test_bad)", SEP, "AssertionError: no", "", SEP, "Ran 2 tests in 0.001s", "", "OK", ""])
    r = testcmd.parse_output(text, 0)
    assert triple(r) == (2, 0, 0) and r["names"] == []


def test_no_tests_ran_is_empty():
    r = testcmd.parse_output(f"\n{SEP}\nRan 0 tests in 0.000s\n\nNO TESTS RAN\n", 5)
    assert r["counted"] is False and r["passed"] == 0 and r["empty"] == "Ran 0 tests in 0.000s"
    old = testcmd.parse_output(f"\n{SEP}\nRan 0 tests in 0.000s\n\nOK\n", 0)
    assert old["counted"] is False and old["empty"] == "Ran 0 tests in 0.000s"


def test_ran_line_without_verdict_does_not_count():
    r = testcmd.parse_output("Ran 5 tests in 0.200s\nsomething else\n", 0)
    assert r["counted"] is False and r["passed"] == 0


def test_pytest_summary_wins():
    r = testcmd.parse_output("Ran 9 tests in 0.100s\n\nOK\n============ 3 passed in 0.12s ============\n", 0)
    assert triple(r) == (3, 0, 0)


def _project(tmp_path, dirs, command):
    for name, body in dirs.items():
        (tmp_path / name).mkdir()
        (tmp_path / name / f"test_{name}.py").write_text(body, encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "python", "test": command}), encoding="utf-8")
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") or k == "SUPERLITE_HOME"}
    env.update(DISK_FREE)
    cp = subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), "--full"], cwd=tmp_path, capture_output=True, text=True, env=env)
    return cp, json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


OK2 = "import unittest\nclass A(unittest.TestCase):\n    def test_a(self): pass\n    def test_b(self): pass\n"
SKIP = "import unittest\nclass B(unittest.TestCase):\n    def test_c(self): pass\n    @unittest.skip('later')\n    def test_d(self): pass\n"
BAD = "import unittest\nclass C(unittest.TestCase):\n    def test_bad(self): self.assertEqual(1, 2)\n"


def test_real_unittest_chain_through_run_tests(tmp_path):
    py = shlex.quote(sys.executable)
    cp, s = _project(tmp_path, {"one": OK2, "two": SKIP}, f"{py} -m unittest discover -s one && {py} -m unittest discover -s two")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert (s["passed"], s["failed"], s["skipped"]) == (3, 0, 1) and "error" not in s


def test_real_unittest_failure_through_run_tests(tmp_path):
    py = shlex.quote(sys.executable)
    cp, s = _project(tmp_path, {"three": BAD}, f"{py} -m unittest discover -s three")
    assert cp.returncode == 1
    assert s["failed"] == 1 and s["failures"] == ["-::test_three.C.test_bad: AssertionError: 1 != 2"]
