import sys
from test_backlog_ship import sh, ship, b1, locked  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief  # noqa: E402
import backlog_ship as bsh  # noqa: E402

B = {"id": "B7", "issues": [850], "pr": 9, "version": "1.0.1"}


def test_scope_rulings_examples():
    assert backlog_brief.scope_rulings("Ruling: x\nRuling: [scope] dropped CSV export (#12)\n- ruling: [SCOPE]  added --dry-run\n") == ["dropped CSV export (#12)", "added --dry-run"]
    assert backlog_brief.scope_rulings("Ruling: keep [scope] words\nFollow-up: y\n") == []


def test_scope_ruling_control_chars():
    assert backlog_brief.scope_rulings("Ruling: [scope] a\x1b[2J\tb\n") == ["a[2J b"]


def test_note_items_scope():
    assert bsh.note_items("Ruling: [scope] dropped X\nFollow-up: y\n") == {"followups": ["y"], "undone": [], "unverified": [], "scope": ["dropped X"], "kind": None}
    assert bsh.note_items("") == {"followups": [], "undone": [], "unverified": [], "scope": [], "kind": None}


def test_summary_lists_scope_first():
    assert backlog_brief.summary(B, "Ruling: plain one\nFollow-up: f\nRuling: [scope] dropped X\n") == "B7 shipped: #850\nPR: #9\nVersion: 1.0.1\nRuling: [scope] dropped X\nRuling: plain one\nFollow-up: f\n"


def test_summary_cap_keeps_scope():
    notes = "".join(f"Ruling: plain {i}\n" for i in range(8)) + "Ruling: [scope] dropped X\n"
    out = backlog_brief.summary(B, notes)
    assert "Ruling: [scope] dropped X" in out.splitlines()
    assert len(out.splitlines()) <= backlog_brief.SUMMARY_LINES


def test_summary_without_scope_unchanged():
    assert backlog_brief.summary(B, "Ruling: a\nFollow-up: f\n") == "B7 shipped: #850\nPR: #9\nVersion: 1.0.1\nRuling: a\nFollow-up: f\n"


def test_merge_stores_scope(sh, capsys):
    locked(sh, capsys)
    (sh.wt / ".superlite").mkdir(exist_ok=True); (sh.wt / ".superlite" / "notes.md").write_text("Ruling: [scope] dropped X\n")
    sh.replies = {"maxapp ship": (0, "merged #201 as abc\n")}
    assert ship(capsys, "B1", "merge")[0] == 0
    assert b1(sh)["scope"] == ["dropped X"]


def test_notes_rule_names_scope():
    assert "`Ruling: [scope] ...`" in backlog_brief.NOTES_RULE


def test_note_items_scope_matches_brief_parser():
    for x in ("Ruling: x\nRuling: [scope] dropped CSV export (#12)\n- ruling: [SCOPE] added --dry-run\n",
              "Ruling: [scope] a\x1b[2J\tb\n", "**Ruling:** [scope] bold one\n", "Ruling: [scope] \n"):
        assert bsh.note_items(x)["scope"] == backlog_brief.scope_rulings(x)
