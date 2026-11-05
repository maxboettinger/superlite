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


ERR_RUNNER = """import sys
for i in range(60):
    print(f"filler {i}")
print("Foo.swift:3:5: error: cannot find 'Date' in scope")
for i in range(50):
    print(f"more {i}")
print("** TEST FAILED **")
sys.exit(65)
"""


def test_compile_error_leads_failures_and_log(tmp_path):
    (tmp_path / "runner.py").write_text(ERR_RUNNER, encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    cmd = f"{sys.executable} runner.py"
    (sl / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd, "junit": "", "setup": ""}), encoding="utf-8")
    cp = run(RUN_TESTS, "--full", cwd=tmp_path)
    assert cp.returncode == 1, cp.both
    assert "build error: Foo.swift:3:5: error:" in summary(tmp_path)["failures"][0]
    log = (sl / "test-output.log").read_text(encoding="utf-8")
    assert "Foo.swift:3:5: error: cannot find 'Date' in scope" in log and "** TEST FAILED **" in log


def test_indented_error_in_tail_not_duplicated(tmp_path):
    (tmp_path / "runner.py").write_text('print("  Foo.swift:3:5: error: bad")\nprint("** TEST FAILED **")\nimport sys; sys.exit(65)\n', encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    cmd = f"{sys.executable} runner.py"
    (sl / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd, "junit": "", "setup": ""}), encoding="utf-8")
    run(RUN_TESTS, "--full", cwd=tmp_path)
    assert (sl / "test-output.log").read_text(encoding="utf-8").count("Foo.swift:3:5: error: bad") == 1


def test_green_log_has_no_prepended_error(tmp_path):
    (tmp_path / "runner.py").write_text('print("x.swift:1:1: error: old")\nfor i in range(60):\n    print(f"filler {i}")\nprint("** TEST SUCCEEDED **")\n', encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    cmd = f"{sys.executable} runner.py"
    (sl / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd, "junit": "", "setup": ""}), encoding="utf-8")
    run(RUN_TESTS, "--full", cwd=tmp_path)
    log = (sl / "test-output.log").read_text(encoding="utf-8")
    assert "error: old" not in log.splitlines()[0] and "error: old" not in log
