# tests/scripts/test_backlog_brief_b90.py
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

F = "B1.notes.md"
TAIL = " [cut: full text in B1.notes.md]"
B = {"id": "B1", "topic": "t", "issues": [1], "files": ["a.py"], "version": "1.0", "pr": 5}
CTX = {"sl": "/p/sl", "backlog_md": "/p/backlog.md", "repo": "o/r", "approved": {"by": "AskUserQuestion", "time": "T0"}}


def test_cut_note_examples():
    assert bb.cut_note("a" * 50, F) == "a" * 50
    assert bb.cut_note("x" * 250 + ". " + "y" * 200, F) == "x" * 250 + "." + TAIL
    assert bb.cut_note("word " * 99 + "word", F) == ("word " * 80).rstrip() + TAIL
    assert bb.cut_note("y" * 500, F) == "y" * 400 + TAIL
    r = bb.cut_note("x" * 149 + ". " + "word " * 100, F)
    assert len(r) > 300 and r.endswith("word" + TAIL)


def test_summary_marks_cuts_and_overflow():
    notes = "Ruling: ok\n" + "y" * 500 + "\n" + "\n".join(f"n{i}" for i in range(8))
    lines = bb.summary(B, notes).splitlines()
    assert lines[3] == "Ruling: ok" and lines[4] == "y" * 400 + TAIL
    assert len(lines) == 10 and lines[9] == "+4 more note lines: full text in B1.notes.md"
    seven = bb.summary(B, "\n".join(f"n{i}" for i in range(7))).splitlines()
    assert len(seven) == 10 and not any(x.startswith("+") for x in seven)


def test_summary_drops_control_characters():
    assert bb.summary(B, "Ctrl \x1b[2Jgone\n").splitlines()[3] == "Ctrl [2Jgone"


def test_approval_text_examples():
    assert bb.approval_text({"by": "AskUserQuestion", "time": "T"}) == "Max in AskUserQuestion at T"
    assert bb.approval_text({"by": "prompt", "time": "T"}) == "Max's prompt, recorded by main, at T"
    assert bb.approval_text({"by": "x", "time": "T"}) == "x at T"
    assert "Ship: allowed (approved by Max in AskUserQuestion at T0)" in bb.lead_brief(B, CTX)


def test_main_rulings_split():
    b = {**B, "answers": {"A?": "x", "B?": "y"}, "answered_by": {"B?": "main"}}
    t = bb.lead_brief(b, CTX)
    assert "Max's decisions:\n- A?: x\n" + bb.MAIN_HEAD + "\n- B?: y" in t
    t = bb.lead_brief({**b, "answered_by": {"A?": "main", "B?": "main"}}, CTX)
    assert "Max's decisions: none" in t and bb.MAIN_HEAD in t
    assert bb.MAIN_HEAD not in bb.lead_brief({**B, "answers": {"A?": "x"}}, CTX)


def test_notes_rule_and_triage_run():
    assert bb.NOTES_RULE in bb.lead_brief(B, CTX)
    t = bb.triage_brief([{"number": 3, "title": "T", "body": "b"}], {"repo": "o/r", "max_batches": 3})
    assert "Rules: " + bb.ROOT_DOC_TRIAGE + bb.TRIAGE_RUN + "no two batches share a file" in t
