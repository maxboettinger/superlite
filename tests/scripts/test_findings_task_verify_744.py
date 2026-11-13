"""Fixer briefs name --task Tn --plan <plan file> for a task with a **Tests:** cmd=, so run_tests runs that command (#744)."""
import json
import re
import sys
from types import SimpleNamespace
import pytest
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import findings  # noqa: E402
import run_tests  # noqa: E402

PLAIN = "Verify: `/sl/sl run_tests --fast <the test files you touched> --background`, then run the printed `wait:` line in the foreground (never as a background command) and end your turn only after it reports."


def f(file, line, tier=1):
    return {"file": file, "line": line, "problem": "p", "fix": "x", "tier": tier}


@pytest.fixture
def run(tmp_path):
    root = tmp_path / "repo"; sd = root / ".superlite"; (sd / "fleet" / "reports").mkdir(parents=True)
    plan = make_plan(sd, [{"id": "T1", "owns": "src/a.py, tests/test_a.py", "tests": "fast cmd=bash tests/run.sh"},
                          {"id": "T2", "owns": "src/b.py", "tests": "fast"}], name="plan.md")
    def report(items):
        p = sd / "fleet" / "reports" / "FR1.json"
        p.write_text(json.dumps({"id": "W4", "label": "FR1", "status": "CHANGES_REQUESTED", "findings": items, "valid": True}))
        return str(p)
    return root, sd, plan, report


def brief(sd, fid):
    return (sd / "briefs" / f"fix-{fid}.md").read_text()


def test_cmd_task_brief_names_task_and_plan_file(run):
    root, sd, plan, report = run
    findings.route(sd, plan, [report([f("src/a.py", 3)])], "/sl/sl")
    t = brief(sd, "F-T1-1")
    assert f"Verify: `/sl/sl run_tests --fast <the test files you touched> --task T1 --plan {plan.resolve()} --background` runs T1's **Tests:** cmd= (`bash tests/run.sh`; the paths are not passed to it), then run the printed `wait:` line in the foreground (never as a background command) and end your turn only after it reports." in t.split("\n")
    assert PLAIN not in t.split("\n")


def test_run_folder_plan_becomes_the_plan_file(run):
    root, sd, plan, report = run
    findings.route(sd, sd, [report([f("src/a.py", 3)])], "/sl/sl")
    t = brief(sd, "F-T1-1")
    assert f"--task T1 --plan {plan.resolve()} --background" in t
    assert f"--plan {sd.resolve()} --background" not in t


def test_brief_command_takes_the_cmd_route(run, monkeypatch):
    root, sd, plan, report = run
    findings.route(sd, sd, [report([f("src/a.py", 3)])], "/sl/sl")
    m = re.search(r"--task (\S+) --plan (\S+) --background", brief(sd, "F-T1-1"))
    monkeypatch.chdir(root)
    spec = run_tests.task_cmd_spec(SimpleNamespace(task=m.group(1), plan=m.group(2)))
    assert spec is not None and spec["command"] == "bash tests/run.sh"


def test_task_without_cmd_keeps_the_plain_line(run):
    root, sd, plan, report = run
    findings.route(sd, plan, [report([f("src/b.py", 3)])], "/sl/sl")
    t = brief(sd, "F-T2-1")
    assert PLAIN in t.split("\n") and "--task" not in t.split("Verify:")[1].split("\n")[0]


def test_coordinator_brief_has_no_task_flag(run):
    root, sd, plan, report = run
    (sd / "pool.json").write_text(json.dumps({"agents": [{"id": "W1", "busy": True, "current": "T1"}]}))
    findings.route(sd, plan, [report([f("src/a.py", 3)])], "/sl/sl")
    t = brief(sd, "F-C-1")
    assert PLAIN in t.split("\n")
    assert "No `--task` here: the tasks owning these files are in progress, so the project's test command runs these files (a task's **Tests:** cmd= does not apply)." in t.split("\n")
    assert "--task T1" not in t


def test_every_brief_names_the_wait_timeout():
    text = "\n".join(findings.shared_lines("/sl/sl"))
    assert "The `--background` run prints a `next:` cue and, as its last line, the `wait:` line; give that wait's Bash call a timeout of 600000 ms (the default 120000 ms ends a longer wait early)." in text.split("\n")


def test_task_cmd_reads_the_tests_field(run):
    root, sd, plan, report = run
    import plan_tools as pt
    tasks = {t.id: t for t in pt.Plan.load(str(plan)).tasks}
    assert findings.task_cmd(tasks["T1"]) == "bash tests/run.sh"
    assert findings.task_cmd(tasks["T2"]) is None
    assert findings.task_cmd(SimpleNamespace(id="T1", owns=["a.py"])) is None
