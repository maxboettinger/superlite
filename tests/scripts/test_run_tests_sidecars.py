"""run_tests counts sidecar JUnit reports (Swift Testing) and keeps the log free of ANSI escapes."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS, run

RUN_TESTS = SCRIPTS / "run_tests.py"


def suite(n, name="A"):
    cases = "".join(f'<testcase classname="Tests/{name}Tests.swift" name="t{i}" time="0.01"></testcase>' for i in range(n))
    return f'<?xml version="1.0"?><testsuites><testsuite name="{name}">{cases}</testsuite></testsuites>'


RUNNER = """import shutil, sys
shutil.copy("sample-junit.xml", sys.argv[1])
if len(sys.argv) > 2:
    open(sys.argv[1][:-4] + "-swift-testing.xml", "w").write(open(sys.argv[2]).read())
"""

ANSI_RUNNER = """import sys
sys.stdout.write("\\x1b[1;33mwarning\\x1b[0m: something\\n")
sys.exit(1)
"""


def setup(tmp_path, sidecar_text, runner=RUNNER):
    (tmp_path / "sample-junit.xml").write_text(suite(1), encoding="utf-8")
    (tmp_path / "sidecar.xml").write_text(sidecar_text, encoding="utf-8")
    (tmp_path / "runner.py").write_text(runner, encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    cmd = f"{sys.executable} runner.py {{junit}} sidecar.xml"
    (sl / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd, "junit": "{junit}", "setup": ""}), encoding="utf-8")


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_sidecar_junit_counted(tmp_path):
    setup(tmp_path, suite(3, "B"))
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert cp.out.strip().split()[:3] == ["4", "0", "0"]
    assert summary(tmp_path)["passed"] == 4


def test_unparseable_sidecar_is_ignored(tmp_path):
    setup(tmp_path, "not xml")
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert summary(tmp_path)["passed"] == 1


def test_log_has_no_ansi_escapes(tmp_path):
    (tmp_path / "runner.py").write_text(ANSI_RUNNER, encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    cmd = f"{sys.executable} runner.py"
    (sl / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd, "junit": "", "setup": ""}), encoding="utf-8")
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    assert cp.returncode == 1, cp.both
    log = (sl / "test-output.log").read_text(encoding="utf-8")
    assert "warning" in log and "\x1b" not in log
    s = summary(tmp_path)
    assert s["failures"] and all("\x1b" not in f for f in s["failures"])
