"""B95 (B94 follow-up): docs/tools.md names what B94 shipped in 1.5.104."""
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


def test_b94_rows_keep_table_shape():
    for name in ("commit_task", "findings", "pool"):
        r = row(name)
        assert r.count(" | ") == 1 and r.endswith(" |"), name


def test_commit_task_row_b94():
    has(row("commit_task"), "import check skipped (no module name)", "import warning", "--plan <run folder>",
        "review: Tn", "busy")


def test_findings_row():
    has(row("findings"), "findings route", "closest committed task", "task=coordinator",
        "commit: held for the coordinator")


def test_pool_row_baseline():
    has(row("pool"), "baseline_k")
