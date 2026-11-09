"""A --fast task tree keeps the files of unfinished sibling tasks at base."""
from __future__ import annotations

import json
import sys

sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[2] / "skills/subagent-driven-development/scripts"))

import next_tasks as nt  # noqa: E402
import run_tests as rt  # noqa: E402
from test_plan_tools import make_plan, run  # noqa: E402
from test_run_tests_plan_fallback import OUT, RUN_TESTS, git  # noqa: E402


def repo(tmp_path, files=("src/a.py", "src/b.py", "src/s.py", "src/c.py"), owns=("src/a.py", "src/b.py")):
    for f in files:
        p = tmp_path / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("base", encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".superlite/\n", encoding="utf-8")
    (tmp_path / "docs").mkdir()
    plan = make_plan(tmp_path / "docs", [{"id": "T1", "owns": owns[0]}, {"id": "T2", "owns": owns[1]}], name="p.md")
    (tmp_path / ".superlite").mkdir()
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")
    return plan


def call(tmp_path, plan, ledger, monkeypatch, task="T2"):
    monkeypatch.chdir(tmp_path)
    info = nt.parse_plan(str(plan))
    return rt.fast_overlay(".", task, info, str(ledger))


def test_fast_overlay_holds_unfinished_sibling_files(tmp_path, monkeypatch):
    plan = repo(tmp_path)
    (tmp_path / "src/a.py").write_text("new", encoding="utf-8")
    (tmp_path / "src/b.py").write_text("new", encoding="utf-8")
    (tmp_path / "README.md").write_text("r", encoding="utf-8")
    assert call(tmp_path, plan, tmp_path / ".superlite" / "l.md", monkeypatch) == (["README.md", "src/b.py"], ["src/a.py"])


def test_committed_sibling_files_are_overlaid(tmp_path, monkeypatch):
    plan = repo(tmp_path)
    (tmp_path / "src/a.py").write_text("new", encoding="utf-8")
    (tmp_path / "src/b.py").write_text("new", encoding="utf-8")
    (tmp_path / "README.md").write_text("r", encoding="utf-8")
    ledger = tmp_path / ".superlite" / "l.md"
    ledger.write_text("- commit T1 5e9dd8b464 x\n", encoding="utf-8")
    got = call(tmp_path, plan, ledger, monkeypatch)
    assert got == (["README.md", "src/a.py", "src/b.py"], []), got


def test_own_file_shared_with_a_sibling_is_overlaid(tmp_path, monkeypatch):
    plan = repo(tmp_path, owns=("src/s.py", "src/s.py"))
    (tmp_path / "src/s.py").write_text("new", encoding="utf-8")
    assert call(tmp_path, plan, tmp_path / ".superlite" / "l.md", monkeypatch) == (["src/s.py"], [])


def swift(tmp_path):
    cmd = f'{sys.executable} -c "print(\'{OUT}\')"'
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "swift", "test": cmd, "test_file": cmd, "isolate": True}), encoding="utf-8")


def test_fast_run_names_the_held_files(tmp_path):
    plan = repo(tmp_path)
    swift(tmp_path)
    (tmp_path / "src/a.py").write_text("new", encoding="utf-8")
    cp = run(RUN_TESTS, "--fast", "src/b.py", "--task", "T2", "--plan", plan, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert "; kept at base: 1 file of unfinished T1" in cp.err
    assert (tmp_path / ".superlite/trees/T2/src/a.py").read_text(encoding="utf-8") == "base"


def test_claimed_file_of_unfinished_sibling_is_held(tmp_path):
    plan = repo(tmp_path)
    swift(tmp_path)
    ledger = tmp_path / ".superlite" / "progress.md"
    ledger.write_text("- Ruling: T1 also commits src/c.py - why\n", encoding="utf-8")
    (tmp_path / "src/c.py").write_text("new", encoding="utf-8")
    cp = run(RUN_TESTS, "--fast", "src/b.py", "--task", "T2", "--plan", plan, "--ledger", ledger, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert (tmp_path / ".superlite/trees/T2/src/c.py").read_text(encoding="utf-8") == "base"
