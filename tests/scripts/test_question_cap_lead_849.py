"""#849: the lead brief and the lead rules cap a lead's questions at 2 rounds of 4, ranked by what the answer saves."""
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
LCTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "b.md"}
BATCH = {"id": "B1", "issues": [7]}


def _lines(ctx):
    return bb.lead_brief(BATCH, ctx).splitlines()


def test_cap_line_text():
    assert bb.QUESTION_CAP.startswith("Question cap: rank your open questions by what the answer saves")
    assert "major and uncertain first, never dropped by the cap" in bb.QUESTION_CAP
    assert "ask at most 2 rounds of 4 (one .superlite/question.json each)" in bb.QUESTION_CAP
    assert "rule the rest as `Ruling:` lines in .superlite/pr-body.md" in bb.QUESTION_CAP
    assert "Max" not in bb.QUESTION_CAP
    assert "where main and the user can veto them" in bb.QUESTION_CAP


def test_cap_line_before_escalate_in_build_brief():
    lines = _lines(LCTX)
    assert lines.count(bb.QUESTION_CAP) == 1
    assert lines[lines.index(bb.QUESTION_CAP) + 1].startswith("Escalate a new major decision:")


def test_cap_line_in_plan_phase():
    lines = _lines({**LCTX, "phase": "plan"})
    assert lines.count(bb.QUESTION_CAP) == 1
    assert lines[lines.index(bb.QUESTION_CAP) + 1].startswith("Escalate a new major decision:")


def test_backlog_md_lead_rule():
    text = (ROOT / "skills/subagent-driven-development/backlog.md").read_text(encoding="utf-8")
    lead = text.split("## Lead")[1].split("## Permissions")[0]
    assert "Rank your open questions by what the answer saves (major and uncertain first: the cap never drops them)" in lead
    assert "ask at most 2 rounds of 4 (a round is one question.json)" in lead
    assert "where main and the user can veto them" in lead
    assert "main and Max" not in lead
