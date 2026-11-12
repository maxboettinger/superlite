"""#626: the lead brief says a lead never stamps a red eval case its batch does not touch."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

LCTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "b.md"}
RULE = ("Evals layer red on a case your batch's files do not touch: never stamp it yourself (no `test_layers.py stamp`); "
        "write .superlite/question.json naming the case and its failing graders (options: main stamps it by ruling, "
        "or the batch waits for the case's fix), then end your turn with Status: NEEDS_DECISION.")


def test_lead_brief_never_stamps_a_red_eval_case_626():
    lines = bb.lead_brief({"id": "B1", "issues": [7]}, LCTX).splitlines()
    assert RULE in lines
    assert lines[lines.index(RULE) - 1].startswith("Escalate a new major decision:")
