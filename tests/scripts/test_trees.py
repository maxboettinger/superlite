"""trees.py: isolated per-task test tree; run_tests --task uses it for compiled stacks."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import trees  # noqa: E402
import run_tests  # noqa: E402
import testcmd  # noqa: E402

PLAN = """# P

## Section A

### T1 first
**Owns:** src/a.py
**Produces:** x

### T2 second
**Owns:** src/b.py
**Produces:** y
"""


def git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args], check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    git(tmp_path, "init", "-q")
    git(tmp_path, "config", "user.email", "t@t")
    git(tmp_path, "config", "user.name", "t")
    (tmp_path / ".git" / "info").mkdir(exist_ok=True)
    (tmp_path / ".git" / "info" / "exclude").write_text(".superlite/\n")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "a.py").write_text("A = 1\n")
    (tmp_path / "src" / "b.py").write_text("B = 1\n")
    (tmp_path / "src" / "old.py").write_text("OLD = 1\n")
    (tmp_path / "plan.md").write_text(PLAN)
    git(tmp_path, "add", ".")
    git(tmp_path, "commit", "-qm", "base")
    return tmp_path


def test_base_follows_new_checkpoint(repo):
    assert trees.base_commit(repo) == git(repo, "rev-parse", "HEAD").strip()
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "checkpoints.json").write_text(json.dumps({"entries": [{"sha": "a1"}, {"sha": "b2"}]}))
    assert trees.base_commit(repo) == "b2"


def test_sibling_half_edit_invisible(repo):
    (repo / "src" / "a.py").write_text("A = (\n")  # T1 half-edited: syntax error
    (repo / "src" / "b.py").write_text("B = 2\n")
    tree = trees.prepare(repo, "T2", ["src/b.py"])
    r = subprocess.run([sys.executable, "-c", "import src.a, src.b"], cwd=tree, capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
    assert (tree / "src" / "a.py").read_text() == "A = 1\n"


def test_own_edit_visible(repo):
    (repo / "src" / "b.py").write_text("B = 2\n")
    (repo / "src" / "new.py").write_text("N = 1\n")
    tree = trees.prepare(repo, "T2", ["src/b.py", "src/new.py"])
    assert tree == repo / ".superlite" / "trees" / "T2"
    assert (tree / "src" / "b.py").read_text() == "B = 2\n"
    assert (tree / "src" / "new.py").read_text() == "N = 1\n"


def test_own_delete_applied(repo):
    (repo / "src" / "old.py").unlink()
    tree = trees.prepare(repo, "T2", ["src/old.py"])
    assert not (tree / "src" / "old.py").exists()


def test_tree_reused_keeps_untracked_build_output(repo):
    tree = trees.prepare(repo, "T2", ["src/b.py"])
    (tree / "build").mkdir()
    (tree / "build" / "o.bin").write_text("x")
    assert trees.prepare(repo, "T2", ["src/b.py"]) == tree
    assert (tree / "build" / "o.bin").read_text() == "x"


def test_stale_overlay_removed(repo):
    (repo / "src" / "b.py").write_text("B = 2\n")
    (repo / "src" / "new.py").write_text("N = 1\n")
    tree = trees.prepare(repo, "T2", ["src/b.py", "src/new.py"])
    git(repo, "checkout", "--", "src/b.py")
    (repo / "src" / "new.py").unlink()
    trees.prepare(repo, "T2", ["src/b.py", "src/new.py"])
    assert (tree / "src" / "b.py").read_text() == "B = 1\n"
    assert not (tree / "src" / "new.py").exists()


def test_clean_removes_worktrees(repo):
    trees.prepare(repo, "T1", ["src/a.py"])
    trees.prepare(repo, "T2", ["src/b.py"])
    assert trees.clean(repo) == 2
    assert ".superlite/trees" not in git(repo, "worktree", "list")
    assert not (repo / ".superlite" / "trees" / "T1").exists()


def fake_resolve(isolate):
    def resolve(root=".", paths=()):
        return {"language": "swift", "python": False, "isolate": isolate, "junit": "", "env": {}, "setup": "",
                "source": "test",
                "command": "python3 -c \"import src.a, src.b; open('ran-here.txt','w').write('x'); print('ok')\""}
    return resolve


def run_task(repo, monkeypatch, isolate, *extra):
    monkeypatch.chdir(repo)
    monkeypatch.setattr(testcmd, "resolve", fake_resolve(isolate))
    return run_tests.main(["--fast", "src/b.py", *extra, "--summary", ".superlite/test-summary.json",
                           "--log", ".superlite/incidents.jsonl", "--ledger", ".superlite/progress.md"])


def test_task_runs_in_tree_and_summary_in_main(repo, monkeypatch):
    (repo / "src" / "a.py").write_text("A = (\n")
    run_task(repo, monkeypatch, True, "--task", "T2", "--plan", "plan.md")
    assert (repo / ".superlite" / "trees" / "T2" / "ran-here.txt").exists()
    assert not (repo / "ran-here.txt").exists()
    assert (repo / ".superlite" / "test-summary.json").exists()


def test_isolate_false_runs_in_place(repo, monkeypatch):
    run_task(repo, monkeypatch, False, "--task", "T2", "--plan", "plan.md")
    assert (repo / "ran-here.txt").exists()
    assert not (repo / ".superlite" / "trees").exists()


def test_no_task_runs_in_place(repo, monkeypatch):
    run_task(repo, monkeypatch, True)
    assert (repo / "ran-here.txt").exists()
    assert not (repo / ".superlite" / "trees").exists()


def test_wait_line_has_absolute_sl_path():
    line = run_tests.wait_line("/x/s.json")
    assert "$SL" not in line
    assert line.startswith("wait: bash ")
    assert str(SCRIPTS.resolve() / "sl") in line.replace('"', "")
    assert line.endswith("run_tests --wait /x/s.json")


def test_concurrent_prepare_same_task(repo):
    import threading
    out = []

    def go():
        try:
            trees.prepare(repo, "T1", ["src/a.py"])
            out.append("ok")
        except Exception as e:  # noqa: BLE001
            out.append(str(e))
    ts = [threading.Thread(target=go) for _ in range(3)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert out == ["ok"] * 3
    assert not (repo / ".superlite" / "trees" / "T1.lock").exists()


def test_vanished_tree_directory_is_recreated(repo):
    import shutil
    tree = trees.prepare(repo, "T1", ["src/a.py"])
    shutil.rmtree(tree)
    assert (trees.prepare(repo, "T1", ["src/a.py"]) / "src" / "a.py").read_text() == "A = 1\n"


def test_files_outside_owns_not_overlaid_and_spaces_ok(tmp_path):
    root = tmp_path / "my repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "t@t")
    git(root, "config", "user.name", "t")
    (root / "a b.py").write_text("1\n")
    git(root, "add", ".")
    git(root, "commit", "-qm", "base")
    (root / "a b.py").write_text("2\n")
    (root / "other.py").write_text("x\n")
    tree = trees.prepare(root, "T1", ["a b.py"])
    assert (tree / "a b.py").read_text() == "2\n"
    assert not (tree / "other.py").exists()
