"""A planning lead's first message names `DONE planned: <plan path>`; other leads keep the worker contract (#716)."""
import sys

import pytest

from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import fleet_report as fr  # noqa: E402

CTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md", "titles": {"7": "Seven"}, "summaries": [],
       "approved": {"by": "AskUserQuestion", "time": "t"}, "text": "default"}
ONE = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "decisions": []}
HEAD = "End your reply with the line `Status: <DONE planned: <plan path>|DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED>`"
JSON = "`, then one fenced json block"


def brief(tmp_path, phase=None, text="default"):
    p = tmp_path / "lead.md"
    p.write_text(bb.lead_brief(ONE, {**CTX, "text": text, "phase": phase, "plan": "docs/plans/p.md"}), encoding="utf-8")
    return str(p)


def test_planned_contract_names_done_planned():
    assert fr.PLANNED.startswith(HEAD)
    assert fr.PLANNED.split(JSON, 1)[1] == fr.WORK.split(JSON, 1)[1]
    assert fr.PLANNED != fr.WORK and "\n" not in fr.PLANNED


def test_marker_is_the_plan_phase_end_line():
    assert fr.PLANNED_END == "End: Status: DONE planned:"
    assert bb.PLAN_END.startswith(fr.PLANNED_END)


@pytest.mark.parametrize("text", ["default", "lean"])
def test_plan_phase_lead_gets_planned(tmp_path, text):
    p = brief(tmp_path, "plan", text)
    assert fr.brief_message("lead", p) == f"Read {p} and do what it says. {fr.PLANNED}"


@pytest.mark.parametrize("phase", [None, "build"])
def test_single_and_build_lead_keep_work(tmp_path, phase):
    p = brief(tmp_path, phase)
    assert fr.brief_message("lead", p) == f"Read {p} and do what it says. {fr.WORK}"


def test_marker_counts_only_at_line_start(tmp_path):
    p = tmp_path / "lead.md"
    p.write_text("Note: a planning lead ends End: Status: DONE planned: x\n    End: Status: DONE planned: y\n"
                 "End: Status: DONE once merge printed shipped\n", encoding="utf-8")
    assert fr.brief_message("lead", str(p)).endswith(fr.WORK)


def test_unreadable_brief_keeps_work(tmp_path):
    assert fr.brief_message("lead", str(tmp_path / "gone.md")) == f"Read {tmp_path / 'gone.md'} and do what it says. {fr.WORK}"
    assert fr.brief_message("lead", str(tmp_path)).endswith(fr.WORK)


@pytest.mark.parametrize("role", ["implementer", "fixer", "package-reviewer", "research"])
def test_other_roles_keep_work_on_a_plan_brief(tmp_path, role):
    p = brief(tmp_path, "plan")
    assert fr.brief_message(role, p) == f"Read {p} and do what it says. {fr.WORK}"


def test_final_reviewer_unchanged(tmp_path):
    p = brief(tmp_path, "plan")
    assert fr.brief_message("final-reviewer", p) == f"Review the packet {p} as your instructions say. {fr.REVIEW}"
