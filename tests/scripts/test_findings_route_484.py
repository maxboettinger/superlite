# tests/scripts/test_findings_route_484.py
import json, sys
import pytest
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import findings  # noqa: E402
import plan_tools as pt  # noqa: E402


def f(file, line, tier, problem="p", fix="x"):
    return {"file": file, "line": line, "problem": problem, "fix": fix, "tier": tier}


@pytest.fixture
def run(tmp_path):
    root = tmp_path / "repo"; sd = root / ".superlite"; (sd / "fleet" / "reports").mkdir(parents=True)

    def report(label, items):
        p = sd / "fleet" / "reports" / f"{label}.json"
        p.write_text(json.dumps({"id": "W4", "label": label, "status": "CHANGES_REQUESTED", "findings": items, "valid": True}))
        return str(p)

    def ledger(*ids):
        (sd / "progress.md").write_text("".join(f"- commit {i} abcdef1234 done\n" for i in ids))

    def pool(*busy):
        (sd / "pool.json").write_text(json.dumps({"agents": [{"id": f"W{n}", "busy": True, "current": t} for n, t in enumerate(busy, 1)]}))
    return root, sd, report, ledger, pool


def test_running_tasks_from_pool_and_fleet(run):
    root, sd, report, ledger, pool = run
    (sd / "pool.json").write_text(json.dumps({"agents": [{"id": "W1", "busy": True, "current": "T5"}, {"id": "W2", "busy": False, "current": "T4"}]}))
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W3": {"state": "busy", "task": "T6,T7"},
                                                            "W4": {"state": "busy", "role": "fixer", "task": "fix-F-T1-1"}}}))
    assert findings.running_tasks(sd) == {"T5", "T6", "T7"}


def test_running_tasks_missing_files(run):
    root, sd, *_ = run
    assert findings.running_tasks(sd) == set()
    (sd / "pool.json").write_text("{bad")
    assert findings.running_tasks(sd) == set()


def test_unowned_file_goes_to_closest_committed_task(run):
    root, sd, report, ledger, pool = run
    plan = make_plan(root, [{"id": "T1", "owns": "src/registry/finance_store.py"}, {"id": "T2", "owns": "src/cli/main.py"}, {"id": "T3", "owns": "src/d.py"}])
    ledger("T1", "T2"); pool("T3")
    p = "tests/registry/test_registry_finance_store.py"
    lines = findings.route(sd, plan, [report("FR1", [f(p, 4, 1)])], "/sl/sl")
    b = sd.resolve() / "briefs"
    assert lines == [f"fixer tier=sonnet brief={b / 'fix-F-T1-1.md'} files={p} task=T1"]
    assert f"commit_task T1 --claim {p} --ruling" in (b / "fix-F-T1-1.md").read_text()


def test_unowned_file_never_goes_to_running_task(run):
    root, sd, report, ledger, pool = run
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py"}, {"id": "T2", "owns": "src/b.py"}])
    ledger("T1"); pool("T2")
    lines = findings.route(sd, plan, [report("FR1", [f("scripts/x.py", 2, 1)])], "/sl/sl")
    assert lines[0].endswith("files=scripts/x.py task=T1") and len(lines) == 1


def test_all_candidates_running_gives_coordinator_brief(run):
    root, sd, report, ledger, pool = run
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py"}, {"id": "T2", "owns": "src/b.py"}])
    pool("T1", "T2")
    lines = findings.route(sd, plan, [report("FR1", [f("scripts/x.py", 2, 2)])], "/sl/sl")
    b = sd.resolve() / "briefs"
    assert lines == [f"fixer tier=sonnet-high brief={b / 'fix-F-C-1.md'} files=scripts/x.py task=coordinator"]
    t = (b / "fix-F-C-1.md").read_text()
    assert "# Fix F-C-1 · tier 2 · coordinator commit" in t and "Task: none · running: T1, T2" in t
    assert "commit: held for the coordinator" in t and "commit_task T" not in t


def test_owned_file_of_running_task_goes_to_coordinator(run):
    root, sd, report, ledger, pool = run
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py"}, {"id": "T2", "owns": "src/b.py"}])
    ledger("T1", "T2"); pool("T1")
    lines = findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1), f("src/b.py", 2, 1)])], "/sl/sl")
    b = sd.resolve() / "briefs"
    assert lines == [f"fixer tier=sonnet brief={b / 'fix-F-T2-1.md'} files=src/b.py task=T2",
                     f"fixer tier=sonnet brief={b / 'fix-F-C-1.md'} files=src/a.py task=coordinator"]


def test_coordinator_ids_continue(run):
    root, sd, report, ledger, pool = run
    plan = make_plan(root, [{"id": "T1", "owns": "src/a.py"}])
    pool("T1")
    (sd / "briefs").mkdir(); (sd / "briefs" / "fix-F-C-2.md").write_text("# Fix F-C-2\n")
    lines = findings.route(sd, plan, [report("FR1", [f("src/a.py", 1, 1)])], "/sl/sl")
    assert "fix-F-C-3.md" in lines[0]
