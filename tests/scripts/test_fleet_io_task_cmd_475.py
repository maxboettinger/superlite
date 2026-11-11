"""#475: the fleet task message names a task's `cmd=` in its Verify line."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_io  # noqa: E402


def plan(tmp_path, tasks):
    out = ["# Plan", "**Goal:** test.", "", "Global constraints:", "- small", "", "```mermaid", "flowchart LR", "  T1[a]", "  %% taskgraph", "```", ""]
    for tid, owns, tests in tasks:
        out += [f"### {tid} thing · Complexity 1", f"**Owns:** {owns}", f"**Tests:** {tests}", ""]
    p = tmp_path / "plan.md"
    p.write_text("\n".join(out), encoding="utf-8")
    return p


TAIL = ", then run the printed `wait:` line in the foreground."


def test_cmd_task_verify_line(tmp_path):
    p = plan(tmp_path, [("T1", "src/a.py, tests/hooks/test.sh", "fast cmd=bash tests/hooks/test.sh")])
    msg = fleet_io.task_message(p, ["T1"], "/sl/sl", "/sl")
    assert ("Verify: `/sl/sl run_tests --task T1 --background` (runs its **Tests:** cmd=`bash tests/hooks/test.sh`)" + TAIL) in msg
    assert "run_tests --fast" not in msg


def test_batch_with_cmd_task_gets_line_per_task(tmp_path):
    p = plan(tmp_path, [("T1", "tests/hooks/test.sh", "fast cmd=bash tests/hooks/test.sh"), ("T2", "src/b.py, tests/test_b.py", "fast")])
    msg = fleet_io.task_message(p, ["T1", "T2"], "/sl/sl", "/sl")
    assert "Verify T1: `/sl/sl run_tests --task T1 --background` (runs its **Tests:** cmd=`bash tests/hooks/test.sh`)" in msg
    assert ("Verify T2: `/sl/sl run_tests --fast tests/test_b.py --task T2 --background`" + TAIL) in msg
    assert "\nVerify: " not in msg


def test_no_cmd_lines_unchanged(tmp_path):
    p = plan(tmp_path, [("T1", "src/a.py, tests/test_a.py", "fast"), ("T2", "app/x.swift", "build"), ("T3", "docs/a.md", "fast")])
    assert ("Verify: `/sl/sl run_tests --fast tests/test_a.py --task T1 --background`" + TAIL) in fleet_io.task_message(p, ["T1"], "/sl/sl", "/sl")
    assert ("Verify: `/sl/sl run_tests --full --task T2 --background` (Tests: build, a build check)" + TAIL) in fleet_io.task_message(p, ["T2"], "/sl/sl", "/sl")
    assert "Verify: no test command (no code file in Owns)" in fleet_io.task_message(p, ["T3"], "/sl/sl", "/sl")
