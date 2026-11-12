"""#603 #596: fixer briefs copy the standing note, name the worktree sl, carry the format and checkpoint rules; --also adds files."""
import json
import re
import sys

import pytest
from test_plan_tools import SCRIPTS
from test_findings_route import f, run  # noqa: F401  (the fixture)

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import findings  # noqa: E402
import fleet_io  # noqa: E402

TOOL = "skills/subagent-driven-development/scripts"
LEAD = (f"# Lead brief: B1 (x)\nMax's decisions: none\n{bb.NOTE_HEAD}\n    run_tests -m is refused for now\n    second line\n"
        "Rulings from shipped batches: none\n")
NOTE = f"{bb.NOTE_HEAD}\n    run_tests -m is refused for now\n    second line\n"


def brief(sd, name):
    return (sd / "briefs" / name).read_text(encoding="utf-8")


def test_brief_copies_the_standing_note(run):
    root, sd, plan, report = run
    (sd / "briefs").mkdir()
    (sd / "briefs" / "lead.md").write_text(LEAD, encoding="utf-8")
    findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl")
    text = brief(sd, "fix-F-T1-1.md")
    assert NOTE in text and text.index(NOTE) < text.index("Findings:")
    assert "Rulings from shipped batches" not in text and "Max's decisions" not in text


def test_no_lead_brief_no_note_and_no_worktree_sl(run):
    root, sd, plan, report = run
    findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl")
    text = brief(sd, "fix-F-T1-1.md")
    assert bb.NOTE_HEAD not in text and "Worktree sl" not in text
    assert findings.standing_note(sd) == []


def test_coordinator_brief_gets_the_note_and_format_rule_only(run):
    root, sd, plan, report = run
    (sd / "briefs").mkdir()
    (sd / "briefs" / "lead.md").write_text(LEAD, encoding="utf-8")
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W1": {"state": "busy", "role": "implementer", "task": "T1"}}}))
    findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl")
    text = brief(sd, "fix-F-C-1.md")
    assert NOTE in text and findings.FORMAT_RULE in text and findings.CHECKPOINT_RULE not in text


def test_brief_names_the_worktree_sl_for_a_tool_file(run):
    root, sd, plan, report = run
    sl = root / TOOL / "sl"
    sl.parent.mkdir(parents=True)
    sl.write_text("#!/bin/sh\n", encoding="utf-8")
    findings.route(sd, plan, [report("FR1", [f(f"{TOOL}/findings.py", 3, 1)])], "/sl/sl")
    text = brief(sd, "fix-F-T3-1.md")
    want = f"Worktree sl (live checks of the tools this fix touches: findings; type it literally): {root.resolve() / TOOL / 'sl'}"
    assert want in text and fleet_io.WORKTREE_REST in text


def test_task_brief_says_checkpoints_are_hidden_and_formats_own_files(run, monkeypatch):
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "0")
    root, sd, plan, report = run
    findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl")
    text = brief(sd, "fix-F-T1-1.md")
    assert findings.FORMAT_RULE in text and findings.CHECKPOINT_RULE in text
    assert text.index(findings.CHECKPOINT_RULE) > text.index("Commit: `/sl/sl commit_task T1")
    for s in ("only the files you changed", "pass their paths", "never run it over the whole tree", "takes no paths",
              "the coordinator's, once at the final-review gate"):
        assert s in findings.FORMAT_RULE
    for s in ("hidden checkpoint", "refs/superlite/", "stay modified in `git status`", "normal"):
        assert s in findings.CHECKPOINT_RULE


def test_also_file_joins_the_one_brief_with_a_claim_line(run):
    root, sd, plan, report = run
    lines = findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl", also=["src/b.py"])
    b = sd.resolve() / "briefs"
    assert lines == [f"fixer tier=sonnet brief={b / 'fix-F-T1-1.md'} files=src/a.py,src/b.py task=T1"]
    text = (b / "fix-F-T1-1.md").read_text(encoding="utf-8")
    assert "Extra files (findings route --also; the fix may edit them too): src/b.py" in text
    assert f'/sl/sl commit_task T1 --claim src/b.py --ruling "{findings.ALSO_RULING}" --plan {plan.resolve()}' in text


def test_also_with_several_briefs_needs_a_task(run):
    root, sd, plan, report = run
    r = report("FR1", [f("src/a.py", 1, 1), f("src/d.py", 2, 1)])
    msg = "--also src/c.py needs one task brief; this call writes 2 (T1, T3): pass --also Tn=src/c.py"
    with pytest.raises(findings.AlsoError, match=re.escape(msg)):
        findings.route(sd, plan, [r], "/sl/sl", also=["src/c.py"])
    assert sorted(sd.glob("briefs/fix-*.md")) == []
    with pytest.raises(findings.AlsoError, match=re.escape("--also T2=src/c.py: T2 gets no brief in this call (T1, T3)")):
        findings.route(sd, plan, [r], "/sl/sl", also=["T2=src/c.py"])
    lines = findings.route(sd, plan, [r], "/sl/sl", also=["T3=src/c.py"])
    assert [ln.split(" files=")[1] for ln in lines] == ["src/a.py task=T1", "src/c.py,src/d.py task=T3"]


def test_cli_also_error_exits_2(run, capsys):
    root, sd, plan, report = run
    r = report("FR1", [f("src/a.py", 1, 1)])
    assert findings.main(["route", "--plan", str(plan), "--also", "T2=src/c.py", r]) == 2
    assert "error: --also T2=src/c.py: T2 gets no brief in this call (T1)" in capsys.readouterr().err
    assert findings.main(["route", "--plan", str(plan), "--also", "src/c.py", r]) == 0


def test_task_brief_has_no_checkpoint_rule_with_autocommit_on(run, monkeypatch):
    monkeypatch.setenv("SUPERLITE_AUTOCOMMIT", "1")
    root, sd, plan, report = run
    findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl")
    text = brief(sd, "fix-F-T1-1.md")
    assert findings.FORMAT_RULE in text and findings.CHECKPOINT_RULE not in text
