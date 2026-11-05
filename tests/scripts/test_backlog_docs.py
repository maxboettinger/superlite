from test_plan_tools import ROOT
CMD = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")
REF = (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8")

def test_command_is_the_main_loop():
    assert CMD.startswith("---\ndescription: ")
    for s in ('"$SL" backlog status', "after any compaction", '"$SL" backlog plan', "background command", '"$SL" backlog decide --print',
              "AskUserQuestion", "at most 4", '"$SL" backlog decide --file', '"$SL" backlog start', '"$SL" backlog wait',
              '"$SL" backlog answer', "needs_decision", "parked", "shipped", "Never read issue bodies", "backlog.md", "BLOCKED"):
        assert s in CMD, s
    assert CMD.index("backlog status") < CMD.index("backlog plan") < CMD.index("backlog start")

def test_reference_holds_the_main_and_lead_rules():
    for s in ("## Main", "## Lead", "--plan", "Never end your turn while your workers run", ".superlite/question.json", "Status: NEEDS_DECISION",
              "answer-<n>.json", '"$SL" backlog ship B lock', "LAYERS:", "fleet run --layer", "exit 4", "exit 5", "exit 6", "bump", "merge",
              "600000", "release --park", ".superlite/notes.md", ".superlite/pr-body.md", "--permission-mode auto", "Bash(maxapp ship *)",
              "PermissionRequest", "fast-forwards the main checkout"):
        assert s in REF, s
    fleet = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
    assert "`backlog.md`" in fleet and "/superlite:backlog" in fleet
