"""#567: the lead brief names .superlite/render/ for UI screenshots, so the review packet lists them."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

CTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md", "titles": {"7": "Seven"}, "summaries": [],
       "approved": {"by": "AskUserQuestion", "time": "t"}}
BUILD = ("Build: superlite:brainstorming (AI orchestrator, no questions), superlite:writing-plans, "
         "superlite:subagent-driven-development with fleet on, the final review (UI screenshots go in .superlite/render/, "
         "its packet lists them), the test layers.")


def test_lead_brief_build_line_names_the_render_folder():
    t = bb.lead_brief({"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "answers": {}}, CTX)
    assert BUILD in t.splitlines()
    assert "the final review, the test layers." not in t
