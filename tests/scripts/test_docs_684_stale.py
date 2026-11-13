"""Stale lines fixed (#684): reuse cap, researcher pin, reference-file readers."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"


def _text(p):
    return p.read_text(encoding="utf-8")


def test_reuse_cap_from_routing():
    skill = _text(SDD / "SKILL.md")
    assert "past 3 tasks" not in skill
    assert "routing.json" in skill and "20" in skill
    assert "<=3 tasks" not in _text(SDD / "fixing.md")


def test_skill_md_cap():
    assert len(_text(SDD / "SKILL.md")) <= 13300


def test_researcher_names_fleet_pin():
    text = _text(ROOT / "agents" / "researcher.md")
    front, body = text.split("---", 2)[1:]
    assert "model: haiku" in front
    assert "sonnet" in body


def test_reference_files_name_reader():
    for name in ("metrics.md", "orchestrator.md"):
        lines = [l for l in _text(SDD / name).splitlines() if l.strip()]
        assert "no brief, command or worker loads" in lines[1], name


def test_fleet_spawn_docstring_names_mcp_fact():
    text = _text(SDD / "scripts" / "fleet.py")
    assert "Every worker starts lean (#377): no MCP servers" not in text
    assert "--strict-mcp-config" in text
