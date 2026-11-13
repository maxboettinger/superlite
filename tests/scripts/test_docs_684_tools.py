"""#684: fleet.md and docs/tools.md carry the lines the issue asks for."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
FLEET = (ROOT / "skills/subagent-driven-development/fleet.md").read_text(encoding="utf-8")
TOOLS = (ROOT / "docs/tools.md").read_text(encoding="utf-8")


def _para(text, needle):
    return next(p for p in text.split("\n\n") if needle in p)


def test_fleet_md_background_wait():
    p = _para(FLEET, "fleet wait --timeout 0")
    assert "background command" in p
    assert "one run's state dir" in FLEET


def test_fleet_md_rearm_backlog_run():
    p = _para(FLEET, "Herdr restart")
    assert "backlog run" in p
    assert "backlog wait" not in p


def test_fleet_md_mcp_fact():
    assert "--strict-mcp-config" in FLEET
    assert "implementer, fixer or package-reviewer" in FLEET
    assert "xcrun mcpbridge" in FLEET


def test_fleet_md_rule_files():
    last = FLEET.rstrip("\n").splitlines()[-1]
    assert "backlog-main.md" in last and "backlog.md" in last


def test_tools_md_677_lines():
    for s in ("not_code", "TREE: unchanged by the sync", "Verdict:", "no run", "--only",
              "machine: <free", "scratch folder removed", "backlog-main.md"):
        assert s in TOOLS, s
