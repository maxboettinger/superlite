"""#566: lint warns when no test command resolves and a task names no **Tests:** cmd=."""
from __future__ import annotations

import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402

TAIL = ('so their sl run_tests --task stops with "no test command found": run /superlite:setup (it proposes the '
        "project's test command and writes .superlite/test-cmd.json) or name each task's command: **Tests:** fast cmd=<command>")


@pytest.fixture(autouse=True)
def no_user_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(tmp_path / "no-user-file.json"))


def task(n, owns, tests="fast", extra=()):
    return [f"### T{n} t{n} · Complexity 1", f"**Owns:** {owns}", f"**Tests:** {tests}", "**Components:** 1",
            "**LOC owned:** 20", *extra, ""]


def project(tmp_path, tasks, marker=None):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    if marker:
        (tmp_path / marker[0]).write_text(marker[1], encoding="utf-8")
    nodes = [f"  T{i + 1}[t]" for i in range(len(tasks))]
    p = tmp_path / "plan.md"
    p.write_text("\n".join(["# Plan", "**Goal:** test.", "", "```mermaid", "flowchart LR", *nodes, "  %% taskgraph", "```", "",
                            *[ln for t in tasks for ln in t]]), encoding="utf-8")
    return p


def lines_of(p):
    plan = plan_tools.Plan.load(str(p))
    issues, warns = plan_tools.lint_plan(plan, plan_tools.build_parser().parse_args(["lint", "--plan", str(p)]))
    return [w for w in warns if "TESTS:" in w], [str(i) for i in issues if str(i).startswith("TESTS:")]


def test_no_command_warns_once_for_tasks_without_cmd(tmp_path):
    p = project(tmp_path, [task(1, "Sources/App/A.swift, Tests/AppTests/ATests.swift"),
                           task(2, "Sources/App/B.swift", tests="fast cmd=Scripts/test.sh"),
                           task(3, "App/C.swift", tests="build"),
                           task(4, "docs/notes.md"),
                           task(5, "Sources/App/D.swift")])
    assert lines_of(p) == (["WARNING: TESTS: no test command resolves for this project; T1, T5 name no **Tests:** cmd=, " + TAIL], [])


def test_no_warning_when_a_command_resolves(tmp_path):
    assert lines_of(project(tmp_path, [task(1, "src/a.go")], marker=("go.mod", "module m\n"))) == ([], [])


def test_no_warning_when_every_task_names_cmd(tmp_path):
    assert lines_of(project(tmp_path, [task(1, "Sources/A.swift", tests="fast cmd=Scripts/test.sh")])) == ([], [])


def test_more_than_five_tasks_are_cut(tmp_path):
    p = project(tmp_path, [task(i, f"Sources/F{i}.swift") for i in range(1, 8)])
    assert lines_of(p)[0] == ["WARNING: TESTS: no test command resolves for this project; T1, T2, T3, T4, T5 +2 more name no **Tests:** cmd=, " + TAIL]


def test_draft_task_skipped_and_no_root(tmp_path):
    p = project(tmp_path, [task(1, "Sources/A.swift", extra=["**Status:** draft"])])
    assert lines_of(p) == ([], [])
    plan = plan_tools.Plan.load(str(p))
    assert plan_tools.no_command_warnings(plan, None) == []
