# tests/scripts/test_backlog_brief_602.py: #602 brief lines for append-only files
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

B = {"id": "B2", "topic": "leads", "issues": [188], "files": ["hooks/session-start", "scripts/x.py"],
     "answers": {}, "reason": "", "version": "1.5.8", "pr": 201}
CTX = {"sl": "/p/sl", "backlog_md": "/p/backlog.md", "repo": "o/r", "approved": {"by": "AskUserQuestion", "time": "T0"},
       "titles": {"188": "Batch leads"}, "summaries": [], "resume": False}
APPEND = ("Append-only files (add lines; never reorder, rewrite or delete existing ones; another batch may append to them too: "
          "keep both sides when the ship rebase conflicts on one): ")


def test_lead_brief_names_append_only_files():
    t = bb.lead_brief({**B, "files": ["a.md", "x.py"], "append_only": ["a.md"]}, CTX)
    assert ("Files this batch may touch: a.md, x.py. Another lead may own any other file.\n" + APPEND + "a.md.") in t
    assert bb.APPEND_LINE == APPEND


def test_lead_brief_without_append_only_is_unchanged():
    t = bb.lead_brief(B, CTX)
    assert "Append-only files" not in t and "(append-only)" not in t


def test_owned_files_mark_append_only():
    t = bb.lead_brief(B, {**CTX, "owned": [{"id": "B9", "state": "running", "files": ["a.md", "z.py"], "append_only": ["a.md"]}]})
    assert "Files other open batches own: B9 (running) a.md (append-only), z.py." in t


def test_triage_rules_name_append_only():
    t = bb.triage_brief([{"number": 1, "title": "t", "body": ""}], {"repo": "o/r", "max_batches": 7})
    assert "no two batches share a file unless one depends on the other or both list it in append_only (" + bb.APPEND_TRIAGE + ")" in t
    assert '"files": ["<path>"], "append_only": [], "depends": []' in t


def test_triage_open_line_marks_append_only():
    t = bb.triage_brief([{"number": 1, "title": "t", "body": ""}], {"repo": "o/r", "max_batches": 7,
                        "open": [{"id": "B9", "state": "running", "files": ["a.md"], "append_only": ["a.md"]}]})
    assert "B9 running: a.md (append-only). " + bb.OPEN_TAIL + " " + bb.OPEN_APPEND in t


def test_triage_open_line_without_append_only_is_unchanged():
    t = bb.triage_brief([{"number": 1, "title": "t", "body": ""}], {"repo": "o/r", "max_batches": 7,
                        "open": [{"id": "B9", "state": "running", "files": ["a.md"]}]})
    assert "B9 running: a.md. " + bb.OPEN_TAIL in t and bb.OPEN_APPEND not in t
