"""#493: other open superlite runs of the repository and the files they own (worktree.open_runs, overlaps, ensure lines)."""
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
SL = SCRIPTS / "sl"
sys.path.insert(0, str(SCRIPTS))

import worktree  # noqa: E402

PLAN = "# P\n\n### T1 a\n**Owns:** {owns}\n"
TAIL = "; the run that merges second merges the default branch first"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


def repo(tmp_path):
    main = tmp_path.resolve() / "repo"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    git(main, "config", "user.name", "t")
    git(main, "config", "user.email", "t@t")
    (main / "a.py").write_text("a\n")
    git(main, "add", ".")
    git(main, "commit", "-q", "-m", "init")
    return main


def add_plan(root, owns):
    plan = root / "docs" / "plan.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(PLAN.format(owns=owns), encoding="utf-8")
    (root / ".superlite").mkdir(exist_ok=True)
    (root / ".superlite" / "stable.json").write_text(json.dumps({"plan": str(plan)}), encoding="utf-8")
    return plan


def add_wt(main, name, owns=None):
    wt = main / ".claude" / "worktrees" / name
    git(main, "worktree", "add", "-q", "-b", f"superlite/{name}", str(wt), "HEAD")
    if owns is not None:
        add_plan(wt, owns)
    return wt


def backlog(main, *batches):
    (main / ".superlite").mkdir(exist_ok=True)
    (main / ".superlite" / "backlog.json").write_text(json.dumps({"batches": list(batches)}), encoding="utf-8")


def test_plan_run_found_with_its_owns(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine")
    other = add_wt(main, "other", owns="tests/test_x.py, src/x.py")
    assert worktree.open_runs(mine, here=mine) == [
        {"label": "superlite/other", "path": other.as_posix(), "files": ["src/x.py", "tests/test_x.py"]}]


def test_own_run_and_ended_runs_are_skipped(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine", owns="src/x.py")
    add_wt(main, "ended")
    assert worktree.open_runs(mine, here=mine) == []


def test_missing_plan_file_is_skipped(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine")
    other = add_wt(main, "other", owns="src/x.py")
    (other / "docs" / "plan.md").unlink()
    assert worktree.open_runs(mine, here=mine) == []


def test_open_backlog_batches_count_planned_and_shipped_do_not(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine")
    b9, b10 = add_wt(main, "b9"), add_wt(main, "b10")
    backlog(main,
            {"id": "B9", "state": "running", "worktree": str(b9), "files": ["src/y.py"]},
            {"id": "B10", "state": "shipped", "worktree": str(b10), "files": ["src/z.py"]},
            {"id": "B11", "state": "planned", "worktree": None, "files": ["src/w.py"]},
            {"id": "B12", "state": "parked", "worktree": str(main / "gone"), "files": ["src/v.py"]})
    assert worktree.open_runs(mine, here=mine) == [{"label": "B9 (running)", "path": b9.as_posix(), "files": ["src/y.py"]}]


def test_batch_files_and_plan_owns_merge(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine")
    b9 = add_wt(main, "b9", owns="src/x.py, src/y.py")
    backlog(main, {"id": "B9", "state": "needs_decision", "worktree": str(b9), "files": ["src/y.py", "docs/d.md"]})
    assert worktree.open_runs(mine, here=mine) == [
        {"label": "B9 (needs_decision)", "path": b9.as_posix(), "files": ["docs/d.md", "src/x.py", "src/y.py"]}]


def test_own_batch_is_skipped(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine")
    backlog(main, {"id": "B8", "state": "running", "worktree": str(mine), "files": ["a.py"]})
    assert worktree.open_runs(mine, here=mine) == []


def test_broken_backlog_json_is_ignored(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine")
    other = add_wt(main, "other", owns="src/x.py")
    (main / ".superlite").mkdir()
    (main / ".superlite" / "backlog.json").write_text("{not json", encoding="utf-8")
    assert [r["path"] for r in worktree.open_runs(mine, here=mine)] == [other.as_posix()]


def test_main_checkout_run_counts(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine")
    add_plan(main, "a.py")
    assert worktree.open_runs(mine, here=mine) == [{"label": "main", "path": main.as_posix(), "files": ["a.py"]}]


def test_no_repository_gives_nothing(tmp_path):
    assert worktree.open_runs(tmp_path, here=tmp_path) == []


@pytest.mark.parametrize("mine, theirs, want", [
    (["a.py", "src/b.py", "docs/x.md"], ["src/", "a.py"], ["a.py", "src/b.py"]),
    (["tests/test_*.py"], ["tests/test_x.py"], ["tests/test_*.py"]),
    (["tests/test_x.py"], ["tests/test_*.py"], ["tests/test_x.py"]),
    (["src/a*.py"], ["src/ab*.py"], ["src/a*.py"]),
    (["src/a*.py"], ["src/b*.py"], []),
    (["./a.py"], ["a.py"], ["./a.py"]),
    (["a.py", "a.py"], ["a.py"], ["a.py"]),
    (["a.py"], ["b.py"], []),
    ([], ["a.py"], []),
])
def test_overlaps(mine, theirs, want):
    assert worktree.overlaps(mine, theirs) == want


def test_shown_list_and_overlap_line():
    assert worktree.shown_list(["a", "b"]) == "a, b"
    assert worktree.shown_list([f"f{i}" for i in range(7)]) == "f0, f1, f2, f3, f4 (+2 more)"
    run = {"label": "B9 (running)", "path": "/r/wt", "files": ["a.py"]}
    assert worktree.overlap_line(run, ["a.py"]) == "OVERLAP: a.py also owned by open run B9 (running) at /r/wt" + TAIL


def ensure(cwd, topic):
    return subprocess.run([str(SL), "worktree", "ensure", topic], cwd=cwd, capture_output=True, text=True, timeout=60)


def test_ensure_without_plan_names_open_runs(tmp_path):
    main = repo(tmp_path)
    other = add_wt(main, "other", owns="src/x.py, src/y.py")
    one = add_wt(main, "one", owns="lib/z.py")
    r = ensure(main, "new thing")
    assert r.returncode == 0
    assert r.stdout.strip() == (main / ".claude" / "worktrees" / "superlite-new-thing").as_posix()
    hint = "; keep your plan's Owns off them (plan lint warns on a shared file)"
    lines = [ln for ln in r.stderr.splitlines() if "open run" in ln]
    assert lines == [f"worktree: open run superlite/one at {one.as_posix()} owns 1 file: lib/z.py" + hint,
                     f"worktree: open run superlite/other at {other.as_posix()} owns 2 files: src/x.py, src/y.py" + hint]


def test_ensure_with_plan_warns_only_on_overlap(tmp_path):
    main = repo(tmp_path)
    mine = add_wt(main, "mine", owns="src/x.py, docs/m.md")
    other = add_wt(main, "other", owns="src/x.py, src/y.py")
    add_wt(main, "third", owns="lib/z.py")
    r = ensure(mine, "mine")
    assert r.returncode == 0 and r.stdout.strip() == mine.as_posix()
    assert r.stderr.splitlines() == [
        f"worktree: WARNING: OVERLAP: src/x.py also owned by open run superlite/other at {other.as_posix()}" + TAIL]


def test_ensure_alone_prints_no_run_line(tmp_path):
    main = repo(tmp_path)
    r = ensure(main, "solo")
    assert r.returncode == 0 and "open run" not in r.stderr and "OVERLAP" not in r.stderr
