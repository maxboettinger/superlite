"""#493: finish warns when the default branch moved in files the run owns."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))

import finish  # noqa: E402

TAIL = "; merge {ref} into this branch before shipping (finishing skill: conflict step)"


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def commit(cwd, files, msg):
    for name, text in files.items():
        p = cwd / name
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text)
    git(cwd, "add", "-A")
    git(cwd, "commit", "-q", "-m", msg)


def setup(tmp_path):
    main = tmp_path.resolve() / "repo"
    main.mkdir()
    git(main, "init", "-q", "-b", "main")
    git(main, "config", "user.name", "t")
    git(main, "config", "user.email", "t@t")
    commit(main, {"src/a.py": "a\n", "src/b.py": "b\n", "docs/d.md": "d\n"}, "init")
    base = git(main, "rev-parse", "HEAD")
    wt = main / ".claude" / "worktrees" / "run"
    git(main, "worktree", "add", "-q", "-b", "superlite/run", str(wt), "HEAD")
    (wt / ".superlite").mkdir()
    return main, wt, base


def line(ref, n, k, base, files):
    return (f"WARNING: {ref} moved in {n} file{'s' if n != 1 else ''} this run owns ({k} commit{'s' if k != 1 else ''} "
            f"since this branch left it at {base[:10]}): {files}" + TAIL.format(ref=ref))


def test_moved_in_owned_file_warns(tmp_path):
    main, wt, base = setup(tmp_path)
    commit(wt, {"src/a.py": "a2\n"}, "run edits a")
    commit(main, {"src/a.py": "a3\n", "docs/d.md": "d2\n"}, "main edits a and d")
    assert finish.moved_lines(wt / ".superlite") == [line("main", 1, 1, base, "src/a.py")]


def test_plan_owns_count_without_a_branch_change(tmp_path):
    main, wt, base = setup(tmp_path)
    plan = wt / "plan.md"
    plan.write_text("# P\n\n### T1 a\n**Owns:** src/b.py, src/new.py\n", encoding="utf-8")
    commit(main, {"src/b.py": "b2\n"}, "one")
    commit(main, {"src/c.py": "c\n"}, "two")
    assert finish.moved_lines(wt / ".superlite", str(plan)) == [line("main", 1, 2, base, "src/b.py")]


def test_uncommitted_tracked_change_counts(tmp_path):
    main, wt, base = setup(tmp_path)
    (wt / "src" / "b.py").write_text("b-dirty\n")
    commit(main, {"src/b.py": "b2\n"}, "main edits b")
    assert finish.moved_lines(wt / ".superlite") == [line("main", 1, 1, base, "src/b.py")]


def test_nothing_moved_or_disjoint_is_quiet(tmp_path):
    main, wt, base = setup(tmp_path)
    commit(wt, {"src/a.py": "a2\n"}, "run edits a")
    assert finish.moved_lines(wt / ".superlite") == []
    commit(main, {"docs/d.md": "d2\n"}, "main edits d only")
    assert finish.moved_lines(wt / ".superlite") == []


def test_merged_default_branch_is_quiet(tmp_path):
    main, wt, base = setup(tmp_path)
    plan = wt / "plan.md"
    plan.write_text("# P\n\n### T1 a\n**Owns:** src/b.py\n", encoding="utf-8")
    commit(main, {"src/b.py": "b2\n"}, "main edits b")
    assert finish.moved_lines(wt / ".superlite", str(plan)) == [line("main", 1, 1, base, "src/b.py")]
    git(wt, "merge", "-q", "--no-edit", "main")
    assert finish.moved_lines(wt / ".superlite", str(plan)) == []


def test_origin_same_commit_gives_one_line(tmp_path):
    main, wt, base = setup(tmp_path)
    commit(wt, {"src/a.py": "a2\n"}, "run edits a")
    commit(main, {"src/a.py": "a3\n"}, "main edits a")
    git(main, "update-ref", "refs/remotes/origin/main", git(main, "rev-parse", "HEAD"))
    git(main, "symbolic-ref", "refs/remotes/origin/HEAD", "refs/remotes/origin/main")
    assert finish.moved_lines(wt / ".superlite") == [line("main", 1, 1, base, "src/a.py")]


def test_origin_ahead_of_local_gets_its_own_line(tmp_path):
    main, wt, base = setup(tmp_path)
    commit(wt, {"src/a.py": "a2\n"}, "run edits a")
    commit(main, {"src/a.py": "a3\n"}, "main edits a")
    git(main, "update-ref", "refs/remotes/origin/main", git(main, "rev-parse", "HEAD"))
    git(main, "reset", "-q", "--hard", base)
    assert finish.moved_lines(wt / ".superlite") == [line("origin/main", 1, 1, base, "src/a.py")]


def test_many_files_are_cut(tmp_path):
    main, wt, base = setup(tmp_path)
    names = {f"src/m{i}.py": "x\n" for i in range(7)}
    commit(wt, names, "run adds seven")
    commit(main, {k: "y\n" for k in names}, "main adds the same seven")
    got = finish.moved_lines(wt / ".superlite")
    assert got == [line("main", 7, 1, base, "src/m0.py, src/m1.py, src/m2.py, src/m3.py, src/m4.py (+2 more)")]


def test_outside_git_is_quiet(tmp_path):
    (tmp_path / ".superlite").mkdir()
    assert finish.moved_lines(tmp_path / ".superlite") == []


def test_summary_prints_the_warning_before_the_last_line(tmp_path):
    main, wt, base = setup(tmp_path)
    commit(wt, {"src/a.py": "a2\n"}, "run edits a")
    commit(main, {"src/a.py": "a3\n"}, "main edits a")
    sd = wt / ".superlite"
    (sd / "progress.md").write_text(f"- start {base}\n", encoding="utf-8")
    lines = finish.summary(str(sd / "progress.md"), str(sd / "incidents.jsonl")).splitlines()
    assert line("main", 1, 1, base, "src/a.py") in lines
    assert lines[-1].startswith("next: sl orchestrator end")
