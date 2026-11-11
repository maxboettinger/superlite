"""#475: task_command, verify_paths, unrunnable in testcmd."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))

import testcmd  # noqa: E402

PY = {"language": "python", "python": True}


def test_task_command_plain():
    assert testcmd.task_command("fast cmd=bash tests/hooks/test.sh") == "bash tests/hooks/test.sh"
    assert testcmd.task_command("fast") is None


def test_task_command_strips_backticks():
    assert testcmd.task_command("fast cmd=`bash x/test.sh -q`") == "bash x/test.sh -q"


def test_task_command_inside_word_is_none():
    assert testcmd.task_command("fast mycmd=x") is None


def test_task_command_empty_is_none():
    assert testcmd.task_command("slow cmd=  ") is None


def test_verify_paths_cases():
    assert testcmd.verify_paths(["src/a.py", "tests/test_a.py", "docs/a.md"]) == ["tests/test_a.py"]
    assert testcmd.verify_paths(["hooks/x", "src/x_test.go"]) == ["src/x_test.go"]
    assert testcmd.verify_paths(["README.md", "tests/fixtures/a.json"]) == []
    assert testcmd.verify_paths(["tests/hooks/test.sh", "hooks/h.sh"]) == ["tests/hooks/test.sh"]


def test_unrunnable_cases():
    assert testcmd.unrunnable(PY, ["tests/hooks/test.sh", "tests/test_a.py"]) == ["tests/hooks/test.sh"]
    assert testcmd.unrunnable({"language": "go", "python": False}, ["x_test.go"]) == []
    assert testcmd.unrunnable(None, ["t.sh"]) == []


def test_unrunnable_glob_suffix():
    assert testcmd.unrunnable(PY, ["tests/*.sh"]) == ["tests/*.sh"]


def test_unrunnable_skips_non_code():
    assert testcmd.unrunnable(PY, ["tests/data.json", "tests/dir/"]) == []


def test_unrunnable_node():
    spec = {"language": "typescript", "python": False}
    assert testcmd.unrunnable(spec, ["t/a.test.ts", "t/b.sh"]) == ["t/b.sh"]
