import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import guard_tools  # noqa: E402

sys.path.insert(0, str(Path(__file__).resolve().parent))
from test_block_coordinator_edits import bash, proj  # noqa: E402,F401

FOLDER = "subprocess folder option (cwd, chdir, proc_open cwd) is not followed"
SHELL = "shell text changes folder (cd, pushd, popd)"
CP = "require('child_process')"


def t(*words):
    return guard_tools.targets(list(words))


@pytest.mark.parametrize("code", [
    f"{CP}.execSync('rm a.py', {{cwd: 'src'}})",
    f"const o = {{cwd: 'src'}}; {CP}.execSync('rm a.py', o)",
    f"{CP}.spawnSync('rm', ['a.py'], {{cwd: 'src'}})",
])
def test_js_cwd_makes_relative_unknown(code):
    assert t("node", "-e", code) == ["?"]
    assert guard_tools.unresolved() == FOLDER


def test_js_cwd_absolute_target_stays():
    assert t("node", "-e", f"{CP}.execSync('rm /abs/a.py', {{cwd: 'src'}})") == ["/abs/a.py"]


def test_js_process_cwd_call_changes_nothing():
    assert t("node", "-e", f"const d = process.cwd(); {CP}.execSync('rm a.py')") == ["a.py"]


@pytest.mark.parametrize("code", [
    'system("rm a.py", chdir: "src")',
    'require "open3"; Open3.capture2("rm a.py", chdir: "src")',
])
def test_ruby_chdir_makes_relative_unknown(code):
    assert t("ruby", "-e", code) == ["?"]


@pytest.mark.parametrize("code,want", [
    ('proc_open("rm a.py", [], $p, "src");', ["?"]),
    ('proc_open("rm a.py", [], $p, null);', ["a.py"]),
    ('proc_open("rm a.py", [], $p);', ["a.py"]),
])
def test_php_proc_open_cwd(code, want):
    assert t("php", "-r", code) == want


@pytest.mark.parametrize("code", [
    'import os; os.system("cd src && rm a.py")',
    'import subprocess; subprocess.run("cd src; rm a.py", shell=True)',
    'import subprocess; subprocess.run(["sh", "-c", "pushd src; rm a.py"])',
    'import os; os.system("(cd src && touch b) ; rm a.py")',
    'import os; os.system("{ cd src; } ; rm a.py")',
])
def test_cd_in_shell_text(code):
    out = t("python3", "-c", code)
    assert "?" in out and "a.py" not in out
    assert guard_tools.unresolved() == SHELL


def test_cd_after_target_and_absolute_target():
    assert t("python3", "-c", 'import os; os.system("rm a.py && cd src")') == ["a.py"]
    assert t("python3", "-c", 'import os; os.system("cd src && rm /abs/a.py")') == ["/abs/a.py"]


def test_cd_in_ruby_and_perl_shell_text():
    assert t("ruby", "-e", "`cd src && rm a.py`") == ["?"]
    assert t("perl", "-e", 'system("cd src && rm a.py")') == ["?"]


def test_python_cwd_literal_unchanged():
    assert t("python3", "-c", 'import subprocess; subprocess.run(["rm", "a.py"], cwd="src")') == ["src/a.py"]


def test_no_state_leaks_into_next_call():
    t("python3", "-c", 'import os; os.system("cd src && rm a.py")')
    t("node", "-e", f"{CP}.execSync('rm a.py', {{cwd: 'src'}})")
    assert t("python3", "-c", 'import os; os.system("rm a.py")') == ["a.py"]
    assert guard_tools.unresolved() == ""
    assert t("node", "-e", f"{CP}.execSync('rm a.py')") == ["a.py"]


def test_bash_walk_keeps_cd_reading(proj):  # noqa: F811
    r = bash(proj, "bash -c 'cd .superlite && rm -f x.txt'")  # the start commit's verdict: the judge's own walk, not guard_tools' shell text
    assert r.returncode == 2 and "Blocked target: x.txt" in r.stderr
    assert "folder (cd, pushd, popd)" not in r.stderr


@pytest.mark.parametrize("code", [
    'import os; os.system("if true; then cd src; fi; rm a.py")',
    'import os; os.system("for i in 1; do cd src; done; rm a.py")',
    'import os; os.system("! cd src; rm a.py")',
])
def test_cd_after_shell_keyword(code):
    assert t("python3", "-c", code) == ["?"]


def test_python_newline_escape_in_shell_text_splits_commands():
    assert t("python3", "-c", 'import os; os.system("cd src\\nrm a.py")') == ["?"]
    assert t("python3", "-c", 'import os; os.system("rm a.py\\nrm b.py")') == ["a.py", "b.py"]


def test_python_tab_escape_is_a_separator_not_a_letter():
    out = t("python3", "-c", 'import os; os.system("rm a\\tb.py")')
    assert out in (["a", "b.py"], ["?"])


def test_python_raw_string_keeps_its_backslashes():
    assert t("python3", "-c", 'import os; os.system(r"rm a\\nrm b.py")') == ["anrm", "b.py"]


def test_python_unreadable_escape_is_unknown():
    assert t("python3", "-c", 'import os; os.system("rm \\N{DIGIT ONE}.py")') == ["?"]


def test_node_newline_escape_in_shell_text():
    assert t("node", "-e", f"{CP}.execSync(\"cd src\\nrm a.py\")") == ["?"]
    assert t("node", "-e", f"{CP}.execSync(\"rm a.py\\nrm b.py\")") == ["a.py", "b.py"]


def test_node_process_chdir_makes_relative_unknown():
    assert t("node", "-e", f"process.chdir('src'); {CP}.execSync('rm a.py')") == ["?"]
    assert guard_tools.unresolved() == FOLDER


def test_perl_chdir_makes_relative_unknown():
    assert t("perl", "-e", 'chdir("src"); system("rm a.py")') == ["?"]


@pytest.mark.parametrize("code", [
    's = "docs/x"; from cfg import s; open(s + "/a.py", "w")',
    's = "docs/x"; import cfg as s; open(s + "/a.py", "w")',
    's = "docs/x"\nif 1: from cfg import s\nopen(s + "/a.py", "w")',
    's = "docs/x"\ntry: import cfg as s\nexcept Exception: pass\nopen(s + "/a.py", "w")',
])
def test_python_one_liner_import_rebinds_name(code):
    assert "?" in t("python3", "-c", code)
