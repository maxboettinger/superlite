import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

TAIL = " [cut: sl backlog ship B1 notes prints the full text]"
CTX = {"sl": "/p/sl", "backlog_md": "/p/backlog.md", "repo": "o/r", "approved": {"by": "AskUserQuestion", "time": "T0"}}


def test_cut_note_examples():
    assert bb.cut_note("short", "B1") == "short"
    assert bb.cut_note("x" * 150 + ". " + "y" * 100, "B1", 200) == "x" * 150 + "." + TAIL
    assert bb.cut_note("word " * 60, "B1", 200) == ("word " * 40).rstrip() + TAIL
    assert bb.cut_note("y" * 500, "B1") == "y" * 400 + TAIL


def test_summary_kinds():
    assert bb.summary({"id": "B2", "issues": [7], "no_change": "duplicate of #3"}, "") == "B2 no-change: #7\nPR: -\nVersion: -\nNo change: duplicate of #3\n"
    s = bb.summary({"id": "B1", "issues": [5], "pr": 9, "version": "1.0", "kind": "design"}, "Unverified: app check (#5)\n- unverified: suite\n")
    assert s == "B1 shipped: #5\nPR: #9\nVersion: 1.0\nKind: design, awaits plan approval\nUNVERIFIED: app check (#5)\nUNVERIFIED: suite\n"
    many = bb.summary({"id": "B1", "issues": [5]}, "\n".join(f"n{i}" for i in range(9))).splitlines()
    assert many[-1] == "+3 more note lines: sl backlog ship B1 notes prints them"


def test_lead_brief_end_states_acceptance_and_tracker():
    t = bb.lead_brief({"id": "B1", "topic": "t", "issues": [1], "files": ["a.py"]}, CTX)
    assert "Status: DONE no-change: <reason>" in t and "Ship without <step>?" in t
    assert "Tracker: change no issue state yourself" in t and "comment with evidence" in t
    assert "`Unverified: <step> (#N)`" in t and "`Kind: design`" in t
    j = bb.lead_brief({"id": "B1", "topic": "t", "issues": ["PIX-1"], "files": ["a.py"]}, CTX)
    assert "write no Jira change yourself" not in j and "main moves the issues" in j
