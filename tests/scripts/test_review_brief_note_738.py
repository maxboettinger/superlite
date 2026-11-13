# tests/scripts/test_review_brief_note_738.py
"""#738: the review brief a script writes carries the lead's standing note once."""
import sys
from test_fleet_for_review_422 import rw  # noqa: F401
from test_fleet import world  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import backlog_brief as bb  # noqa: E402


def lead(rw, with_note=True):
    (rw.sd / "briefs").mkdir(exist_ok=True)
    rows = ["# Lead", "x"] + ([bb.NOTE_HEAD, "    keep it public", "    no names"] if with_note else [])
    (rw.sd / "briefs" / "lead.md").write_text("\n".join(rows) + "\n\nother\n")


def go(rw, *a):
    return fleet.main(["spawn", "--for-review", "T3", "--plan", str(rw.plan), *a])


def test_review_brief_carries_standing_note(rw):
    lead(rw)
    (rw.sd / "notes.txt").write_text("my note")
    assert go(rw, "--note", str(rw.sd / "notes.txt")) == 0
    text = (rw.sd / "briefs" / "review-T3.md").read_text()
    assert text.count(bb.NOTE_HEAD) == 1 and "    keep it public\n    no names\n" in text
    assert text.index(bb.NOTE_HEAD) < text.index("## Coordinator notes")


def test_review_brief_note_without_coordinator_notes(rw):
    lead(rw)
    assert go(rw) == 0
    text = (rw.sd / "briefs" / "review-T3.md").read_text()
    assert text.count(bb.NOTE_HEAD) == 1 and "## Coordinator notes" not in text


def test_review_brief_without_note_unchanged(rw):
    assert go(rw) == 0
    plain = (rw.sd / "briefs" / "review-T3.md").read_text()
    lead(rw, with_note=False)
    assert go(rw) == 0
    assert (rw.sd / "briefs" / "review-T3.md").read_text() == plain
    assert bb.NOTE_HEAD not in plain
