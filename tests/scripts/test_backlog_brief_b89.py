import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

B = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "answers": {}}
CTX = {"sl": "/x/sl", "backlog_md": "/x/backlog.md", "repo": "o/r", "approved": None, "titles": {"7": "Seven"}, "summaries": []}
OWNED = [{"id": "B1", "state": "running", "files": ["a.py"]}, {"id": "B2", "state": "planned", "files": ["b.py", "c.py"]},
         {"id": "B3", "state": "running", "files": ["d.py"]}]


def test_note_lines():
    t = bb.lead_brief(B, {**CTX, "note": "Use uv.\nNo emojis."}).splitlines()
    i = t.index(bb.NOTE_HEAD)
    assert t[i + 1:i + 3] == ["    Use uv.", "    No emojis."] and t[i + 3].startswith("Rulings from shipped batches")
    assert bb.NOTE_HEAD not in bb.lead_brief(B, {**CTX, "note": ""})


def test_standing_is_the_default(monkeypatch):
    monkeypatch.setattr(bb, "STANDING", {"note": "x"})
    assert "    x" in bb.lead_brief(B, CTX).splitlines()
    assert bb.NOTE_HEAD not in bb.lead_brief(B, {**CTX, "note": ""})


def test_owned_line():
    t = bb.lead_brief(B, {**CTX, "owned": OWNED}).splitlines()
    i = next(k for k, x in enumerate(t) if x.startswith("Files this batch may touch"))
    assert t[i + 1] == "Files other open batches own: B2 (planned) b.py, c.py; B3 (running) d.py."
    t = bb.lead_brief(B, {**CTX, "owned": OWNED[:1]})
    assert "Files other open batches own: none.\n" in t
    assert "Files other open batches own" not in bb.lead_brief(B, CTX)


def test_root_doc_rule_always():
    t = bb.lead_brief(B, CTX).splitlines()
    i = next(k for k, x in enumerate(t) if x.startswith("Files this batch may touch"))
    assert t[i + 1] == bb.ROOT_DOC_RULE
    t = bb.lead_brief(B, {**CTX, "owned": OWNED}).splitlines()
    assert t[i + 2] == bb.ROOT_DOC_RULE


def test_note_control_characters():
    assert "    ab" in bb.lead_brief(B, {**CTX, "note": "a\x07b"}).splitlines()


def test_triage_open_line():
    op = [{"id": "B89", "state": "running", "files": ["a.py", "b.py"]}, {"id": "B90", "state": "planned", "files": ["c.py"]}]
    iss = [{"number": 3, "title": "T", "body": "b"}]
    t = bb.triage_brief(iss, {"repo": "o/r", "max_batches": 3, "open": op})
    assert bb.OPEN_HEAD + "B89 running: a.py, b.py; B90 planned: c.py. " + bb.OPEN_TAIL in t.splitlines()
    for c in ({"open": []}, {}):
        assert bb.OPEN_HEAD not in bb.triage_brief(iss, {"repo": "o/r", "max_batches": 3, **c})


def test_triage_root_doc_rule():
    t = bb.triage_brief([{"number": 3, "title": "T", "body": "b"}], {"repo": "o/r", "max_batches": 3})
    assert "Rules: " + bb.ROOT_DOC_TRIAGE + bb.TRIAGE_RUN + "no two batches share a file" in t
