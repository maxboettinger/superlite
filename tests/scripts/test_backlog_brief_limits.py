import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

def test_triage_brief_states_every_question_limit_it_checks():
    t = bb.triage_brief([{"number": 1, "title": "t"}], {"repo": "r", "max_batches": 2})
    for s in ("1 to 4 distinct questions per decision", "question at most 300 characters", "header at most 12 characters",
              "2 to 4 options with distinct labels", "option label at most 60 characters", "description at most 200 characters",
              "an over-long header, label or description is cut to its limit", "any other violation rejects the whole proposal"):
        assert s in t, s
