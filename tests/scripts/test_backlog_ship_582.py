import sys
from test_backlog_ship import sh, ship, b1, locked  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_ship as bsh  # noqa: E402
import backlog_state as bs  # noqa: E402


def test_note_items_unverified_and_kind():
    assert bsh.note_items("Unverified: app check (#12)\nKind: design (docs/plans/a.md)\n") == {"followups": [], "undone": [], "unverified": ["app check (#12)"], "kind": "design"}
    assert bsh.note_items("") == {"followups": [], "undone": [], "unverified": [], "kind": None}
    assert bsh.note_items("- unverified: suite green\nKind: code") == {"followups": [], "undone": [], "unverified": ["suite green"], "kind": None}


def test_with_closes_keeps_refs_and_kept_issues_open():
    assert bsh.with_closes("Refs #5\n", [5, 6]) == "Refs #5\n\nCloses #6\n"
    assert bsh.with_closes("", [5], keep_open=(5,)) == ""
    assert bsh.with_closes("refs: #5", [5]) == "refs: #5"


def test_kept_open_examples():
    assert bsh.kept_open("Refs #5", [5, 6], {"unverified": [], "kind": None}) == [5]
    assert bsh.kept_open("", [5, 6], {"unverified": ["app check (#6)"], "kind": None}) == [6]
    assert bsh.kept_open("", [5, "PIX-1"], {"unverified": [], "kind": "design"}) == [5, "PIX-1"]
    assert bsh.kept_open("Refs PIX-1", [5, "PIX-1"], {"unverified": [], "kind": None}) == ["PIX-1"]
    assert bsh.kept_open("", [56], {"unverified": ["check (#5)"], "kind": None}) == []


def notes(sh, text, body=None):
    d = sh.wt / ".superlite"; d.mkdir(exist_ok=True); (d / "notes.md").write_text(text)
    if body is not None:
        (d / "pr-body.md").write_text(body)


def test_merge_adds_no_closes_for_an_unverified_issue(sh, capsys):
    locked(sh, capsys); bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"issues": [5, 6]}))
    notes(sh, "Unverified: running-app check (#6)\n", "Fixes #5\nRefs #6\n")
    sh.replies = {"maxapp ship": (0, "merged #201 as abc\n"), "gh issue view 6": (0, "OPEN\n")}
    rc, out = ship(capsys, "B1", "merge")
    assert rc == 0 and out.endswith("OPEN #6\n")
    assert (sh.sd / "backlog" / "B1.pr-body.md").read_text() == "Fixes #5\nRefs #6\n"
    assert (b1(sh)["unverified"], b1(sh)["kind"], b1(sh)["open_issues"]) == (["running-app check (#6)"], None, [6])


def test_merge_refuses_a_body_closing_a_kept_issue(sh, capsys):
    locked(sh, capsys)
    notes(sh, "Unverified: suite green (#5)\n", "Closes #5\n")
    rc, out = ship(capsys, "B1", "merge")
    assert rc == 2 and out.startswith("refused: #5 stays open") and "Refs #5" in out
    assert not any(c[:2] == ["maxapp", "ship"] for c in sh.calls)


def test_design_batch_closes_nothing(sh, capsys):
    locked(sh, capsys); notes(sh, "Kind: design (docs/plans/x.md)\n", "Refs #5\n")
    sh.replies = {"maxapp ship": (0, "merged #201 as abc\n"), "gh issue view 5": (0, "OPEN\n")}
    assert ship(capsys, "B1", "merge")[0] == 0
    assert "Closes" not in (sh.sd / "backlog" / "B1.pr-body.md").read_text() and b1(sh)["kind"] == "design"


def test_notes_prints_reason_and_full_notes_anywhere(sh, capsys, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_ROLE")
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"state": "parked", "reason": "Status: BLOCKED " + "a" * 900}))
    assert ship(capsys, "B1", "notes") == (0, "reason: Status: BLOCKED " + "a" * 900 + "\nno notes\n")
    notes(sh, "Ruling: " + "r" * 700 + "\n")
    assert ship(capsys, "B1", "notes")[1].endswith("Ruling: " + "r" * 700 + "\n")
    (sh.sd / "backlog").mkdir(exist_ok=True); (sh.sd / "backlog" / "B1.notes.md").write_text("Ruling: kept\n")
    assert ship(capsys, "B1", "notes")[1].endswith("Ruling: kept\n")
    assert ship(capsys, "B9", "notes")[0] == 2


def test_notes_ignores_cwd_when_batch_has_no_worktree(sh, capsys, monkeypatch, tmp_path):
    monkeypatch.delenv("SUPERLITE_FLEET_ROLE")
    (tmp_path / ".superlite").mkdir(); (tmp_path / ".superlite" / "notes.md").write_text("Ruling: stray\n")
    monkeypatch.chdir(tmp_path)
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"worktree": None}))
    assert ship(capsys, "B1", "notes") == (0, "no notes\n")
