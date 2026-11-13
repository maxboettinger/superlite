"""#602: backlog.md names append-only files, adjacent fixes and the notes route."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ((ROOT / "skills/subagent-driven-development/backlog-main.md").read_text() + "\n" + (ROOT / "skills/subagent-driven-development/backlog.md").read_text())

S1 = ("A batch's `append_only` (in the triage proposal) lists the files of its `files` it only adds lines to, such as a strings catalog, "
      "a changelog or a module doc; a file two batches both list there does not serialise them: the proposal needs no `depends` for it, "
      "`start` holds neither batch on it, and its `overlap:` line ends `append-only in both, no hold; conflicts resolve at the ship rebase` (#602).")
S2 = ("- Adjacent fixes: a defect you find on the screen or flow your batch already changes (a render check, a review, a test) is fixed in this "
      "batch when the fix stays inside your batch's files and needs no new design decision; name it in notes.md as one "
      "`Ruling: adjacent fix: <what>` line and in pr-body.md. A fix outside those files, or one that needs a decision, stays a `Follow-up:` line (#602).")
S3 = ("- Append-only files: your brief's `Append-only files` line names files of your batch that another batch may append to at the same time. "
      "Add your lines and never reorder, rewrite or delete existing ones; when the ship rebase conflicts on such a file (`bump` exits 5), "
      "keep both sides' lines, finish the rebase and rerun `bump` (#602).")
S4 = '`"$SL" backlog notes B` does the same.'


def test_backlog_md_names_append_only_and_adjacent_fixes():
    assert S1 in BACKLOG
    lead = BACKLOG.split("## Lead", 1)[1].split("## Permissions", 1)[0]
    assert S2 in lead and S3 in lead


def test_backlog_md_names_the_notes_route():
    assert S4 in BACKLOG
