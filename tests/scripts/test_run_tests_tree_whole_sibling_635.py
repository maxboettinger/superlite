"""A task tree takes a sibling that co-owns a changed file whole (#635)."""
from __future__ import annotations

import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "skills/subagent-driven-development/scripts"))

import next_tasks as nt  # noqa: E402
import run_tests as rt  # noqa: E402
from test_plan_tools import make_plan, run  # noqa: E402
from test_run_tests_fast_tree_siblings import call, swift  # noqa: E402
from test_run_tests_plan_fallback import RUN_TESTS, git  # noqa: E402


def setup(tmp_path, owns, files=("src/s.py", "src/n.py", "src/b.py", "src/a.py", "src/c.py")):
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("base", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".superlite/\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    plan = make_plan(tmp_path / "docs", [{"id": t, "owns": o} for t, o in owns], name="p.md")
    (tmp_path / ".superlite").mkdir()
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")
    return plan


def change(tmp_path, *names):
    for n in names:
        (tmp_path / "src" / n).write_text("new", encoding="utf-8")


def ledger(tmp_path):
    return tmp_path / ".superlite" / "l.md"


def test_shared_file_pulls_the_sibling_whole(tmp_path, monkeypatch):
    plan = setup(tmp_path, [("T1", "src/s.py, src/n.py"), ("T2", "src/s.py, src/b.py")], files=("src/s.py", "src/b.py"))
    change(tmp_path, "s.py", "n.py")
    assert call(tmp_path, plan, ledger(tmp_path), monkeypatch) == (["src/n.py", "src/s.py"], {})


def test_unshared_sibling_stays_held(tmp_path, monkeypatch):
    plan = setup(tmp_path, [("T1", "src/s.py, src/n.py"), ("T2", "src/s.py, src/b.py"), ("T3", "src/a.py")])
    change(tmp_path, "s.py", "n.py", "a.py")
    assert call(tmp_path, plan, ledger(tmp_path), monkeypatch) == (["src/n.py", "src/s.py"], {"src/a.py": ["T3"]})


def test_pull_is_transitive(tmp_path, monkeypatch):
    plan = setup(tmp_path, [("T1", "src/s.py, src/n.py"), ("T3", "src/n.py, src/c.py"), ("T2", "src/s.py")])
    change(tmp_path, "s.py", "n.py", "c.py")
    assert call(tmp_path, plan, ledger(tmp_path), monkeypatch) == (["src/c.py", "src/n.py", "src/s.py"], {})


def test_unchanged_shared_file_pulls_nothing(tmp_path, monkeypatch):
    plan = setup(tmp_path, [("T1", "src/s.py, src/n.py"), ("T2", "src/s.py, src/b.py")], files=("src/s.py", "src/b.py"))
    change(tmp_path, "n.py")
    assert call(tmp_path, plan, ledger(tmp_path), monkeypatch) == ([], {"src/n.py": ["T1"]})


def test_committed_sibling_is_not_pulled(tmp_path):
    plan = setup(tmp_path, [("T1", "src/s.py, src/n.py"), ("T2", "src/s.py, src/b.py")])
    led = ledger(tmp_path)
    led.write_text("- commit T1 5e9dd8b464 x\n", encoding="utf-8")
    info = nt.parse_plan(str(plan))
    assert rt.shared_siblings(["src/n.py", "src/s.py"], "T2", info, rt.ct.committed_tasks(str(led))) == {}


def test_shared_siblings_names_the_shared_path(tmp_path):
    plan = setup(tmp_path, [("T1", "src/s.py, src/n.py"), ("T2", "src/s.py, src/b.py")])
    info = nt.parse_plan(str(plan))
    assert rt.shared_siblings(["src/n.py", "src/s.py"], "T2", info, set()) == {"T1": "src/s.py"}


def test_fast_run_names_the_pulled_sibling(tmp_path):
    plan = setup(tmp_path, [("T1", "src/s.py, src/n.py"), ("T2", "src/s.py, src/b.py")])
    swift(tmp_path)
    change(tmp_path, "s.py", "n.py")
    cp = run(RUN_TESTS, "--fast", "src/b.py", "--task", "T2", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert "run_tests: T2's tree takes T1 whole: it shares src/s.py" in cp.err
    assert (tmp_path / ".superlite/trees/T2/src/n.py").read_text(encoding="utf-8") == "new"


def test_full_task_tree_takes_the_pulled_files(tmp_path):
    plan = setup(tmp_path, [("T1", "src/s.py, src/n.py"), ("T2", "src/s.py, src/b.py")])
    swift(tmp_path)
    change(tmp_path, "s.py", "n.py", "b.py")
    cp = run(RUN_TESTS, "--full", "--task", "T2", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert (tmp_path / ".superlite/trees/T2/src/n.py").read_text(encoding="utf-8") == "new"
    assert (tmp_path / ".superlite/trees/T2/src/b.py").read_text(encoding="utf-8") == "new"
