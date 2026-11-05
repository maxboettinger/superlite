# tests/scripts/test_findings_route.py
import json, sys
import pytest
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import findings  # noqa: E402

def f(file, line, tier, problem="p", fix="x"):
    return {"file": file, "line": line, "problem": problem, "fix": fix, "tier": tier}

@pytest.fixture
def run(tmp_path):
    root = tmp_path / "repo"; sd = root / ".superlite"; (sd / "fleet" / "reports").mkdir(parents=True)
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py, tests/test_a.py"}, {"id": "T2", "owns": "src/b.py, src/c.py"}, {"id": "T3", "owns": "src/d.py"}])
    def report(label, items):
        p = sd / "fleet" / "reports" / f"{label}.json"
        p.write_text(json.dumps({"id": "W4", "label": label, "status": "CHANGES_REQUESTED", "findings": items, "valid": True}))
        return str(p)
    return root, sd, plan, report

def test_groups_by_owning_task_with_the_highest_tier(run):
    root, sd, plan, report = run
    r1 = report("FR1", [f("src/a.py", 12, 1, "off by one", "use <="), f("src/b.py", 3, 1), f("src/c.py", 9, 3)])
    r2 = report("R-T1", [f("src/a.py", 12, 1, "off by one", "use <="), f("tests/test_a.py", 4, 2)])
    lines = findings.route(sd, plan, [r1, r2], "/sl/sl")
    b = sd.resolve() / "briefs"
    assert lines == [f"fixer tier=sonnet-high brief={b / 'fix-F-T1-1.md'} files=src/a.py,tests/test_a.py task=T1",
                     f"fixer tier=opus brief={b / 'fix-F-T2-1.md'} files=src/b.py,src/c.py task=T2"]
    t1 = (b / "fix-F-T1-1.md").read_text()
    assert "- F-T1-1 src/a.py:12 - off by one - use <= (tier 1, from FR1)" in t1 and "- F-T1-2 tests/test_a.py:4 - p - x (tier 2, from R-T1)" in t1
    assert "F-T1-3" not in t1 and f"PLAN={plan.resolve()}" in t1 and "/sl/sl commit_task T1 --plan" in t1 and ".superlite/fixes/<id>.md" in t1

def test_ids_continue_after_earlier_rounds(run):
    root, sd, plan, report = run
    (sd / "fixes").mkdir(); (sd / "fixes" / "F-T3-2.md").write_text("# F-T3-2 · tier 1 · round 1 · NOT_FIXED\n")
    assert findings.route(sd, plan, [report("FR2", [f("src/d.py", 5, 1)])], "/sl/sl") == [
        f"fixer tier=sonnet brief={sd.resolve() / 'briefs' / 'fix-F-T3-3.md'} files=src/d.py task=T3"]

def test_unowned_and_absolute_paths(run):
    root, sd, plan, report = run
    lines = findings.route(sd, plan, [report("FR1", [f(str(root / "src" / "d.py"), 1, 1), f("./scripts/x.py", 2, 1)])], "/sl/sl")
    assert lines == [f"fixer tier=sonnet brief={sd.resolve() / 'briefs' / 'fix-F-T3-1.md'} files=scripts/x.py,src/d.py task=T3"]
    assert "/sl/sl commit_task T3 --claim scripts/x.py --ruling" in (sd / "briefs" / "fix-F-T3-1.md").read_text()

def test_no_findings_and_bad_report(run, capsys):
    root, sd, plan, report = run
    assert findings.route(sd, plan, [report("FR3", [])], "/sl/sl") == []
    assert findings.main(["route", "--plan", str(plan), report("FR3", [])]) == 0 and capsys.readouterr().out.strip() == "findings: none"
    assert findings.main(["route", "--plan", str(plan), str(sd / "missing.json")]) == 2 and "cannot read report" in capsys.readouterr().err
