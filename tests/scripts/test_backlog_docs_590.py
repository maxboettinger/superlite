"""#590: backlog.md and tools.md name the plan sync, the run end, the handover."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BACKLOG = ((ROOT / "skills/subagent-driven-development/backlog-main.md").read_text() + "\n" + (ROOT / "skills/subagent-driven-development/backlog.md").read_text())
TOOLS = (ROOT / "docs/tools.md").read_text()


def section(name):
    return BACKLOG.split("## " + name, 1)[1].split("\n## ", 1)[0]


def step(n):
    return section("Main").split(f"\n{n}. ", 1)[1].split("\n", 1)[0]


def test_main_names_plan_sync():
    s = step(2)
    assert "sync: main checkout fast-forwarded" in s
    assert "not fast-forwarded" in s


def test_main_names_run_end():
    m = section("Main")
    assert "run end: every batch shipped or parked; fleet off (stopped workers cleared: <n>)" in m
    assert "sl fleet off stops and clears them" in m


def test_main_hand_over_rule():
    m = section("Main")
    assert "Hand over while a lead runs" in m
    assert "WAITING" in m


def test_closing_report_other_repository():
    assert "Follow-up: other repository <name>: <text>" in section("Lead")
    assert "other repository" in section("Main")


def test_tools_rows():
    rows = {l.split("|")[1].strip(" `"): l for l in TOOLS.splitlines() if l.startswith("| `")}
    assert "sync:" in rows["backlog"]
    assert "run end:" in rows["backlog_run"]
