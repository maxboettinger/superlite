import sys

import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

TCTX = {"repo": "o/r", "max_batches": 3}
LCTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md", "titles": {"7": "Seven"}, "summaries": [],
        "approved": {"by": "AskUserQuestion", "time": "t"}, "text": "default"}
ONE = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "decisions": []}
TRIAGE = ("An issue that links a spec, plan or design doc (a repo path, or a URL to a file of this repository, in its body or "
          "comments): read that file first; never propose a decision it already rules, and plan the batch to what it rules. ")
LEAD = ("An issue that links a spec, plan or design doc (a path or URL in its body or comments): read it before you plan; "
        "follow what it rules and never ask a question or write a ruling against it.")


def test_spec_texts_exact():
    assert bb.SPEC_TRIAGE == TRIAGE and bb.SPEC_LEAD == LEAD


def test_triage_rules_open_with_spec_rule():
    lines = bb.triage_brief([{"number": 5, "title": "A", "body": "see docs/specs/a.md"}], TCTX).splitlines()
    rules = [ln for ln in lines if ln.startswith("Rules: ")]
    assert len(rules) == 1 and rules[0].startswith("Rules: " + TRIAGE + bb.ROOT_DOC_TRIAGE)


def test_triage_spec_rule_once_jira_pinned():
    t = bb.triage_brief([{"number": "PIX-1", "title": "A", "body": "b"}], {**TCTX, "pinned": {"head": "abc", "version": "1.0"}})
    assert t.count(TRIAGE) == 1 and t.index("Pinned:") < t.index(TRIAGE)


@pytest.mark.parametrize("extra", [{}, {"text": "lean"}, {"phase": "plan"}, {"phase": "build", "plan": "docs/plans/p.md"}])
def test_lead_spec_line_after_data_rule(extra):
    lines = bb.lead_brief(ONE, {**LCTX, **extra}).splitlines()
    i = lines.index(bb.DATA_RULE)
    assert lines[i + 1] == LEAD and lines.count(LEAD) == 1
