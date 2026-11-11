"""B95 (#450, B86-B91 follow-ups): docs/tools.md fleet and backlog rows name what shipped in 1.5.82 to 1.5.101."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")


def row(name):
    rows = [ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |")]
    assert len(rows) == 1, name
    return rows[0]


def has(text, *tokens):
    missing = [t for t in tokens if t not in text]
    assert not missing, missing


def test_fleet_rows_keep_table_shape():
    for name in ("fleet", "fleet_io", "backlog", "backlog_run", "backlog_ship"):
        r = row(name)
        assert r.count(" | ") == 1 and r.endswith(" |"), name


def test_fleet_row():
    has(row("fleet"), "--for-review", "--package", "review: Tn", "--strict-mcp-config", "another account",
        "dropped", "--autocompact", "trust")


def test_fleet_io_row():
    has(row("fleet_io"), "ASKED", "concerns=N", "--full", "Files changed:", "retr")


def test_backlog_row():
    has(row("backlog"), "GitHub numbers", "ranked first", "--github", "--max-batches", "--add", "overlap:",
        "--note FILE", "note:", "parked", "tell B --text T", "--approve-ship --source prompt", '"by"')


def test_backlog_run_and_ship_rows():
    has(row("backlog_run"), "followups=N", "undone=M", "follow-up:", "left undone:")
    has(row("backlog_ship"), "B.notes.md", "[cut: full text in B.notes.md]")
