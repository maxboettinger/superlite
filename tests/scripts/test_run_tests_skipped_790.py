"""#790: a skipped Swift test is named in test-summary.json; JUnit skips keep their ids."""
from __future__ import annotations

import json

from test_plan_tools import run
from test_run_tests_plan_fallback import RUN_TESTS

SWIFT_OUT = ("◇ Test run started.\n➜ Test gatedNetworkTest() skipped: \"needs network\"\n➜ Test anotherGate() skipped.\n"
             "✔ Test ok() passed after 0.001 seconds.\n✔ Test run with 3 tests passed after 0.002 seconds.\n")


def spec(tmp_path, **kw):
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(kw), encoding="utf-8")


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_swift_skips_named_in_summary(tmp_path):
    (tmp_path / "out.txt").write_text(SWIFT_OUT, encoding="utf-8")
    spec(tmp_path, language="swift", test="cat out.txt")
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert s["passed"] == 1 and s["skipped"] == 2
    assert s["skipped_tests"] == ["gatedNetworkTest()", "anotherGate()"]


def test_junit_skips_unchanged(tmp_path):
    (tmp_path / "report.xml").write_text(
        '<testsuite><testcase classname="t" name="test_a" file="test_a.py"/>'
        '<testcase classname="t" name="test_b" file="test_a.py"><skipped message="x"/></testcase></testsuite>', encoding="utf-8")
    spec(tmp_path, language="python", test="cp report.xml {junit}", junit="{junit}")
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert s["passed"] == 1 and s["skipped"] == 1
    assert s["skipped_tests"] == ["test_a.py::test_b"]
