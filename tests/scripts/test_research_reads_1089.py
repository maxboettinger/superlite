"""Standing-note copies: a missing path is text; the lead brief lists the outside paths research may read (#1089)."""
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
from test_backlog_note_refs_1067 import w, B, CTX  # noqa: F401,E402
import backlog_brief as bb  # noqa: E402
import backlog_run  # noqa: E402
import findings  # noqa: E402
import fleet  # noqa: E402


def test_missing_path_is_neither_copied_nor_named(w):
    note, lines = bb.note_refs("Deploy to ~/app and ~/app/data.db on the host.", w.wt)
    assert note == "Deploy to ~/app and ~/app/data.db on the host." and lines == []


def test_copied_and_capped_paths_are_listed_for_research(w, monkeypatch):
    monkeypatch.setattr(bb, "REF_CAP", (10, 5000))
    text = f"Read {w.other}/docs/spec.md and {w.other}/README.md; all of {w.tmp}; write {w.other}/new.md."
    _, lines = bb.note_refs(text, w.wt)
    assert lines == [bb.REF_COPIED.format(n=1, ref=w.ref),
                     bb.REF_SKIPPED.format(items=f"{w.other}/README.md (over the copy cap); {w.tmp} (holds the worktree)"),
                     bb.REF_READ.format(items=f"{w.other}/docs/spec.md; {w.other}/README.md")]


def test_research_reads_parses_the_line(w):
    (w.wt / ".superlite" / "briefs").mkdir(parents=True)
    (w.wt / ".superlite" / "briefs" / "lead.md").write_text("head\n" + bb.REF_READ.format(items="~/github/other; /opt/x") + "\ntail\n")
    assert bb.research_reads(w.wt / ".superlite") == [f"{w.home}/github/other", "/opt/x"]


def test_research_reads_without_a_lead_brief_is_empty(tmp_path):
    assert bb.research_reads(tmp_path) == []


def test_lead_brief_lists_the_note_paths_for_research(w):
    t = bb.lead_brief(B, {**CTX, "note": f"Reference: {w.other}", "worktree": str(w.wt)})
    (w.wt / ".superlite" / "briefs" / "lead.md").write_text(t)
    assert bb.research_reads(w.wt / ".superlite") == [str(w.other)]
    assert bb.REF_READ.split("{items}")[0] in t and "--machine local" not in bb.REF_READ and "(#1089, #1132)" in bb.REF_READ


def test_research_reads_parses_the_pre_1132_line(w):
    (w.wt / ".superlite" / "briefs").mkdir(parents=True)
    (w.wt / ".superlite" / "briefs" / "lead.md").write_text("head\n" + bb.REF_READ_1089.format(items="~/github/other; /opt/x") + "\ntail\n")
    assert bb.research_reads(w.wt / ".superlite") == [f"{w.home}/github/other", "/opt/x"]
    assert "--machine local" in bb.REF_READ_1089


def test_research_reads_first_line_wins(w):
    (w.wt / ".superlite" / "briefs").mkdir(parents=True)
    rows = [bb.REF_READ.format(items="/opt/new"), bb.REF_READ_1089.format(items="/opt/old")]
    (w.wt / ".superlite" / "briefs" / "lead.md").write_text("\n".join(rows) + "\n")
    assert bb.research_reads(w.wt / ".superlite") == ["/opt/new"]


def test_start_rewrites_a_stale_lead_brief(w, monkeypatch):
    briefs = w.wt / ".superlite" / "briefs"; briefs.mkdir(parents=True)
    (briefs / "lead.md").write_text(f"{bb.NOTE_HEAD}\n    Reference: {w.other}/docs/spec.md\n")
    monkeypatch.setattr(bb, "STANDING", {"note": f"Reference: {w.other}/docs/spec.md", "owned": {}})
    sd = w.tmp / "sd"; sd.mkdir()
    backlog_run._write_brief(sd, {"repo": "o/r"}, {**B, "state": "planned"}, w.wt, "b1", {"lead": {"text": "default"}}, "single", ([], 0))
    assert findings.standing_note(w.wt / ".superlite") == [bb.NOTE_HEAD, f"    Reference: {w.ref}/github/other/docs/spec.md"]
