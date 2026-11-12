from pathlib import Path

DOC = (Path(__file__).resolve().parents[2] / "docs" / "tools.md").read_text(encoding="utf-8")


def rows(*names):
    return "\n".join(l for l in DOC.splitlines() if any(l.startswith(f"| `{n}` |") for n in names))


def test_backlog_rows_name_607_ship_and_status_items():
    r = rows("backlog", "backlog_run", "backlog_ship")
    for s in ("cleanup-cmd.json", "--reset", "OPEN", "Closes", "Decisions:", "Attribution:", "queue place", "cleanup owed", "healthy"):
        assert s in r, s


def test_backlog_rows_name_plan_and_undo_lines():
    r = rows("backlog", "backlog_run", "backlog_ship")
    for s in ("fast path", "already shipped:", "check:", "not found:", "offer:", "unskip", "--discard", "--help", "reopened", "latest"):
        assert s in r, s


def test_backlog_rows_name_lead_end_states():
    r = rows("backlog", "backlog_run", "backlog_ship")
    for s in ("no-change", "Unverified:", "Kind: design", "Refs #N", "ship B notes"):
        assert s in r, s


def test_worktree_row_names_core_bare():
    assert "core.bare" in rows("worktree")
