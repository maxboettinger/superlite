"""run_tests --wait prints each fact once: its stdout JSON leaves out what its stderr lines print (#1085)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS, run
from test_run_tests_tested_818 import RUN_TESTS, TAIL, stack, tree_run

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402


def test_wait_shown_leaves_out_the_stderr_keys():
    data = {"passed": 3, "failed": 1, "skipped": 0, "mode": "task", "files": {"t.py": [3, 1]},
            "failures": ["t.py::test_x: boom"], "error": "", "output": "/r/.superlite/s.output.log",
            "warning": "w", "tree": ".superlite/trees/T1", "lacks": ["a.py"], "drift": ["b.py"],
            "result_bundles": ["/r/x.xcresult"], "task": "T1"}
    assert run_tests.wait_shown(data, "/r/.superlite/s.json") == {
        "passed": 3, "failed": 1, "skipped": 0, "mode": "task", "failures": ["t.py::test_x: boom"],
        "error": "", "task": "T1", "summary": "/r/.superlite/s.json"}
    assert run_tests.WAIT_STDERR_KEYS == ("output", "warning", "tree", "lacks", "drift", "result_bundles")
    assert "output" in data and "files" in data


def test_wait_prints_tree_and_output_once(tmp_path):
    plan = stack(tmp_path)
    cp = tree_run(tmp_path, plan, "--background")
    assert cp.returncode == 0, cp.both
    w = run(RUN_TESTS, "--wait", "--timeout", "120", cwd=tmp_path)
    assert w.returncode == 0, w.both
    shown = json.loads(w.out)
    assert [k for k in run_tests.WAIT_STDERR_KEYS if k in shown] == []
    disk = json.loads(Path(shown["summary"]).read_text(encoding="utf-8"))
    assert disk["tree"] == ".superlite/trees/T1" and disk["lacks"] == ["src/b.txt"]
    lines = w.err.strip().splitlines()
    assert lines[-2] == f"output: {disk['output']}"
    assert lines[-1].endswith(TAIL)
    assert w.both.count(disk["output"]) == 1
