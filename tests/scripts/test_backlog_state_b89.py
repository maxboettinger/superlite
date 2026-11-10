import sys
import pytest
from backlog_fixtures import Q, batch as b
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402


def data(*batches, **kw):
    return {**bs.default(), "repo": "o/r", "batches": list(batches), **kw}


def test_skip_parked_keeps_the_rest():
    d = data(b("B2", ["b.py"], "parked", worktree="/w/b2", issues=[2, 5]))
    assert bs.skip_issue(d, 2) == "skipped #2 (B2 keeps #5)"
    assert d["batches"][0]["state"] == "parked" and d["batches"][0]["issues"] == [5] and 2 in d["skipped"]


def test_skip_parked_last_issue_drops_it():
    d = data(b("B2", ["b.py"], "parked", worktree="/w/b2", issues=[5]), b("B3", ["c.py"], depends=["B2"]))
    assert bs.skip_issue(d, 5) == "skipped #5 (B2 dropped; its worktree /w/b2 stays)"
    assert [x["id"] for x in d["batches"]] == ["B3"] and d["batches"][0]["depends"] == []


def test_skip_parked_without_worktree_unchanged():
    d = data(b("B2", ["b.py"], "parked", issues=[5]))
    assert bs.skip_issue(d, 5) == "skipped #5 (B2 dropped)"


def test_skip_running_and_needs_decision_refused():
    d = data(b("B1", ["a.py"], "running"), b("B2", ["b.py"], "needs_decision"))
    for n, msg in ((1, "#1 is in B1, which is running"), (2, "#2 is in B2, which is needs_decision")):
        with pytest.raises(ValueError, match=msg):
            bs.skip_issue(d, n)


def test_read_note_cleans(tmp_path):
    p = tmp_path / "n.md"
    p.write_bytes(b"Use uv.\r\nNo emojis.\x07  \n\n")
    assert bs.read_note(str(p)) == "Use uv.\nNo emojis."
    p.write_bytes(b"\xef\xbb\xbfUse uv.\r\nNo emojis.\x07  \n\n")
    assert bs.read_note(str(p)) == "Use uv.\nNo emojis."
    p.write_bytes(b"a\n\tx")
    assert bs.read_note(str(p)) == "a\n\tx"


def test_read_note_errors(tmp_path):
    p = tmp_path / "n.md"
    with pytest.raises(ValueError, match="^--note .* unreadable: "):
        bs.read_note(str(p))
    p.write_bytes(b"\xff\xfe\xfa")
    with pytest.raises(ValueError, match="^--note .* unreadable: "):
        bs.read_note(str(p))
    p.write_text("x" * 2001)
    with pytest.raises(ValueError, match="2001 characters, at most 2000") as e:
        bs.read_note(str(p))
    assert str(e.value).startswith(f"--note {p}: ")
    p.write_text("x" * 2000)
    assert bs.read_note(str(p)) == "x" * 2000


def test_set_note_stores_and_clears():
    d = data()
    assert bs.set_note(d, "Use uv.\nNo emojis.", "/m/rules.md", "2026-11-10T22:00:00Z") == \
        "note: stored from /m/rules.md (2 lines); every lead brief from now on carries it"
    assert d["note"] == {"text": "Use uv.\nNo emojis.", "file": "/m/rules.md", "time": "2026-11-10T22:00:00Z"}
    assert "(1 line)" in bs.set_note(d, "one", "/m/o.md", "T")
    assert bs.set_note(d, "", "/m/empty.md", "T") == "note: cleared; lead briefs carry no note"
    assert "note" not in d
    assert bs.set_note(d, "", "/m/empty.md", "T") == "note: cleared; lead briefs carry no note"


def test_status_shows_note():
    note = {"text": "a\nb", "file": "/m/rules.md", "time": "T"}
    line = ("note: 2 lines from /m/rules.md (T) go into every lead brief "
            "(sl backlog start --note FILE replaces it, an empty file clears it)")
    assert bs.note_line({"note": note}) == line
    assert bs.note_line({}) is None and bs.note_line({"note": {"text": 5}}) is None
    assert bs.status_lines(data(note=note))[-1] == line
    d = data(b("B1", ["a.py"], "needs_decision", questions=1, decisions=[Q]), note=note)
    lines = bs.status_lines(d)
    if any(x.startswith("questions:") for x in lines):
        assert lines[-2] == line and lines[-1].startswith("questions:")
    else:
        assert lines[-1] == line


def test_skip_issue_signature_takes_int_or_str():
    import inspect
    ann = inspect.signature(bs.skip_issue).parameters["n"].annotation
    assert "str" in str(ann) and "int" in str(ann)
