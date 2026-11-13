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


# B188: git checkout with an unknown operand, a git subcommand that is not a literal (#726), subprocess cwd= (#728)

CO = "checkout operand {} may be a path; git switch takes only a branch"


@pytest.mark.parametrize("words,op", [
    (["git", "checkout", "$x"], "$x"),
    (["git", "checkout", "?"], "?"),
    (["git", "checkout", "src/$x"], "src/$x"),
    (["git", "checkout", "$(cat b)"], "$(cat b)"),
    (["git", "checkout", "`cat b`"], "`cat b`"),
    (["git", "checkout", "-q", "$x"], "$x"),
    (["git", "-C", "sub", "checkout", "$x"], "$x"),
])
def test_checkout_unknown_operand_may_be_a_path_726(words, op):
    assert guard_tools.targets(words) == ["?"]
    assert guard_tools.why(words) == CO.format(op)


def test_checkout_unknown_first_of_two_operands_726():
    assert guard_tools.targets(["git", "checkout", "$x", "$y"]) == ["$y", "?"]


@pytest.mark.parametrize("words", [
    ["git", "checkout", "-b", "$x"],
    ["git", "checkout", "-b", "new", "$x"],
    ["git", "checkout", "-B", "$x", "$y"],
    ["git", "checkout", "--detach", "$x"],
    ["git", "checkout", "--orphan", "$x"],
    ["git", "checkout", "main"],
    ["git", "switch", "$x"],
    ["git", "-C", "$X", "checkout", "a.py"],
    ["git", "-C", "$d", "status"],
])
def test_branch_and_start_point_operands_stay_no_write_726(words, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert guard_tools.targets(words) == []


@pytest.mark.parametrize("words,want", [
    (["git", "checkout", "$x", "--", "src/a.py"], ["src/a.py"]),
    (["git", "checkout", "--", "$x"], ["$x"]),
    (["git", "checkout", "--ours", "$x"], ["$x"]),
    (["git", "checkout", "~/x"], ["~/x"]),
    (["git", "restore", "$x"], ["$x"]),
    (["git", "restore", "?"], ["?"]),
])
def test_path_operands_keep_their_word_726(words, want):
    assert guard_tools.targets(words) == want


@pytest.mark.parametrize("words,sub", [
    (["git", "$s", "x"], "$s"),
    (["git", "?", "x"], "?"),
    (["git", "-C", "d", "$s"], "$s"),
    (["git", "${S}"], "${S}"),
])
def test_unknown_subcommand_is_unknown_726(words, sub):
    assert guard_tools.targets(words) == ["?"]
    assert guard_tools.why(words) == f"subcommand {sub} is not a literal"


@pytest.mark.parametrize("code,why", [
    ('subprocess.run(["git", "checkout", p])', "subprocess argument 3 is not a string literal"),
    ('subprocess.run(["git", p, "src/a.py"])', "subprocess argument 2 is not a string literal"),
    ("os.system('git checkout \"$x\"')", ""),
    ("os.system('git \"$s\" x')", ""),
])
def test_unknown_checkout_operand_or_subcommand_in_scripts_726(code, why):
    assert py(code) == ["?"]
    assert guard_tools.unresolved() == why


@pytest.mark.parametrize("code", [
    'subprocess.run(["git", "checkout", "-b", p])',
    'subprocess.run(["git", "switch", p])',
    "os.system('git switch \"$b\"')",
])
def test_branch_forms_in_scripts_still_pass_726(code):
    assert py(code) == []


@pytest.mark.parametrize("code,want", [
    ('subprocess.run(["rm", "a.py"], cwd="src")', ["src/a.py"]),
    ('subprocess.run(["rm", "a.py"], check=True, cwd="src")', ["src/a.py"]),
    ('subprocess.Popen(["rm", "a.py"], cwd="src")', ["src/a.py"]),
    ('subprocess.run("rm a.py", shell=True, cwd="src")', ["src/a.py"]),
    ('subprocess.run(["rm", "a.py"], cwd="/abs/d")', ["/abs/d/a.py"]),
    ('subprocess.run(["rm", "/abs/a.py"], cwd="src")', ["/abs/a.py"]),
    ('D = "src"\nsubprocess.run(["rm", "a.py"], cwd=D)', ["src/a.py"]),
    ('subprocess.run(["rm", "a.py"], cwd=os.path.join("src", "lib"))', ["src/lib/a.py"]),
    ('subprocess.run(["git", "clean", "-fd"], cwd="src")', ["src/?"]),
    ('subprocess.run(["git", "reset", "--hard"], cwd="src")', ["src"]),
    ('subprocess.run(["tar", "xf", "a.tar"], cwd="src")', ["src/"]),
    ('subprocess.run(["git", "-C", "lib", "checkout", "--", "a.py"], cwd="src")', ["src/lib/a.py"]),
    ('os.system("rm a.py")', ["a.py"]),
])
def test_literal_cwd_resolves_relative_targets_728(code, want):
    assert py(code) == want
    assert guard_tools.unresolved() == ""


@pytest.mark.parametrize("code", [
    'subprocess.run(["rm", "a.py"], cwd=p)',
    'subprocess.run(["rm", "a.py"], cwd=f"src/{p}")',
    'subprocess.run(["rm", "a.py"], cwd="~/x")',
    'subprocess.run(["rm", "a.py"], cwd="")',
])
def test_unknown_cwd_makes_relative_target_unknown_728(code):
    assert py(code) == ["?"]
    assert guard_tools.unresolved() == "subprocess cwd= is not a string literal"


@pytest.mark.parametrize("code,want", [
    ('subprocess.run(["rm", "/abs/a.py"], cwd=p)', ["/abs/a.py"]),
    ('subprocess.run(["git", "status"], cwd=p)', []),
])
def test_unknown_cwd_keeps_absolute_and_empty_targets_728(code, want):
    assert py(code) == want
    assert guard_tools.unresolved() == ""


def test_argument_cause_comes_before_cwd_728():
    assert py('subprocess.run(["rm", p], cwd=p)') == ["?"]
    assert guard_tools.unresolved() == "subprocess argument 2 is not a string literal"


def test_checkout_operand_looked_up_in_cwd_728(tmp_path, monkeypatch):
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("x = 1\n")
    monkeypatch.chdir(tmp_path)
    assert py('subprocess.run(["git", "checkout", "a.py"], cwd="src")') == ["src/a.py"]
    assert py('subprocess.run(["git", "checkout", "a.py"])') == []
    assert py('subprocess.run(["git", "checkout", "a.py"], cwd=p)') == []
    assert guard_tools.targets(["git", "checkout", "src/a.py"]) == ["src/a.py"]
