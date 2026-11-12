import sys
from test_backlog_ship import sh, ship, b1, locked  # noqa: F401
from test_backlog_ship_done import dn, setb  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_ship as bsh  # noqa: E402
import backlog_run  # noqa: E402


def test_note_items_examples():
    assert bsh.note_items("Ruling: x\nFollow-up: docs/tools.md lacks tell\n- Left undone: run the migration on prod\n") == {"followups": ["docs/tools.md lacks tell"], "undone": ["run the migration on prod"], "unverified": [], "kind": None}
    assert bsh.note_items("Ruling: a; follow-up (outside B27's files): fix SKILL.md") == {"followups": ["fix SKILL.md"], "undone": [], "unverified": [], "kind": None}
    assert bsh.note_items("Follow-up issue: x\x1b[2J\ty") == {"followups": ["x[2J y"], "undone": [], "unverified": [], "kind": None}
    assert bsh.note_items("") == {"followups": [], "undone": [], "unverified": [], "kind": None}
    assert bsh.note_items("Left undone: a") == {"followups": [], "undone": ["a"], "unverified": [], "kind": None}


def test_merge_keeps_notes_and_items(sh, capsys):
    locked(sh, capsys)
    (sh.wt / ".superlite").mkdir(exist_ok=True); (sh.wt / ".superlite" / "notes.md").write_text("Ruling: x\nFollow-up: y\nLeft undone: z\x07\n")
    sh.replies = {"maxapp ship": (0, "merged #201 as abc\n")}
    assert ship(capsys, "B1", "merge")[0] == 0
    assert (sh.sd / "backlog" / "B1.notes.md").read_text() == "Ruling: x\nFollow-up: y\nLeft undone: z\n"
    assert (b1(sh)["followups"], b1(sh)["undone"]) == (["y"], ["z"])


def test_merge_without_notes_writes_no_file(sh, capsys):
    locked(sh, capsys)
    sh.replies = {"maxapp ship": (0, "merged #201 as abc\n")}
    assert ship(capsys, "B1", "merge")[0] == 0
    assert not (sh.sd / "backlog" / "B1.notes.md").exists()
    assert (b1(sh).get("followups"), b1(sh).get("undone")) == ([], [])


def test_done_records_items(dn, capsys, monkeypatch):
    sh, seen = dn, []
    (sh.wt / ".superlite").mkdir(exist_ok=True); (sh.wt / ".superlite" / "notes.md").write_text("Follow-up: q")
    sh.replies = {"gh pr view": (0, "MERGED\n")}
    monkeypatch.setattr(backlog_run, "_shipped", lambda p, sd, root, b, wt, **kw: seen.append((b, kw)) or ["x"])
    assert ship(capsys, "B1", "done", "--pr", "262")[0] == 0
    assert b1(sh)["followups"] == ["q"] and seen[0][0]["followups"] == ["q"] and seen[0][0]["undone"] == []
    assert seen[0][1].get("push") is False
