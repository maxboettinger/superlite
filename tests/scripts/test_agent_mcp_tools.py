"""Implementer, fixer and package-reviewer agents inherit the session's MCP tools (S1 spike, #98)."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
AGENTS = ["implementer", "implementer-haiku", "fixer-sonnet", "fixer-sonnet-high", "fixer-opus", "package-reviewer"]
DISALLOWED = ("disallowedTools: Agent, Task, Workflow, AskUserQuestion, SendMessage, EnterWorktree, ExitWorktree, "
              "EnterPlanMode, ExitPlanMode, CronCreate, CronDelete, ScheduleWakeup, RemoteTrigger, PushNotification, "
              "TaskCreate, TaskUpdate, TaskStop")


def frontmatter(name):
    lines = (ROOT / "agents" / f"{name}.md").read_text(encoding="utf-8").splitlines()
    assert lines[0] == "---"
    return lines[1:lines.index("---", 1)]


def test_agents_admit_mcp_tools():
    """No `tools:` allow-list (it hides every MCP tool); the exact deny-list instead; final-reviewer stays read-only."""
    for name in AGENTS:
        fm = frontmatter(name)
        assert not any(line.startswith("tools:") for line in fm), name
        assert fm.count(DISALLOWED) == 1, name
    assert "tools: Read, Grep, Glob" in frontmatter("final-reviewer")


def test_agents_never_get_agent_tool():
    """No agent file admits `Agent`: either no allow-list entry for it or it is on the deny-list."""
    for path in sorted((ROOT / "agents").glob("*.md")):
        fm = frontmatter(path.stem)
        allow = [line.split(":", 1)[1] for line in fm if line.startswith("tools:")]
        deny = [line.split(":", 1)[1] for line in fm if line.startswith("disallowedTools:")]
        for line in allow:
            assert "Agent" not in [t.strip() for t in line.split(",")], path.name
        if not allow:
            assert deny and "Agent" in [t.strip() for t in deny[0].split(",")], path.name


def test_plans_may_name_mcp_checks():
    """writing-plans: an MCP-only check is a task step only when the project configures that server."""
    t = (ROOT / "skills/writing-plans/SKILL.md").read_text(encoding="utf-8")
    line = next((x for x in t.splitlines() if "RenderPreview" in x), "")
    assert "MCP-only check" in line and "task step" in line and "configures that MCP server" in line
    assert "coordinator's step" in line


def test_sdd_names_inherited_mcp_tools():
    """subagent-driven-development: agents inherit the session's MCP tools; approve project servers before dispatch."""
    t = (ROOT / "skills/subagent-driven-development/SKILL.md").read_text(encoding="utf-8")
    line = next((x for x in t.splitlines() if "inherit the session's MCP tools" in x), "")
    assert "approved before dispatch" in line and "background agents" in line
