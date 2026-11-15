"""#847: run_tests --affected [--base REV] [--files F ...] runs the tests testcmd.select_affected picks."""
import json
import os
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
CFG = {"language": "python", "lock": False,
       "test": "echo FULL > .superlite/got.txt; echo '1 passed'",
       "test_file": "printf '%s\\n' {files} > .superlite/got.txt; echo '1 passed'"}
FILES = {
    "src/calc/adder.py": "def add(a, b):\n    return a + b\n",
    "src/calc/orphan.py": "X = 1\n",
    "tests/conftest.py": "",
    "tests/test_adder.py": "from calc.adder import add\n\n\ndef test_add():\n    assert add(1, 2) == 3\n",
    "tests/test_misc.py": "def test_true():\n    assert True\n",
}
PLAN = """# Plan

### T1 adder
**Owns:** src/calc/adder.py, tests/test_adder.py

### T2 misc
**Owns:** src/calc/orphan.py, tests/test_misc.py
"""
GIT_ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}


def git(root, *args):
    return subprocess.run(["git", "-c", "user.name=t", "-c", "user.email=t@example.com", *args], cwd=root, check=True,
                          capture_output=True, text=True, env=GIT_ENV).stdout.strip()


def repo(tmp_path):
    root = tmp_path / "repo"
    for rel, text in FILES.items():
        (root / rel).parent.mkdir(parents=True, exist_ok=True)
        (root / rel).write_text(text, encoding="utf-8")
    git(root, "init", "-q")
    (root / ".git" / "info").mkdir(parents=True, exist_ok=True)
    (root / ".git" / "info" / "exclude").write_text(".superlite/\n", encoding="utf-8")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "base")
    (root / ".superlite").mkdir()
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps(CFG), encoding="utf-8")
    (root / ".superlite" / "plan.md").write_text(PLAN, encoding="utf-8")
    return root


def rt(cwd, *args, root=None):
    sl = Path(root or cwd) / ".superlite"
    return subprocess.run([sys.executable, str(RUN_TESTS), *args, "--log", str(sl / "incidents.jsonl"),
                           "--ledger", str(sl / "ledger.md"), "--summary", str(sl / "test-summary.json")],
                          cwd=cwd, capture_output=True, text=True, timeout=120)


