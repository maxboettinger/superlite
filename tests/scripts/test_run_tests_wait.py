"""run_tests --wait PATH waits on exactly one run; --background prints the wait line."""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from test_plan_tools import ROOT, SCRIPTS, run

RUN_TESTS = SCRIPTS / "run_tests.py"

PASS = '<testsuites><testsuite name="s"><testcase classname="T.a" name="ok" time="0.01"></testcase></testsuite></testsuites>'
FAIL = '<testsuites><testsuite name="s"><testcase classname="T.b" name="bad" time="0.01"><failure message="boom">x</failure></testcase></testsuite></testsuites>'

RUNNER = """import sys, pathlib
n = pathlib.Path("count"); k = int(n.read_text()) if n.exists() else 0; n.write_text(str(k + 1))
src = "pass.xml" if k == 0 else "fail.xml"
pathlib.Path(sys.argv[1]).write_text(open(src).read())
"""


def setup(tmp_path):
    (tmp_path / "pass.xml").write_text(PASS, encoding="utf-8")
    (tmp_path / "fail.xml").write_text(FAIL, encoding="utf-8")
    (tmp_path / "runner.py").write_text(RUNNER, encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir(exist_ok=True)
    cmd = f"{sys.executable} runner.py {{junit}}"
    (sl / "test-cmd.json").write_text(json.dumps({"language": "python", "test": cmd, "test_file": cmd, "junit": "{junit}", "setup": ""}), encoding="utf-8")


def start(tmp_path):
    cp = run(RUN_TESTS, "--full", "--background", cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    lines = cp.out.splitlines()
    return lines, lines[0].split("summary: ", 1)[1]


def test_wait_path_returns_that_run_only(tmp_path):
    setup(tmp_path)
    _, a = start(tmp_path)
    ca = run(RUN_TESTS, "--wait", a, "--timeout", "60", cwd=tmp_path)  # run A finishes first: counter 0 = pass
    _, b = start(tmp_path)
    cb = run(RUN_TESTS, "--wait", b, "--timeout", "60", cwd=tmp_path)
    ca2 = run(RUN_TESTS, "--wait", a, "--timeout", "60", cwd=tmp_path)
    assert ca.returncode == 0 and json.loads(ca.out)["passed"] == 1, ca.both
    assert cb.returncode == 1 and json.loads(cb.out)["failed"] == 1, cb.both
    assert ca2.returncode == 0, ca2.both


def test_background_prints_wait_line(tmp_path):
    setup(tmp_path)
    lines, path = start(tmp_path)
    assert len(lines) == 2
    assert lines[1] == f'wait: bash "$SL" run_tests --wait {path}'
    assert Path(path).is_absolute()


def test_bare_wait_uses_pointer(tmp_path):
    setup(tmp_path)
    start(tmp_path)
    cp = run(RUN_TESTS, "--timeout", "60", "--wait", cwd=tmp_path)
    assert cp.returncode == 0 and json.loads(cp.out)["passed"] == 1, cp.both


def test_wait_missing_path_times_out(tmp_path):
    cp = run(RUN_TESTS, "--wait", "/nope.json", "--timeout", "1", cwd=tmp_path)
    assert cp.returncode == 2 and "timed out" in cp.err


def test_prompts_say_wait_path():
    files = ["implementer", "implementer-haiku", "fixer-sonnet", "fixer-sonnet-high", "fixer-opus", "package-reviewer"]
    paths = [ROOT / "agents" / f"{f}.md" for f in files] + [ROOT / "skills" / "subagent-driven-development" / "fixing.md"]
    for p in paths:
        text = p.read_text(encoding="utf-8")
        assert "--wait" in text, p
        assert not re.search(r"--wait(`|\s*\n)", text), p
