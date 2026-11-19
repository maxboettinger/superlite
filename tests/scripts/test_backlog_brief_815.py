# tests/scripts/test_backlog_brief_815.py
import sys
from pathlib import Path
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

B = {"id": "B1", "topic": "t", "issues": [1], "files": ["a.py"], "version": "1.0", "pr": 5}
CTX = {"sl": "/p/sl", "backlog_md": "/p/backlog.md", "repo": "o/r", "approved": {"by": "AskUserQuestion", "time": "T0"}}


def test_brief_says_lead_never_files_followups():
    assert "one `Follow-up: ...` line per follow-up issue (main files it; never file one yourself, also when the project tracks work in an issue tracker)" in bb.lead_brief(B, CTX)


def test_backlog_md_followup_rule():
    md = (SCRIPTS.parent / "backlog.md").read_text(encoding="utf-8")
    assert "(a follow-up issue; main files it from the full text `sl backlog ship B notes` prints, also in a project with an issue tracker; a lead never files one itself)" in md
