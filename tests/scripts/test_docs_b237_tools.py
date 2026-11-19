"""docs/tools.md rows name the B237 facts (#788 #789 #814 #878 #879 #882 #888 #894 #896)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"


def row(name):
    return next(ln for ln in TOOLS.splitlines() if ln.startswith(f"| `{name}` |"))


def check(name, *parts):
    r = row(name)
    missing = [p for p in parts if p not in r]
    assert not missing, (name, missing)


def src(name, *parts):
    t = (SCRIPTS / name).read_text(encoding="utf-8")
    missing = [p for p in parts if p not in t]
    assert not missing, (name, missing)


def test_backlog_row_names_github_not_found():
    check("backlog", "`not found: #N`", "read by number")


def test_backlog_rows_name_note_size_left_out_and_by():
    check("backlog", "of 2000 characters", "drops closed left-out issues")
    check("backlog", '"by" is required')


def test_commit_task_row():
    parts = ("import check skipped (__main__ runs the program)", "TimeoutExpired", "SUPERLITE_IMPORT_TIMEOUT")
    check("commit_task", *parts)
    src("commit_task.py", *parts)


def test_run_tests_and_trees_rows():
    check("trees", "tree index not updated", "kept at base")
    check("run_tests", "changed in the run root while the tests ran", "[run folder", "found no scheme or package", '"cwd"')
    src("trees.py", "tree index not updated")
    src("run_tests.py", "kept at base", "changed in the run root while the tests ran", "[run folder", "found no scheme or package", '"cwd"')


def test_finish_and_dispatch_rows():
    check("finish", "`archived:`", "dispatch-log.jsonl", "`Ruling:` lines")
    check("dispatch", "dispatch-log.jsonl")


def test_fleet_row_names_sign_in():
    check("fleet", "signed out", "600000")
