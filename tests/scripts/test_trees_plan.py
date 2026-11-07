"""#303: trees.py clean and path take --plan P / --plan=P anywhere and work in P's checkout."""
from __future__ import annotations

import os
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402
import trees  # noqa: E402

SL = SCRIPTS / "sl"
USAGE = "usage: trees.py clean | path Tn [--plan P]"


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


def make_repo(path):
    path.mkdir(parents=True)
    git(path, "init", "-q")
    git(path, "config", "user.email", "t@t")
    git(path, "config", "user.name", "t")
    (path / ".git" / "info").mkdir(exist_ok=True)
    (path / ".git" / "info" / "exclude").write_text(".superlite/\n")
    (path / "src").mkdir()
    (path / "src" / "a.py").write_text("A = 1\n")
    git(path, "add", ".")
    git(path, "commit", "-qm", "base")
    (path / ".superlite").mkdir()
    return path


@pytest.fixture
def two(tmp_path, monkeypatch):
    run = make_repo(tmp_path / "run")
    other = make_repo(tmp_path / "other")
    monkeypatch.chdir(other)
    return run, other


def trees_of(repo):
    base = repo / ".superlite" / "trees"
    return sorted(p.name for p in base.iterdir() if p.is_dir()) if base.is_dir() else []


@pytest.mark.parametrize("argv", [
    ["clean", "--plan", "{run}/.superlite"],
    ["--plan", "{run}/.superlite", "clean"],
    ["clean", "--plan={run}/docs/plans/p.md"],
    ["--plan={run}", "clean"],
])
def test_clean_with_plan_works_in_plan_checkout(two, capsys, argv):
    run, other = two
    trees.prepare(run, "T1", ["src/a.py"])
    trees.prepare(other, "T1", ["src/a.py"])
    assert trees.main([a.format(run=run) for a in argv]) == 0
    assert capsys.readouterr().out.strip() == "removed 1"
    assert trees_of(run) == []
    assert trees_of(other) == ["T1"]


def test_path_with_plan_prints_plan_checkout_tree(two, capsys):
    run, _ = two
    assert trees.main(["path", "T3", "--plan", str(run / ".superlite")]) == 0
    assert capsys.readouterr().out.strip() == str((run / ".superlite" / "trees" / "T3").resolve())


def test_path_plan_before_command(two, capsys):
    run, _ = two
    assert trees.main([f"--plan={run / 'docs' / 'plans' / 'p.md'}", "path", "T2"]) == 0
    assert capsys.readouterr().out.strip() == str((run / ".superlite" / "trees" / "T2").resolve())


@pytest.mark.parametrize("argv", [["clean", "--plan"], ["clean", "--plan="], ["clean", "--plan", "--x"],
                                  ["path", "T1", "--plan"]])
def test_plan_without_value_is_usage_error(two, capsys, argv):
    _, other = two
    trees.prepare(other, "T1", ["src/a.py"])
    assert trees.main(argv) == 2
    cap = capsys.readouterr()
    assert USAGE in cap.err
    assert cap.out == ""
    assert trees_of(other) == ["T1"]


def test_plan_outside_any_checkout_keeps_cwd(two, tmp_path, capsys):
    _, other = two
    plan = tmp_path / "loose" / "plan.md"
    if state.git_root(plan):
        pytest.skip("tmp_path lies inside a git checkout")
    trees.prepare(other, "T1", ["src/a.py"])
    assert trees.main(["clean", "--plan", str(plan)]) == 0
    assert capsys.readouterr().out.strip() == "removed 1"
    assert trees_of(other) == []


def test_without_plan_unchanged(two, capsys):
    run, other = two
    trees.prepare(run, "T1", ["src/a.py"])
    trees.prepare(other, "T1", ["src/a.py"])
    assert trees.main(["clean"]) == 0
    assert capsys.readouterr().out.strip() == "removed 1"
    assert trees_of(run) == ["T1"]
    assert trees_of(other) == []
    assert trees.main(["path", "T4"]) == 0
    assert capsys.readouterr().out.strip() == str((other / ".superlite" / "trees" / "T4").resolve())
    assert trees.main(["bogus"]) == 2
    assert USAGE in capsys.readouterr().err


@pytest.mark.skipif(os.name == "nt", reason="bash launcher")
def test_sl_trees_clean_with_plan(two):
    run, _ = two
    trees.prepare(run, "T1", ["src/a.py"])
    r = subprocess.run([str(SL), "trees", "clean", "--plan", ".superlite"], cwd=run, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert r.stdout.strip() == "removed 1"
    assert trees_of(run) == []
