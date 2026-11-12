"""#567: the lead brief names .superlite/render/ for UI screenshots, so the review packet lists them."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

CTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md", "titles": {"7": "Seven"}, "summaries": [],
       "approved": {"by": "AskUserQuestion", "time": "t"}}
BUILD = ("Build: superlite:brainstorming (AI orchestrator, no questions), superlite:writing-plans, "
         "superlite:subagent-driven-development with fleet on, the final review (UI screenshots go in .superlite/render/, "
         "its packet lists them), "
         "the test layers. Builds: the verdict is `sl run_tests` (the project's test command; a project with `.maxapp` runs "
         "`maxapp test`, which a build pool may place on another Mac, and a full run whose tree a green maxapp test stamp "
         "covers returns that result without a run); task trees build in <tree>/.build/DerivedData and any build of your "
         "own goes under .build/ of the worktree, never -derivedDataPath outside the worktree (your session scratchpad "
         "included; backlog cleanup removes scratchpad build folders when the worktree goes); a product, simulator or "
         "device build stays on this machine and runs only when an issue's acceptance asks for a running-app check; "
         "copy this sentence into every worker brief.")


def test_lead_brief_build_line_names_the_render_folder():
    t = bb.lead_brief({"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "answers": {}}, CTX)
    assert BUILD in t.splitlines()
    assert "the final review, the test layers." not in t


def test_lead_brief_names_build_rule():
    t = bb.lead_brief({"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "answers": {}}, CTX)
    assert "never -derivedDataPath outside the worktree (your session scratchpad included" in t
    assert "<tree>/.build/DerivedData" in t
