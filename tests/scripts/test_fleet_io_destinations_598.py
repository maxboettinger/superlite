"""#598: a task's Verify line carries the destinations its Steps and Notes name."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_io  # noqa: E402

TAIL = ", then run the printed `wait:` line in the foreground."


def plan(tmp_path, owns, tests, steps="", notes=""):
    out = ["# Plan", "**Goal:** test.", "", "Global constraints:", "- small", "", "```mermaid", "flowchart LR", "  T1[a]", "  %% taskgraph", "```", "",
           "### T1 thing · Complexity 1", f"**Owns:** {owns}", f"**Tests:** {tests}"]
    if steps:
        out.append(f"**Steps:** {steps}")
    if notes:
        out += ["**Notes:**", f"- {notes}"]
    p = tmp_path / "plan.md"
    p.write_text("\n".join(out) + "\n", encoding="utf-8")
    return p


def test_verify_line_carries_named_destinations(tmp_path):
    p = plan(tmp_path, "src/a.py, tests/test_a.py", "fast", steps="Run on -destination 'platform=macOS' and -destination \"platform=iOS Simulator,name=iPhone 16\".")
    msg = fleet_io.task_message(p, ["T1"], "/sl/sl", "/sl")
    assert ("Verify: `/sl/sl run_tests --fast tests/test_a.py --task T1 --destination platform=macOS --destination 'platform=iOS Simulator,name=iPhone 16' --background`" + TAIL) in msg


def test_cmd_task_line_unchanged(tmp_path):
    p = plan(tmp_path, "tests/hooks/test.sh", "fast cmd=bash tests/hooks/test.sh", steps="Run on -destination 'platform=macOS'.")
    msg = fleet_io.task_message(p, ["T1"], "/sl/sl", "/sl")
    assert ("Verify: `/sl/sl run_tests --task T1 --background` (runs its **Tests:** cmd=`bash tests/hooks/test.sh`)" + TAIL) in msg


def test_build_form_and_notes_dedup(tmp_path):
    p = plan(tmp_path, "app/x.swift", "build", notes="use --destination platform=macOS twice: -destination platform=macOS")
    msg = fleet_io.task_message(p, ["T1"], "/sl/sl", "/sl")
    assert "run_tests --full --task T1 --destination platform=macOS --background` (Tests: build" in msg
    assert msg.count("--destination") == 1


def test_named_destinations():
    f = fleet_io.named_destinations
    assert f("Run on -destination 'platform=macOS' and -destination \"platform=iOS Simulator,name=iPhone 16\".") == ["platform=macOS", "platform=iOS Simulator,name=iPhone 16"]
    assert f("run_tests --destination platform=macOS") == ["platform=macOS"]
    assert f("no platform") == []
