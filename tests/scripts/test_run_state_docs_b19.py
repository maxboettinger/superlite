# tests/scripts/test_run_state_docs_b19.py
"""B19: report, finishing, status and backlog command texts (#250, #251, #271)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def test_report_names_the_build_report_pair_and_the_legacy_read():
    t = read("commands/report.md")
    assert "`<plan>.build-report.md` and `.build-report.json`" in t
    assert "`<plan>.report.md` and `.report.json` pair that older builds wrote" in t
    assert t.index("build-report.md") < t.index("older builds wrote")


def test_finishing_names_the_build_report():
    t = read("skills/finishing-a-development-branch/SKILL.md")
    assert "name `<plan>.build-report.md` (next to the plan) as the full report" in t
    assert "<plan>.report.md" not in t


def test_status_lists_held_tasks():
    t = read("commands/status.md")
    assert "held tasks, budget." in t.splitlines()[1]
    assert "`sl hold --plan <plan>`" in t and "`held Tn: reason`" in t and "`held: none`" in t
    assert "each held task with its id and reason" in t
    assert "under 15 lines" in t and t.rstrip().endswith("Change nothing.")


def test_backlog_main_starts_in_a_fresh_session():
    t = read("commands/backlog.md")
    para = next(p for p in t.split("\n\n") if p.startswith("Start in a fresh session."))
    for s in ("re-injects", "`/clear`", "`/superlite:backlog` again", "end your turn", "Never load another superlite skill"):
        assert s in para, s
    assert t.index("Start in a fresh session.") < t.index("1. Run")
