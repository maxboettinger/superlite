import sys
from pathlib import Path

import pytest

from test_block_coordinator_edits import bash, proj  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import guard_tools  # noqa: E402


@pytest.fixture
def code_proj(proj):  # noqa: F811
    (proj / "src").mkdir()
    (proj / "src" / "a.py").write_text("x\n")
    return proj


@pytest.mark.parametrize("words,want", [
    (["git", "restore", "--staged", "$o", "f"], ["f"]),  # $o may be -W
    (["git", "restore", "--staged", "?", "f"], ["f"]),
    (["git", "restore", "--staged", "$o", "src/a?.py"], ["src/a?.py"]),  # a literal glob path
    (["git", "checkout", "-b", "n", "$o", "a?"], ["a?", "."]),  # a glob path does not hide the -f reading
    (["git", "switch", "$o", "b"], ["."]),  # -f
    (["git", "switch", "-c", "n", "$o"], ["."]),
    (["git", "reset", "$o"], ["."]),  # --hard
    (["git", "reset", "-q", "$(cat m)"], ["."]),
    (["git", "-C", "sub", "reset", "$o"], ["sub"]),
    (["git", "checkout", "-b", "n", "$o"], ["."]),  # -f
    (["git", "checkout", "-B", "$x", "$y"], ["."]),
    (["git", "checkout", "--detach", "$x"], ["."]),
    (["git", "read-tree", "$o", "HEAD"], ["."]),  # -u
    (["git", "checkout-index", "$o"], ["."]),  # -a
    (["git", "reset", "--$o"], ["."]),  # an expansion in the option name
])
def test_unknown_option_word_writes(words, want, tmp_path, monkeypatch):  # #749
    monkeypatch.chdir(tmp_path)
    assert guard_tools.targets(words) == want


@pytest.mark.parametrize("words", [
    ["git", "switch", "$b"],
    ["git", "switch", "-c", "$b"],
    ["git", "switch", "-C", "$b"],
    ["git", "checkout", "-b", "$x"],
    ["git", "checkout", "--orphan", "$x"],
    ["git", "restore", "--staged", "$f"],
    ["git", "restore", "-s", "$s", "--staged", "f"],
    ["git", "reset", "--soft", "$c"],
    ["git", "reset", "--mixed", "$c"],
    ["git", "reset", "$c", "--", "f"],
    ["git", "reset", "src/$x"],
    ["git", "log", "$range"],
    ["git", "diff", "$a", "$b"],
    ["git", "status", "$x"],
])
def test_reading_git_refuses_passes(words, tmp_path, monkeypatch):  # #749
    monkeypatch.chdir(tmp_path)
    assert guard_tools.targets(words) == []


@pytest.mark.parametrize("words,want", [
    (["git", "checkout", "$x", "--", "src/a.py"], ["src/a.py"]),
    (["git", "checkout", "$x", "$y"], ["$y", "?"]),
    (["git", "restore", "$x"], ["$x"]),
])
def test_written_unknown_keeps_its_targets(words, want, tmp_path, monkeypatch):  # #749
    monkeypatch.chdir(tmp_path)
    assert guard_tools.targets(words) == want


@pytest.mark.parametrize("cmd", [
    'git restore --staged "$o" src/a.py',
    'git switch "$o" main',
    'git reset "$o"',
    'git checkout -b n "$o"',
    "python3 - <<'EOF'\nimport subprocess, sys\nsubprocess.run([\"git\", \"reset\", sys.argv[1]])\nEOF",
])
def test_hook_blocks_unknown_git_option(code_proj, cmd):  # #749
    assert bash(code_proj, cmd).returncode == 2, cmd


@pytest.mark.parametrize("cmd", [
    'git switch "$b"',
    'git reset --soft "$c"',
    'git restore --staged "$f"',
    'git log "$range"',
])
def test_hook_passes_git_readings_that_cannot_write(code_proj, cmd):  # #749
    assert bash(code_proj, cmd).returncode == 0, cmd
