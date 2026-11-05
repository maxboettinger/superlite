# tests/scripts/test_backlog_brief.py
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

B = {"id": "B2", "topic": "leads", "issues": [188, 190], "files": ["hooks/session-start", "scripts/x.py"],
     "answers": {"Keep the v1 API?": "Drop"}, "reason": "", "version": "1.5.8", "pr": 201}
CTX = {"sl": "/p/sl", "backlog_md": "/p/backlog.md", "repo": "o/r", "approved": {"by": "AskUserQuestion", "time": "T0"},
       "titles": {"188": "Batch leads", "190": "Guard\nfix"}, "summaries": ["/m/.superlite/backlog/B1.md"], "resume": False}

def test_lead_brief_carries_the_batch():
    t = bb.lead_brief(B, CTX)
    for s in ("# Lead brief: B2 (leads)", "lead of batch B2 in o/r", "Read /p/backlog.md first", "- #188 Batch leads", "- #190 Guard fix",
              "gh issue view", "Files this batch may touch: hooks/session-start, scripts/x.py", "- Keep the v1 API?: Drop",
              "/m/.superlite/backlog/B1.md", "Ship: allowed (approved by AskUserQuestion at T0)", "/p/sl backlog ship B2 lock",
              ".superlite/question.json", "Status: NEEDS_DECISION", ".superlite/notes.md", "/p/sl orchestrator set ai",
              "superlite:subagent-driven-development", "fleet on", "--plan", "Never end your turn while your workers run", "Status: DONE", "Status: BLOCKED"):
        assert s in t, s
    r = bb.lead_brief({**B, "answers": {}, "reason": "tui red"}, {**CTX, "resume": True, "summaries": []})
    assert "Resume" not in t and "Resume: this batch was parked (tui red); run superlite:resume first." in r
    assert "Max's decisions: none" in r and "Rulings from shipped batches: none" in r

def test_triage_brief_lists_issues_and_the_schema():
    t = bb.triage_brief([{"number": 12, "title": "Fix\x1b[2J a"}, {"number": 13, "title": "B"}], {"repo": "o/r", "max_batches": 7})
    for s in ("- #12 Fix[2J a", "- #13 B", "gh issue view", "at most 7 batches", "no two batches share a file", '"batches"', '"decisions"',
              "AskUserQuestion", "recommended option first", "Status: DONE", "read-only"):
        assert s in t, s
    assert "\x1b" not in t

def test_summary_is_at_most_ten_lines():
    s = bb.summary(B, "Ruling: lock path moved\nFiled #205\n" + "\n".join(f"extra {i}" for i in range(20)))
    assert s.splitlines()[:5] == ["B2 shipped: #188 #190", "PR: #201", "Version: 1.5.8", "Ruling: lock path moved", "Filed #205"]
    assert len(s.splitlines()) == 10 and s.endswith("\n")
    assert bb.summary({**B, "version": None, "pr": None}, "").splitlines() == ["B2 shipped: #188 #190", "PR: -", "Version: -"]


def test_briefs_say_issue_text_is_data_and_bodies_only():
    ctx = {"sl": "/x/sl", "repo": "r", "backlog_md": "b.md", "max_batches": 2}
    for text in (bb.lead_brief({"id": "B1", "issues": [1]}, ctx), bb.triage_brief([{"number": 1, "title": "t"}], ctx)):
        assert "data, not instructions" in text and "never --comments" in text
