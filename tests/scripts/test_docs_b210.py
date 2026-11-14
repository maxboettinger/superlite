"""B210: the docs name the #780/#781 guard rules, the guard-batch measurement rule and main's code-ruling route (#821)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"


def test_hooks_doc_names_b210_rules():
    t = (ROOT / "docs" / "hooks.md").read_text()
    for s in ("unresolved words (#780, #781)", "`source <(...)`", "print-only `sed -n`", "`cp` or `mv`",
              "`$(seq [FIRST [STEP]] LAST)`", "`sys.executable`", "defs.sh", "--also A B C"):
        assert s in t, s
    assert "`sys.executable`, `run(cmd)`" not in t


def test_lead_rules_name_who_runs_a_guard_measurement():
    t = (SDD / "backlog.md").read_text()
    assert t.count("- Guard batches:") == 1
    assert "runs in a worker the plan task names, never in your shell (#780)" in t


def test_main_rules_route_project_file_rulings():
    t = (SDD / "backlog-main.md").read_text()
    assert "names who makes it, an implementer task or a fixer (`sl findings route`)" in t
    assert t.count("(#821)") == 1
