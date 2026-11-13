"""Docs for the run config (#681)."""
from __future__ import annotations

from pathlib import Path

DOCS = Path(__file__).resolve().parents[2] / "docs"


def test_config_md_run_config():
    t = (DOCS / "config.md").read_text(encoding="utf-8")
    for s in ("run-configs.json", "run-config.json", "--config NAME", "CLAUDE_CODE_PROMPT_CACHE_TTL",
              "--strict-mcp-config", "xhigh", "default_tier"):
        assert s in t, s


def test_tools_md_lines():
    t = (DOCS / "tools.md").read_text(encoding="utf-8")
    for s in ("`run_config`", "backlog start --config", "fleet on --config"):
        assert s in t, s


def test_tools_md_append_only():
    lines = (DOCS / "tools.md").read_text(encoding="utf-8").splitlines()
    i = next(n for n, x in enumerate(lines) if x.startswith("`batch_cost.py` appends one cost and quality row"))
    assert i < len(lines) - 1
    tail = "\n".join(lines[i + 1:])
    assert "`run_config`" in tail and "backlog start --config" in tail and "fleet on --config" in tail


def test_tools_md_names_run_config_tool_line():
    lines = (DOCS / "tools.md").read_text(encoding="utf-8").splitlines()
    assert any("`run_config`" in x and "show|list" in x for x in lines)
