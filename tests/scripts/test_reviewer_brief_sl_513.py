# tests/scripts/test_reviewer_brief_sl_513.py
# #513: a review in a superlite worktree names the worktree's sl for live checks of the tools its tasks add or change.
import sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402

PLAN_TEXT = """# Plan
**Goal:** x.

```mermaid
%% taskgraph
flowchart LR
  T1 --> T2
```

## Package: tools

### T1 resume · Complexity 3 · Est. context 30k
**Owns:** skills/subagent-driven-development/scripts/orchestrator.py, skills/subagent-driven-development/scripts/status.py, tests/scripts/test_status.py

### T2 docs · Complexity 2 · Est. context 30k
**Owns:** docs/tools.md

### T3 probe · Complexity 2 · Est. context 30k
**Owns:** ./skills/subagent-driven-development/probes/probe_run.py
"""

SCRIPTS_REL = Path("skills/subagent-driven-development/scripts")


@pytest.fixture
def world(tmp_path):
    proj = tmp_path / "wt"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    (proj / ".git").write_text("gitdir: elsewhere\n")  # a linked worktree's .git file
    (proj / SCRIPTS_REL).mkdir(parents=True)
    (proj / SCRIPTS_REL / "sl").write_text("#!/usr/bin/env bash\n")
    plan = proj / "plan.md"; plan.write_text(PLAN_TEXT, encoding="utf-8")
    (sd / "progress.md").write_text("- commit T1 abc1234 a\n- commit T2 def5678 b\n- commit T3 0123abc c\n", encoding="utf-8")
    main = tmp_path / "main"; (main / SCRIPTS_REL).mkdir(parents=True)
    return type("W", (), {"proj": proj, "sd": sd, "plan": str(plan), "main": main, "main_sl": str(main / SCRIPTS_REL / "sl")})


def worktree_lines(out):
    return [ln for ln in out.splitlines() if ln.startswith("Worktree sl")]


def test_brief_names_worktree_sl_for_the_tools_the_tasks_change(world):
    out = io.review_brief(world.sd, world.plan, ["T1"], world.main_sl, str(world.main))
    lines = out.splitlines()
    wt_sl = str(world.proj.resolve() / SCRIPTS_REL / "sl")
    assert worktree_lines(out) == [
        f"Worktree sl (live checks of the tools these tasks add or change: orchestrator, status; type it literally): {wt_sl}",
    ]
    i = lines.index(f"sl (type it literally in every command): {world.main_sl}")
    assert lines[i + 1] == worktree_lines(out)[0]
    assert lines[i + 2] == "Every other command (task, incident, run_tests, commit_task) stays on the sl above: it holds the run's state."
    # run bookkeeping stays on the main checkout's sl
    assert f"Spec slice: `{world.main_sl} task T1 --plan {Path(world.plan).resolve()}`" in lines


def test_probe_tools_count_and_dot_slash_owns_are_read(world):
    out = io.review_brief(world.sd, world.plan, ["T1", "T3"], world.main_sl, str(world.main))
    assert worktree_lines(out)[0].startswith(
        "Worktree sl (live checks of the tools these tasks add or change: orchestrator, status, probe_run; type it literally): ")


def test_no_line_when_the_tasks_change_no_tool(world):
    out = io.review_brief(world.sd, world.plan, ["T2"], world.main_sl, str(world.main))
    assert worktree_lines(out) == []
    assert "Every other command" not in out


def test_no_line_when_the_review_runs_in_the_superlite_checkout_itself(world):
    sl = str(world.proj / SCRIPTS_REL / "sl")
    out = io.review_brief(world.sd, world.plan, ["T1"], sl, str(world.proj))
    assert worktree_lines(out) == []


def test_no_line_when_root_holds_no_sl_launcher(world):
    (world.proj / SCRIPTS_REL / "sl").unlink()
    out = io.review_brief(world.sd, world.plan, ["T1"], world.main_sl, str(world.main))
    assert worktree_lines(out) == []


def test_worktree_sl_helper_is_pure_over_root_and_files(world):
    files = ["skills/subagent-driven-development/scripts/orchestrator.py", "README.md",
             "skills/subagent-driven-development/scripts/orchestrator.py"]
    assert io.worktree_sl(world.proj, world.main, files) == (
        str(world.proj.resolve() / SCRIPTS_REL / "sl"), ["orchestrator"])
    assert io.worktree_sl(world.proj, world.main, ["README.md"]) is None
    assert io.worktree_sl(world.proj, world.proj, files) is None
