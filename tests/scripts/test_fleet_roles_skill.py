# tests/scripts/test_fleet_roles_skill.py
from test_plan_tools import ROOT

SDD = ROOT / "skills" / "subagent-driven-development"
LINE = 'Fleet mode (user asks): `"$SL" fleet on` before the first dispatch, then `fleet.md`: every role a worker, never in-process; missing or BLOCKED: report BLOCKED.'

def read(name):
    return (SDD / name).read_text(encoding="utf-8")

def test_sdd_fleet_line_sends_every_role_to_fleet():
    sdd = read("SKILL.md")
    assert LINE in sdd.splitlines() and "with the Agent calls" not in sdd and len(sdd) <= 11700

def test_fleet_md_names_each_role_and_its_command():
    t = read("fleet.md")
    for s in ("fleet spawn --for-dispatch", "briefs/wave0.md", "--role package-reviewer", "--role final-reviewer",
              "review-packet.md", "findings route", "--role fixer --tier", "--role research", "fleet send Wn --brief",
              ".superlite/briefs/", "fleet run --layer", "scripts/test_layers.py", "findings=", "UNKNOWN",
              "never call `Agent` for a superlite role", "stopped by `fleet wait`", "fleet send Wn --text"):
        assert s in t, s

def test_fleet_md_keeps_earlier_contract_words():
    t = read("fleet.md")
    for s in ("before the first dispatch", "sl-<run folder>-<hash>-w", "implementer", "in-process", "report BLOCKED",
              "never fall back to in-process", "one taskgraph plan in one checkout", "in addition", "fleet stop --all"):
        assert s in t, s
    assert "Reviewers, fixers and the final reviewer stay in-process" not in t
