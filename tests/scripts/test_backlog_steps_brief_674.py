# tests/scripts/test_backlog_steps_brief_674.py
import sys

from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

CTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md", "titles": {"12": "Twelve"}, "summaries": [],
       "approved": {"by": "AskUserQuestion", "time": "t"}}
ONE = {"id": "B1", "topic": "t", "issues": [12], "files": ["a.py"], "decisions": []}
STEPS = [{"issues": [12], "runs": "main", "command": "git lfs install", "why": "LFS hooks"},
         {"runs": "user", "command": "gh auth login", "question": "Who signs in?"}]


def test_lead_brief_rule_always():
    t = bb.lead_brief(ONE, {**CTX, "text": "default"})
    assert t.count(bb.STEPS_RULE) == 1 and bb.STEPS_HEAD not in t
    assert "main runs this: <command>" in bb.STEPS_RULE


def test_lead_brief_lists_steps():
    lines = bb.lead_brief({**ONE, "main_steps": STEPS}, {**CTX, "text": "default"}).splitlines()
    i = lines.index(bb.STEPS_RULE)
    assert lines[i + 1:i + 4] == [bb.STEPS_HEAD, "- main runs this: git lfs install (#12: LFS hooks)",
                                  "- Max runs this: gh auth login (decision: Who signs in?)"]


def test_lead_brief_steps_control_chars():
    t = bb.lead_brief({**ONE, "main_steps": [{"issues": [12], "runs": "main", "command": "x", "why": "a\x07b"}]}, CTX)
    assert "(#12: ab)" in t and "\x07" not in t


def test_lean_brief_has_steps():
    t = bb.lead_brief({**ONE, "main_steps": STEPS}, {**CTX, "text": "lean"})
    assert bb.LEAN_BUILD.format(sl="/x/sl")[:20] in t
    assert t.count(bb.STEPS_RULE) == 1 and "- main runs this: git lfs install (#12: LFS hooks)" in t


def test_triage_brief_names_main_steps():
    t = bb.triage_brief([{"number": 1, "title": "t"}], {"repo": "r", "max_batches": 2})
    assert bb.TRIAGE_RUN in t
    for s in ("main_steps", '"runs"', '"command"', '"files": ["<path>"], "append_only": [], "depends": [], "main_steps": [], "decisions"'):
        assert s in t, s


def test_steps_block_follows_attribution():
    t = bb.lead_brief({**ONE, "main_steps": STEPS, "answers": {"Q?": "x"}, "answered_by": {"Q?": "main"}}, {**CTX, "note": "n"})
    assert bb.MAIN_HEAD + "\n- Q?: x\n" + bb.ATTRIBUTION + "\n" + bb.STEPS_RULE + "\n" + bb.STEPS_HEAD + "\n" in t
    assert t.index(bb.STEPS_HEAD) < t.index(bb.NOTE_HEAD)
