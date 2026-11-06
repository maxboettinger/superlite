"""lint: an Owns entry equal to the build report is flagged; `lint --stable` prints HELD lines for held tasks."""
from __future__ import annotations

from test_plan_tools import PLAN_TOOLS, SCRIPTS, make_plan, run
from test_wave0 import PY, plan

ISSUE = "T1: Owns `{}` is the build report"


def lint(tmp_path, owns, *extra):
    p = make_plan(tmp_path, [{"id": "T1", "owns": owns}])
    return run(PLAN_TOOLS, "lint", *extra, "--plan", p, cwd=tmp_path)


def test_reserved_build_report_flagged(tmp_path):
    out = lint(tmp_path, "plan.build-report.md, tests/test_a.py").both
    assert ISSUE.format("plan.build-report.md") in out
    stable = lint(tmp_path, "plan.build-report.md, tests/test_a.py", "--stable").out
    assert "FIX" in stable and "T1" in stable.split("FIX", 1)[1]


def test_reserved_json_flagged(tmp_path):
    assert ISSUE.format("plan.build-report.json") in lint(tmp_path, "plan.build-report.json, tests/test_a.py").both


def test_plan_task_report_name_not_flagged(tmp_path):
    assert "is the build report" not in lint(tmp_path, "plan.report.md, tests/test_a.py").both


def test_reserved_with_note_and_ticks_flagged(tmp_path):
    assert ISSUE.format("plan.build-report.md") in lint(tmp_path, "`plan.build-report.md` (closing report)").both


def test_lint_stable_held_line(tmp_path):
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    sd = tmp_path / ".superlite"
    sd.mkdir(exist_ok=True)
    (sd / "progress.md").write_text("- commit T0 abcdef1234 skeleton\n- Hold T1: ssh sign-in\n", encoding="utf-8")
    out = run(SCRIPTS / "plan_tools.py", "lint", "--stable", "--plan", p, cwd=tmp_path).out
    lines = out.rstrip().splitlines()
    assert "HELD: T1 (ssh sign-in; `sl hold --release T1` puts it back)" in lines
    assert lines[-1] == "DISPATCH NOW: none"
    assert not any(ln.startswith("THEN LOG") and "T1" in ln for ln in lines)
    with open(sd / "progress.md", "a", encoding="utf-8") as f:
        f.write("- Release T1\n")
    again = run(SCRIPTS / "plan_tools.py", "lint", "--stable", "--plan", p, cwd=tmp_path).out
    last = again.rstrip().splitlines()[-1]
    assert "HELD:" not in again and last.startswith("DISPATCH NOW: T1")


def test_lint_stable_committed_held_task_does_not_block_dependents(tmp_path):
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    sd = tmp_path / ".superlite"
    sd.mkdir(exist_ok=True)
    (sd / "progress.md").write_text(
        "- commit T0 abcdef1234 skeleton\n- Hold T1: ssh sign-in\n- commit T1 abcdef2345 slug\n", encoding="utf-8")
    out = run(SCRIPTS / "plan_tools.py", "lint", "--stable", "--plan", p, cwd=tmp_path).out
    assert "HELD:" not in out
    assert out.rstrip().splitlines()[-1].startswith("DISPATCH NOW: T2")
