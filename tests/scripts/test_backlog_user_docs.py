# tests/scripts/test_backlog_user_docs.py
from test_plan_tools import ROOT

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_docs_fleet_md_covers_leads():
    t = read("docs/fleet.md")
    for s in ("## Batch leads", "/superlite:backlog", "SUPERLITE_FLEET_ROLE=lead", "SUPERLITE_FLEET_PARENT_DIR", "--permission-mode auto",
              "Bash(maxapp ship *)", "ship lock", "~/.superlite/locks/", "backlog.json", "NEEDS_DECISION", "question.json",
              "Lead ships a batch", "Escalation", "Two leads ship in turn", "fast-forwards the main checkout"):
        assert s in t, s

def test_hooks_md_names_the_lead_rules():
    t = read("docs/hooks.md")
    line = next(x for x in t.splitlines() if x.startswith("- `block-coordinator-edits`"))
    assert all(s in line for s in ("SUPERLITE_FLEET_ROLE=lead", "backlog.json", "absolute path", "turns the outside base off"))
    assert "- `capture-worker-stop`" in t and "SUPERLITE_FLEET_PARENT_DIR" in t and "- `deny-worker-permission`" in t

def test_tools_md_lists_the_backlog_tools():
    t = read("docs/tools.md")
    for s in ("backlog", "backlog_run", "backlog_ship", "backlog_state", "backlog_checks", "backlog_brief", "ship_lock", "fleet_lead"):
        assert f"| `{s}` |" in t, s
