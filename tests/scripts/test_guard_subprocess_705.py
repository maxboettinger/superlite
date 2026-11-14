import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "block-coordinator-edits"
BASH = shutil.which("bash")
HEAD = "import os, subprocess, sys\np = input()\n"
NOTE = ("A subprocess call whose program is not a string literal (`[prog, ...]`) is judged unknown; a list name bound "
        "once to a literal list (used only as the call's argument or a `*` splat) counts as that list, `sys.executable` "
        "as python3, and a later argument that is not a literal is judged like an unknown shell variable.")


@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "P"
    (p / ".superlite" / "scratch").mkdir(parents=True)
    (p / ".superlite" / "pool.json").write_text("{}")
    (p / "src").mkdir()
    (p / "src" / "a.py").write_text("x = 1\n")
    return p


def hook(proj, payload):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    env.update(CLAUDE_PROJECT_DIR=str(proj), SUPERLITE_HOME=str(proj.parent / "home"))
    return subprocess.run([BASH, str(HOOK)], input=json.dumps(payload), capture_output=True, text=True, env=env, cwd=proj)


def bash(proj, cmd):
    return hook(proj, {"tool_name": "Bash", "tool_input": {"command": cmd}})


def heredoc(code):
    return f"python3 - <<'EOF'\n{HEAD}{code}\nEOF"


def word(r):
    return [ln for ln in r.stderr.splitlines() if ln.startswith("Unresolved word: ")]


@pytest.mark.parametrize("code", [
    'subprocess.run(["git", "show", f"HEAD:{p}"])',
    'subprocess.run(["git", "show", "HEAD:" + p], capture_output=True)',
    'subprocess.check_output(["wc", "-c", str(p)])',
])
def test_heredoc_read_with_dynamic_argument_passes(proj, code):
    assert bash(proj, heredoc(code)).returncode == 0


def test_scratch_script_with_dynamic_argument_passes(proj):
    (proj / ".superlite" / "scratch" / "m.py").write_text(HEAD + 'subprocess.run(["git", "show", f"HEAD:{p}"])\n')
    assert bash(proj, "python3 .superlite/scratch/m.py").returncode == 0


def test_program_name_blocked_names_cause(proj):
    r = bash(proj, heredoc('subprocess.run([p, "x"])'))
    assert r.returncode == 2
    assert word(r) == ["Unresolved word: ? (from python3: subprocess program is not a string literal)"]


def test_dynamic_destination_names_argument(proj):
    r = bash(proj, heredoc('subprocess.run(["cp", "a", p])'))
    assert r.returncode == 2
    assert word(r) == ["Unresolved word: ? (from python3: subprocess argument 3 is not a string literal)"]


def test_scratch_script_block_names_cause(proj):
    (proj / ".superlite" / "scratch" / "w.py").write_text(HEAD + 'subprocess.run(["rm", f"src/{p}"])\n')
    r = bash(proj, "python3 .superlite/scratch/w.py")
    assert r.returncode == 2
    assert word(r) == ["Unresolved word: ? (from python3: subprocess argument 2 is not a string literal)"]


def test_checkout_same_verdict_as_shell_word(proj):
    sub = bash(proj, heredoc('subprocess.run(["git", "checkout", f"{p}"])'))
    sh = bash(proj, heredoc("os.system('git checkout \"$x\"')"))
    assert sub.returncode == sh.returncode == 2


def test_unknown_open_keeps_plain_word(proj):
    r = bash(proj, "python3 - <<'EOF'\nimport sys\nopen(sys.stdin.readline() + '.md', 'w')\nEOF")
    assert r.returncode == 2
    assert word(r) == ["Unresolved word: ? (from python3)"]


def test_git_reason_unchanged(proj):
    r = bash(proj, 'git -c core.hooksPath="$(cat x)" commit -m x')
    assert all("subprocess" not in ln for ln in word(r))


def test_scratch_hint_names_non_literal_program(proj):
    w = hook(proj, {"tool_name": "Write", "tool_input": {"file_path": str(proj / "src" / "x.py")}})
    b = bash(proj, "cat > src/x.py <<'EOF'\nprint(1)\nEOF")
    for r in (w, b):
        assert r.returncode == 2
        lines = [ln for ln in r.stderr.splitlines() if ln.startswith("- A throwaway script")]
        assert len(lines) == 1 and lines[0].endswith(NOTE)


@pytest.mark.parametrize("cmd,line", [
    ('git checkout "$x"', "Unresolved word: ? (from git: checkout operand $x may be a path; git switch takes only a branch)"),
    ('git "$s" src/a.py', "Unresolved word: ? (from git: subcommand $s is not a literal)"),
    ('git restore "$x"', "Unresolved word: $x"),
])
def test_unknown_git_operand_blocks_726(proj, cmd, line):
    r = bash(proj, cmd)
    assert r.returncode == 2
    assert word(r) == [line]


@pytest.mark.parametrize("cmd", ["git checkout main", 'git checkout -b "$x"', 'git switch "$x"'])
def test_branch_forms_pass_726(proj, cmd):
    assert bash(proj, cmd).returncode == 0


def test_subprocess_cwd_resolves_relative_target_728(proj):
    r = bash(proj, heredoc('subprocess.run(["rm", "a.py"], cwd="src")'))
    assert r.returncode == 2
    assert r.stderr.splitlines()[-1] == "Blocked target: src/a.py"


def test_subprocess_cwd_into_state_folder_passes_728(proj):
    assert bash(proj, heredoc('subprocess.run(["rm", "x.json"], cwd=".superlite/scratch")')).returncode == 0


def test_subprocess_unknown_cwd_names_cause_728(proj):
    r = bash(proj, heredoc('subprocess.run(["rm", "a.py"], cwd=p)'))
    assert r.returncode == 2
    assert word(r) == ["Unresolved word: ? (from python3: subprocess cwd= is not a string literal)"]
