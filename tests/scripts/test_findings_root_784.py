"""Fix briefs name Root after PLAN and carry the tree rule after the Reviewed version line (#784)."""
import json
import sys
from types import SimpleNamespace
import pytest
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import findings  # noqa: E402
from test_findings_route import put  # noqa: E402

RULE = ("Edit only files under Root, by absolute paths; a copy elsewhere (the main checkout, the folder that holds sl) is not yours. "
        "`git status` showing files changed against HEAD is the run's normal state: never revert, restore or stash a file you did not change "
        "(`git checkout`, `git restore` and `git stash` are denied to workers).")


@pytest.fixture
def run(tmp_path):
    root = tmp_path / "repo"; sd = root / ".superlite"; (sd / "fleet" / "reports").mkdir(parents=True)
    plan = make_plan(sd, [{"id": "T1", "owns": "src/a.py", "tests": "fast"}], name="plan.md")
    def report():
        p = sd / "fleet" / "reports" / "FR1.json"
        item = {"file": "src/a.py", "line": 3, "problem": "p", "fix": "x", "tier": 1, "quote": "code at 3"}
        put(root, item["file"], item["line"], item["quote"])
        p.write_text(json.dumps({"id": "W4", "label": "FR1", "status": "CHANGES_REQUESTED", "findings": [item], "valid": True}))
        return str(p)
    return root, sd, plan, report


def lines(sd, fid):
    return (sd / "briefs" / f"fix-{fid}.md").read_text().split("\n")


def check(ls, root):
    i = next(n for n, x in enumerate(ls) if x.startswith("PLAN="))
    assert ls[i + 1] == f"Root: {root.resolve().as_posix()}"
    j = next(n for n, x in enumerate(ls) if x.startswith("Reviewed version:"))
    assert ls[j + 1] == findings.TREE_RULE


def test_tree_rule_text():
    assert findings.TREE_RULE == RULE


def test_task_brief_names_root_after_plan(run):
    root, sd, plan, report = run
    findings.route(sd, plan, [report()], "/sl/sl")
    check(lines(sd, "F-T1-1"), root)


def test_coordinator_brief_names_root_after_plan(run):
    root, sd, plan, report = run
    (sd / "pool.json").write_text(json.dumps({"agents": [{"id": "W1", "busy": True, "current": "T1"}]}))
    findings.route(sd, plan, [report()], "/sl/sl")
    check(lines(sd, "F-C-1"), root)


def test_brief_text_without_root(run):
    root, sd, plan, report = run
    task = SimpleNamespace(id="T1", owns=["src/a.py"], tests="fast", cmd=None)
    item = {"id": "F-T1-1", "file": "src/a.py", "line": 3, "problem": "p", "fix": "x", "tier": 1, "label": "FR1"}
    ls = findings.brief_text("/sl/sl", plan, task, [item], 1, checkpoints=None).split("\n")
    assert not any(x.startswith("Root:") for x in ls)
    j = next(n for n, x in enumerate(ls) if x.startswith("Reviewed version:"))
    assert ls[j + 1] == findings.TREE_RULE
