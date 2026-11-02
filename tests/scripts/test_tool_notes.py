"""Tool notes: audit excludes run state, Claude Code fallback and limits, commit_task --also docs."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
CC_TOOLS = (ROOT / "skills" / "using-superlite" / "references" / "claude-code-tools.md").read_text(encoding="utf-8")
DOCS_TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")


def test_audit_excludes_run_state():
    cfg = json.loads((ROOT / ".version-bump.json").read_text(encoding="utf-8"))
    assert ".superlite" in cfg["audit"]["exclude"]


def test_claude_code_fallback():
    assert "general-purpose" in CC_TOOLS and "minus the frontmatter" in CC_TOOLS


def test_claude_code_limits():
    assert "for loop" in CC_TOOLS and "feedback add --file" in CC_TOOLS


def test_also_doc():
    row = next(line for line in DOCS_TOOLS.splitlines() if line.startswith("| `commit_task` |"))
    assert "several files" in row and "docs.md" in row
