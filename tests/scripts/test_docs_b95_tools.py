"""B95 (#450, B75-B93 follow-ups): docs/tools.md plan, review and test rows name what shipped in 1.5.77 to 1.5.103."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
ROWS = ("plan_tools", "pt_review", "probe_run", "commit_task", "testcmd", "run_tests", "incident", "feedback",
        "finish", "status", "pool", "orchestrator", "worktree")


def row(name):
    rows = [ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |")]
    assert len(rows) == 1, name
    return rows[0]


def has(text, *tokens):
    missing = [t for t in tokens if t not in text]
    assert not missing, missing


def test_rows_keep_table_shape():
    for name in ROWS:
        r = row(name)
        assert r.count(" | ") == 1 and r.endswith(" |"), name


def test_plan_tools_row():
    r = row("plan_tools")
    has(r, "**Edges:** hard", "imports Python", "WARNING: PLATFORM:", "ADAPTER: rebuilt", "ADAPTER: removed",
        "RUN: <sl> plan_tools adapter --plan P", "import-linter", "package.json")
    assert "SwiftPM only" not in r


def test_pt_review_row():
    has(row("pt_review"), "Name(Exception)", "owning task", "write the full module path", "## Render evidence",
        ".superlite/render/")


def test_probe_run_row():
    has(row("probe_run"), "--plan", "raises=", "--dismiss", 'results["dismissed"]', "dismissed.json")


def test_commit_task_row():
    r = row("commit_task")
    has(r, "probe files committed", "claimed by T2, changed after its checkpoint",
        "commit_task T2 commits it once T2 is done")
    assert "(`left uncommitted (claimed by Tn): F`)" not in r


def test_testcmd_row():
    has(row("testcmd"), "membership", "not in a test target")


def test_run_tests_row():
    has(row("run_tests"), "--limit", "wall-clock limit", "--also", "test-summary-Tn.latest", ".output.log",
        "run_tests: output", "no tests ran", "runner:", "(crashed)")


def test_incident_feedback_finish_rows():
    has(row("incident"), "resolve --kind", "--reason")
    has(row("feedback"), "held back")
    has(row("finish"), "review packet: older than the last full run", "next: sl orchestrator end")


def test_status_pool_orchestrator_worktree_rows():
    has(row("status"), "sl status")
    has(row("pool"), "prune", "session")
    has(row("orchestrator"), "resume")
    has(row("worktree"), "--dir NAME", "--branch NAME")


def test_guard_paragraph():
    para = [ln for ln in TOOLS.splitlines() if ln.startswith("The coordinator guard")]
    assert len(para) == 1
    has(para[0], "Refused command:", "rmdir", "+")
