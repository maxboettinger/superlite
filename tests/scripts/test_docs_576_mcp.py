"""Docs name the MCP servers a fleet worker keeps (#576)."""
from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_fleet_md_names_mcp():
    text = (DOCS / "fleet.md").read_text(encoding="utf-8")
    for needle in ('"mcp"', "--mcp-config", "xcode", "SUPERLITE_MCP_CHECK=0", "left out"):
        assert needle in text, needle


def test_tools_md_rows():
    lines = (DOCS / "tools.md").read_text(encoding="utf-8").splitlines()
    assert any(line.startswith("| `fleet_mcp` |") for line in lines)
    assert any(line.startswith("| `mcp_check` |") for line in lines)
    fleet = next(line for line in lines if line.startswith("| `fleet` |"))
    assert "--mcp-config" in fleet


def test_fleet_md_lookup_order_matches_code():
    text = (DOCS / "fleet.md").read_text(encoding="utf-8")
    assert "(local scope), the project `.mcp.json`, user scope or the built-in `xcode`" in text
