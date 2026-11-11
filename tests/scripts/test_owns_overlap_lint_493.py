"""#493: plan lint warns when the plan's Owns share a file with another open superlite run."""
from __future__ import annotations

import sys

from test_owns_overlap_493 import TAIL, add_wt, backlog, repo
from test_plan_tools import SCRIPTS, pt

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402

TWO = ("# P\n**Goal:** t.\n\n```mermaid\nflowchart LR\n  T1[a]\n  T2[b]\n  %% taskgraph\n  T1 --> T2\n```\n\n"
       "### T1 a · Complexity 1 · Est. context 20k\n**Owns:** src/x.py, tests/test_x.py\n**Components:** 1\n"
       "**LOC owned:** 10\n**Tests:** fast\n**Model:** sonnet\n\n"
       "### T2 b · Complexity 1 · Est. context 20k\n**Owns:** src/x.py, docs/d.md\n**Components:** 1\n"
       "**LOC owned:** 10\n**Tests:** fast\n**Model:** sonnet\n")


def my_plan(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine")
    plan = mine / "docs" / "p.md"
    plan.parent.mkdir(parents=True)
    plan.write_text(TWO, encoding="utf-8")
    return main, plan


def overlap(out):
    return [ln for ln in out.splitlines() if "OVERLAP" in ln]


def test_lint_warns_per_run_with_task_ids(tmp_path):
    main, plan = my_plan(tmp_path)
    b9 = add_wt(main, "b9")
    backlog(main, {"id": "B9", "state": "running", "worktree": str(b9), "files": ["src/x.py", "tests/"]})
    other = add_wt(main, "other", owns="docs/*.md")
    assert overlap(pt("lint", "--plan", plan).out) == [
        f"WARNING: OVERLAP: src/x.py (T1, T2), tests/test_x.py (T1) also owned by open run B9 (running) at {b9.as_posix()}" + TAIL,
        f"WARNING: OVERLAP: docs/d.md (T2) also owned by open run superlite/other at {other.as_posix()}" + TAIL]


def test_overlap_is_never_an_issue(tmp_path):
    main, plan = my_plan(tmp_path)
    before = pt("lint", "--plan", plan)
    add_wt(main, "other", owns="src/x.py")
    after = pt("lint", "--plan", plan)
    assert overlap(before.out) == [] and len(overlap(after.out)) == 1
    assert after.returncode == before.returncode
    issues = lambda out: [ln for ln in out.splitlines() if ln.startswith("ISSUE:")]
    assert issues(after.out) == issues(before.out)


def test_cross_run_warnings_direct(tmp_path):
    main, plan = my_plan(tmp_path)
    other = add_wt(main, "other", owns="src/")
    assert plan_tools.cross_run_warnings(plan_tools.Plan.load(str(plan))) == [
        f"WARNING: OVERLAP: src/x.py (T1, T2) also owned by open run superlite/other at {other.as_posix()}" + TAIL]


def test_no_other_run_no_warning(tmp_path):
    _, plan = my_plan(tmp_path)
    assert plan_tools.cross_run_warnings(plan_tools.Plan.load(str(plan))) == []


def test_plan_outside_git_has_no_overlap_line(tmp_path):
    plan = tmp_path / "p.md"
    plan.write_text(TWO, encoding="utf-8")
    assert overlap(pt("lint", "--plan", plan).out) == []
