"""#910: docs route preview renders in a linked worktree run to the checker."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"

CLAUSES = (
    (ROOT / "skills/writing-plans/probe-plan.md", "RenderPreview cannot reach the run's views in a linked git worktree (#910)"),
    (SDD / "fleet.md", "in a linked-worktree run the checks whose reach is a preview or snapshot render run per package (#910)"),
    (ROOT / "docs/simulator-limits.md", "RenderPreview renders the workspace Xcode has open, so in a linked worktree it shows the main checkout, never the run's edits (#910)"),
    (ROOT / "docs/tools.md", "`fleet_mcp.worktree_previews` (#910)"),
)


def test_docs_910_clauses_once():
    for path, clause in CLAUSES:
        assert path.read_text(encoding="utf-8").count(clause) == 1, (path, clause)


def test_quoted_texts_match_code():
    prime = (SDD / "scripts" / "build_prime.py").read_text(encoding="utf-8")
    lint = (SDD / "scripts" / "plan_tools.py").read_text(encoding="utf-8")
    assert "- Previews: RenderPreview cannot show this run's views" in prime
    assert "WARNING: PREVIEW:" in lint
    tools = (ROOT / "docs/tools.md").read_text(encoding="utf-8")
    assert "`- Previews:`" in tools and "`WARNING: PREVIEW:`" in tools
