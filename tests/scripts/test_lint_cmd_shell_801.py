"""#801: lint rejects a Tests cmd= that is not valid shell."""
from __future__ import annotations

from test_lint_tests_cmd_475 import issues_of, project


def shell_issues(p):
    return [i for i in issues_of(p)[0] if i.startswith("TESTS: T1 cmd=")]


def test_prose_after_cmd_rejected(tmp_path):
    p = project(tmp_path, tests="slow cmd=swift test --filter X (then FOO=off swift test --triple arm64-apple-ios)")
    hits = shell_issues(p)
    assert len(hits) == 1 and hits[0].startswith("TESTS: T1 cmd= is not valid shell")


def test_joined_cmd_accepted(tmp_path):
    p = project(tmp_path, tests="slow cmd=swift test --filter X && xcodebuild build -destination 'generic/platform=iOS'")
    assert shell_issues(p) == []
    assert shell_issues(project(tmp_path, tests="fast cmd=bash tests/hooks/test.sh")) == []


def test_quoted_paren_accepted(tmp_path):
    assert shell_issues(project(tmp_path, tests="""fast cmd=python3 -c 'print("(x")'""")) == []


def test_draft_task_not_checked(tmp_path):
    p = project(tmp_path, tests="slow cmd=swift test --filter X (then FOO=off swift test)", status="draft")
    assert shell_issues(p) == []


def test_checked_without_test_command(tmp_path):
    p = project(tmp_path, tests="slow cmd=swift test --filter X (then FOO=off swift test)", marker=False)
    assert len(shell_issues(p)) == 1
