# tests/scripts/test_fleet_roles_docs.py
from test_plan_tools import ROOT

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_fixing_md_routes_fleet_fixes():
    t = read("skills/subagent-driven-development/fixing.md")
    for s in ('"$SL" findings route', "fleet spawn --role fixer --tier", "fleet send Wn --brief", "(fleet off only)", "fresh fixer worker"):
        assert s in t, s
    assert 'bash "$SL"' not in t

def test_docs_fleet_md_covers_roles():
    t = read("docs/fleet.md")
    for s in ("--role", "fixer", "package-reviewer", "final-reviewer", "research", "--effort", ".superlite/briefs/",
              "auto mode", "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=0", "findings=", "findings route", "fleet run --layer",
              "APPROVED", "CHANGES_REQUESTED", "fleet off", "agents/researcher.md"):
        assert s in t, s
    assert "Reviewers, fixers and the final reviewer stay in-process" not in t
    assert "only implementer tasks of a taskgraph plan run in panes" not in t

def test_docs_fleet_md_keeps_earlier_contract_words():
    t = read("docs/fleet.md")
    for s in ("before the first dispatch", "sl-<run folder>-<hash>-w", "implementer", "in-process", "report BLOCKED",
              "never fall back to in-process", "4 panes", "20 rows", "fleet/agents"):
        assert s in t, s
