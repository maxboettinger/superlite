import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import guard_tools  # noqa: E402

HEAD = "import os, subprocess, sys\np = input()\n"


def py(code):
    return guard_tools.targets(["python3", "-c", HEAD + code])


@pytest.mark.parametrize("code", [
    'subprocess.run(["git", "show", f"HEAD:{p}"])',
    'subprocess.run(["git", "show", "HEAD:" + p])',
    'subprocess.check_output(["wc", "-c", str(p)])',
    'subprocess.run(["git", "show", p], capture_output=True, text=True)',
    'subprocess.Popen(["git", "log", "--format=%H", f"{p}..HEAD"])',
    'subprocess.run(["git", "show", d["k]"]])',
    'subprocess.run(["bash", p], input="{}")',
    'subprocess.run(["python3", p])',
    'subprocess.run(["python3", "-c", "print(1)", p])',
    'subprocess.run(["timeout", p, "git", "status"])',
    'subprocess.run(\n    ["git", "diff", "--stat", p],\n    check=True,\n)',
    'HOOK = "hooks/x"\nsubprocess.run([HOOK, "--flag"])',
])
def test_dynamic_argument_judged_by_program(code):
    assert py(code) == []
    assert guard_tools.unresolved() == ""


@pytest.mark.parametrize("code,why", [
    ('subprocess.run([p, "x"])', "subprocess program is not a string literal"),
    ('subprocess.run([sys.executable, "-c", "print(1)"])', "subprocess program is not a string literal"),
    ('subprocess.run(p, shell=True)', "subprocess program is not a string literal"),
    ('subprocess.run(f"git show {p}", shell=True)', "subprocess program is not a string literal"),
    ('os.system("git show " + p)', "subprocess program is not a string literal"),
    ('from subprocess import run\nrun(p)', "subprocess program is not a string literal"),
    ('subprocess.run(["cp", "a", p])', "subprocess argument 3 is not a string literal"),
    ('subprocess.run(["rm", f"src/{p}"])', "subprocess argument 2 is not a string literal"),
    ('subprocess.run(["python3", "-c", p])', "subprocess argument 3 is not a string literal"),
    ('subprocess.run(["bash", "-c", p])', "subprocess argument 3 is not a string literal"),
    ('subprocess.run(["bash", p, "x"])', "subprocess argument 2 is not a string literal"),
    ('subprocess.run(["node", p, "-e", "1"])', "subprocess argument 2 is not a string literal"),
    ('subprocess.run(["bash", *sys.argv[1:]])', "subprocess argument 2 is not a string literal"),
    ('subprocess.run(["git", "show"] + sys.argv[1:])', "subprocess argument 3 is not a string literal"),
    ('subprocess.run(["env", p, "x"])', "subprocess argument 2 is not a string literal"),
    ('subprocess.run(["find", p, "-name", "x"])', "subprocess argument 2 is not a string literal"),
])
def test_unknown_names_the_cause(code, why):
    assert py(code) == ["?"]
    assert guard_tools.unresolved() == why


@pytest.mark.parametrize("argv,shell", [
    ('["git", "checkout", f"{p}"]', 'git checkout "$x"'),
    ('["git", "show", f"{p}:a"]', 'git show "$x"'),
    ('["rm", p]', 'rm "$x"'),
    ('["cp", "a", p]', 'cp a "$x"'),
])
def test_same_targets_as_shell_word(argv, shell):
    assert py(f"subprocess.run({argv})") == py(f"os.system({shell!r})")


@pytest.mark.parametrize("shell", ['env "$P" x', 'bash "$o" "$c"', 'python3 -c "$X"', 'find . "$o"', 'perl "$o" "$c"'])
def test_shell_word_that_may_run_text_is_unknown(shell):
    assert py(f"os.system({shell!r})") == ["?"]


@pytest.mark.parametrize("shell", ['nohup ./run.sh "$a"', 'timeout 5 git show "$r"', 'bash -c "echo hi"'])
def test_shell_word_as_operand_still_passes(shell):
    assert py(f"os.system({shell!r})") == []


def test_reason_is_per_call():
    assert py('subprocess.run([p, "x"])') == ["?"]
    assert guard_tools.targets(["python3", "-c", "import sys\nopen(sys.stdin.readline() + '.md', 'w')"]) == ["?"]
    assert guard_tools.unresolved() == ""


def test_literal_lists_unchanged():
    assert py('subprocess.run(["rm", "src/a"])') == ["src/a"]
    assert py('subprocess.run(["bash", "-c", "rm src/a"], check=True)') == ["src/a"]
    assert py('subprocess.run(["git", "show", "HEAD:src/a.py"])') == []