def summary(root):
    return json.loads((root / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def got(root):
    p = root / ".superlite" / "got.txt"
    return p.read_text(encoding="utf-8").splitlines() if p.exists() else None


def edit(root, rel):
    with open(root / rel, "a", encoding="utf-8") as f:
        f.write("# changed\n")


def test_affected_runs_the_tests_a_change_touches(tmp_path):
    root = repo(tmp_path)
    edit(root, "src/calc/adder.py")
    r = rt(root, "--affected")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/test_adder.py"]
    assert "run_tests: --affected: 1 changed, 1 selected (base " in r.stderr
    s = summary(root)
    assert s["mode"] == "fast"
    assert s["affected"] == {"base": git(root, "rev-parse", "HEAD"), "changed": 1, "selected": ["tests/test_adder.py"],
                             "reasons": {"tests/test_adder.py": "name"}, "untested": []}


def test_files_replace_git_changes(tmp_path):
    root = repo(tmp_path)
    r = rt(root, "--affected", "--files", "tests/test_misc.py")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/test_misc.py"]
    assert "run_tests: --affected: 1 changed, 1 selected (--files)" in r.stderr
    assert summary(root)["affected"]["base"] is None


def test_files_from_a_subfolder_are_read_from_there(tmp_path):
    root = repo(tmp_path)
    r = rt(root / "tests", "--affected", "--files", "test_misc.py", root=root)
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/test_misc.py"]


def test_nothing_selected_exits_2_and_names_the_untested_files(tmp_path):
    root = repo(tmp_path)
    edit(root, "src/calc/orphan.py")
    r = rt(root, "--affected")
    assert r.returncode == 2, r.stderr
    assert ("--affected: no test covers the change; untested: src/calc/orphan.py; "
            "write a test or run --fast PATHS") in r.stderr
    assert got(root) is None
    assert "untested: src/calc/orphan.py" in summary(root)["error"]


def test_no_change_exits_2(tmp_path):
    root = repo(tmp_path)
    r = rt(root, "--affected")
    assert r.returncode == 2
    assert "--affected: no changed files since " in r.stderr
    assert got(root) is None


def test_shared_setup_change_runs_the_whole_suite(tmp_path):
    root = repo(tmp_path)
    edit(root, "tests/conftest.py")
    r = rt(root, "--affected")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["FULL"]
    assert "run_tests: --affected: tests/conftest.py changed: the whole suite runs" in r.stderr
    s = summary(root)
    assert s["mode"] == "full" and s["affected"]["trigger"] == "tests/conftest.py"


def test_bad_base_exits_2(tmp_path):
    root = repo(tmp_path)
    r = rt(root, "--affected", "--base", "no-such-rev")
    assert r.returncode == 2
    assert "--affected: cannot diff against no-such-rev" in r.stderr
    assert got(root) is None


def test_base_and_files_need_affected(tmp_path):
    root = repo(tmp_path)
    r = rt(root, "--fast", "tests/test_misc.py", "--base", "HEAD")
    assert r.returncode == 2 and "--base needs --affected" in r.stderr
    r = rt(root, "--fast", "tests/test_misc.py", "--files", "src/calc/adder.py")
    assert r.returncode == 2 and "--files needs --affected" in r.stderr
    assert got(root) is None


def test_explicit_base_reaches_back(tmp_path):
    root = repo(tmp_path)
    edit(root, "src/calc/adder.py")
    git(root, "commit", "-qam", "change adder")
    r = rt(root, "--affected", "--base", "HEAD~1")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/test_adder.py"]


def test_task_keeps_its_own_files(tmp_path):
    root = repo(tmp_path)
    edit(root, "src/calc/adder.py")
    edit(root, "tests/test_misc.py")
    r = rt(root, "--affected", "--task", "T1", "--plan", ".superlite")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/test_adder.py"]
    assert summary(root)["affected"]["changed"] == 1


def test_task_base_is_the_run_start_so_a_checkpointed_change_still_counts(tmp_path):
    root = repo(tmp_path)
    start = git(root, "rev-parse", "HEAD")
    edit(root, "src/calc/adder.py")
    git(root, "commit", "-qam", "T1 checkpoint")
    cp = git(root, "rev-parse", "HEAD")
    (root / ".superlite" / "checkpoints.json").write_text(json.dumps(
        {"base": start, "head": start,
         "entries": [{"task": "T1", "sha": cp, "title": "T1", "files": ["src/calc/adder.py"]}]}), encoding="utf-8")
    r = rt(root, "--affected", "--task", "T1", "--plan", ".superlite")
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/test_adder.py"]
    assert summary(root)["affected"]["base"] == start
    r = rt(root, "--affected")
    assert r.returncode == 2
    assert "--affected: no changed files since " + cp[:12] in r.stderr


def test_background_run_passes_affected_through(tmp_path):
    root = repo(tmp_path)
    r = rt(root, "--affected", "--files", "tests/test_misc.py", "--background")
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip().splitlines()[-1].startswith("wait: ")
    path = r.stdout.split("summary: ", 1)[1].splitlines()[0].strip()
    w = rt(root, "--wait", path, "--timeout", "60")
    assert w.returncode == 0, w.stderr
    assert got(root) == ["tests/test_misc.py"]


def test_files_equals_spelling_from_a_subfolder_is_read_from_there(tmp_path):
    root = repo(tmp_path)
    r = rt(root / "tests", "--affected", "--files=test_misc.py", root=root)
    assert r.returncode == 0, r.stderr
    assert got(root) == ["tests/test_misc.py"]


def test_to_root_tolerates_a_namespace_without_files(tmp_path, monkeypatch):
    import argparse
    import run_tests
    root, sub = tmp_path / "proj", tmp_path / "proj" / "sub"
    sub.mkdir(parents=True)
    monkeypatch.chdir(tmp_path)
    argv = ["--full"]
    run_tests.to_root(argparse.Namespace(also=[], fast=None), argv, str(sub), str(root))
    assert argv == ["--full"]
    os.chdir(tmp_path)
