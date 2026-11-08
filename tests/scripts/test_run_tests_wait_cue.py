"""#286: run_tests --background prints a do-not-end cue, then the wait line last."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS
from test_run_tests_wait import RUN_TESTS, run, setup, start

sys.path.insert(0, str(SCRIPTS))

import run_tests  # noqa: E402

CUE = ("next: tests still running; run the wait line below now, in the foreground "
       "(never as a background command), and do not end your turn until it reports.")


def test_cue_text():
    assert run_tests.WAIT_CUE == CUE


def test_background_prints_cue_then_wait_last(tmp_path):
    setup(tmp_path)
    lines, path = start(tmp_path)
    assert lines == [f"summary: {path}", CUE, run_tests.wait_line(path)]
    assert lines[-1].startswith("wait: ") and lines[-1].endswith(f"run_tests --wait {path}")
    done = run(RUN_TESTS, "--wait", path, "--timeout", "60", cwd=tmp_path)
    assert done.returncode == 0, done.both


def test_docstring_names_the_cue():
    doc = " ".join(run_tests.__doc__.split())
    assert "a `next:` line (run the wait line now, in the foreground; do not end your turn until it reports) and, last, the `wait:` line" in doc
