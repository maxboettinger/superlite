"""#475: lint rejects a task whose verify paths the project's test command cannot run, unless it names `cmd=`."""
from __future__ import annotations

import json
import subprocess
import sys

from test_plan_tools import SCRIPTS, pt

sys.path.insert(0, str(SCRIPTS))
import plan_tools  # noqa: E402


def project(tmp_path, owns="tests/hooks/test.sh", tests="fast", extra="", marker=True, status=""):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    (tmp_path / ".superlite").mkdir(exist_ok=True)
    if marker:
        (tmp_path / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    p = tmp_path / "plan.md"
    p.write_text("\n".join([
        "# Plan", "**Goal:** test.", "", "```mermaid", "flowchart LR", "  T1[a]", "  %% taskgraph", "```", "",
        "### T1 hook · Complexity 1", f"**Owns:** {owns}", f"**Tests:** {tests}", "**Components:** 1", "**LOC owned:** 20",
        *([f"**Status:** {status}"] if status else []), extra, ""]), encoding="utf-8")
    return p


def issues_of(p):
    plan = plan_tools.Plan.load(str(p))
    issues, warns = plan_tools.lint_plan(plan, plan_tools.build_parser().parse_args(["lint", "--plan", str(p)]))
    return [str(i) for i in issues], warns


def found(p):
    return [i for i in issues_of(p)[0] if i.startswith("TESTS:")]


def test_shell_test_in_python_project_is_an_issue(tmp_path):
    p = project(tmp_path)
    hits = found(p)
    assert len(hits) == 1
    assert "TESTS: T1 verifies with tests/hooks/test.sh" in hits[0]
    assert "cmd=bash tests/hooks/test.sh" in hits[0] and "(pytest)" in hits[0]
    cp = pt("lint", "--plan", p, "--stable")
    fix = cp.out.split("FIX:")[1]
    assert "T1" in fix and "TESTS:" in fix


def test_cmd_silences_it(tmp_path):
    p = project(tmp_path, tests="fast cmd=bash tests/hooks/test.sh")
    assert found(p) == []


def test_build_and_draft_skipped(tmp_path):
    assert found(project(tmp_path, tests="build")) == []


def test_draft_skipped(tmp_path):
    plan = plan_tools.Plan.load(str(project(tmp_path, status="draft")))
    assert plan.tasks[0].status == "draft"
    assert plan_tools.tests_issues(plan, tmp_path) == []


def test_python_tests_pass(tmp_path):
    assert found(project(tmp_path, owns="src/a.py, tests/test_a.py")) == []


def test_unknown_runner_checks_nothing(tmp_path):
    p = project(tmp_path, marker=False)
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "shell", "test": "bats tests"}), encoding="utf-8")
    assert found(p) == []


def test_no_root_is_empty(tmp_path):
    plan = plan_tools.Plan.load(str(project(tmp_path)))
    assert plan_tools.tests_issues(plan, None) == []


def test_platform_slow_cmd_counts_as_slow(tmp_path):
    p = project(tmp_path, owns="src/a.py, tests/test_a.py", tests="slow cmd=xcodebuild build -destination 'generic/platform=iOS'",
                extra="Code behind `#if os(iOS)` needs the iOS build.")
    assert not [w for w in issues_of(p)[1] if "PLATFORM:" in w]


def test_tests_issues_contract_returns_issue_list(tmp_path):
    p = project(tmp_path)
    plan = plan_tools.Plan.load(str(p))
    got = plan_tools.tests_issues(plan, tmp_path)
    assert got and all(isinstance(i, plan_tools.Issue) for i in got)
    assert plan_tools.tests_issues.__annotations__["return"] == "list[Issue]"
