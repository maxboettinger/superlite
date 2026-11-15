"""A --fast task tree holds a busy reviewer's file at base and a red tree run names root drift (#785)."""
from __future__ import annotations

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills/subagent-driven-development/scripts"))

import run_tests as rt  # noqa: E402
from test_plan_tools import run  # noqa: E402
from test_run_tests_plan_fallback import RUN_TESTS, setup  # noqa: E402


def busy(tmp_path, names):
    sd = tmp_path / ".superlite"
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W2": {"state": "busy", "role": "package-reviewer", "task": "rev-1"}}}), encoding="utf-8")
    (sd / "briefs").mkdir(exist_ok=True)
    (sd / "briefs" / "rev-1.md").write_text("Review " + " and ".join(names), encoding="utf-8")


def tree_file(tmp_path, rel):
    return (tmp_path / ".superlite/trees/T1" / rel).read_text(encoding="utf-8")


def changed(tmp_path):
    shared = tmp_path / "src" / "shared.c"
    shared.write_text("base", encoding="utf-8")
    from test_run_tests_plan_fallback import git
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "shared")
    shared.write_text("new", encoding="utf-8")
    (tmp_path / "src" / "a.c").write_text("new", encoding="utf-8")


def go(tmp_path, plan):
    return run(RUN_TESTS, "--fast", "src/a.c", "--task", "T1", "--plan", plan, cwd=tmp_path)


def test_fast_task_tree_holds_a_busy_reviewer_file(tmp_path):
    plan = setup(tmp_path)
    changed(tmp_path)
    busy(tmp_path, ["src/shared.c"])
    cp = go(tmp_path, plan)
    assert cp.returncode == 0, cp.both
    assert tree_file(tmp_path, "src/shared.c") == "base"
    assert "kept at base: 1 file of busy W2" in cp.err
    assert [l for l in cp.err.splitlines() if "run_tests: tree " in l][0].endswith("kept at base: 1 file of busy W2")


def test_task_own_file_is_never_held(tmp_path):
    plan = setup(tmp_path)
    changed(tmp_path)
    busy(tmp_path, ["src/a.c"])
    cp = go(tmp_path, plan)
    assert cp.returncode == 0, cp.both
    assert tree_file(tmp_path, "src/a.c") == "new"
    assert "kept at base" not in cp.err or "busy W2" not in cp.err


def test_no_fleet_holds_nothing(tmp_path):
    plan = setup(tmp_path)
    changed(tmp_path)
    cp = go(tmp_path, plan)
    assert cp.returncode == 0, cp.both
    assert tree_file(tmp_path, "src/shared.c") == "new"
    assert "busy" not in cp.err


def test_tree_drift_names_changed_copies(tmp_path):
    root, tree = tmp_path / "root", tmp_path / "tree"
    root.mkdir()
    tree.mkdir()
    (root / "a.c").write_bytes(b"same")
    (tree / "a.c").write_bytes(b"same")
    (root / "b.c").write_bytes(b"one")
    (tree / "b.c").write_bytes(b"two")
    (tree / "gone.c").write_bytes(b"x")
    assert rt.tree_drift(root, tree, ["a.c", "b.c", "gone.c"]) == ["b.c", "gone.c"]


def test_tree_drift_compares_bytes_not_mtimes(tmp_path):
    root, tree = tmp_path / "root", tmp_path / "tree"
    root.mkdir()
    tree.mkdir()
    (root / "a.c").write_bytes(b"same")
    (tree / "a.c").write_bytes(b"same")
    import os
    os.utime(root / "a.c", (1, 1))
    assert rt.tree_drift(root, tree, ["a.c"]) == []


def test_red_tree_run_names_drift(tmp_path):
    plan = setup(tmp_path)
    x = tmp_path / "src" / "x.c"
    x.write_text("base", encoding="utf-8")
    from test_run_tests_plan_fallback import git
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "x")
    x.write_text("new", encoding="utf-8")
    (tmp_path / ".superlite" / "edit.py").write_text(
        f"import sys\nopen({str(x)!r}, 'w').write('later')\nprint('error: red')\nsys.exit(1)\n", encoding="utf-8")
    cmd = f"{sys.executable} .superlite/edit.py"
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": cmd, "test_file": cmd, "isolate": True}), encoding="utf-8")
    cp = go(tmp_path, plan)
    assert cp.returncode == 1, cp.both
    assert "run_tests: changed in the run root while the tests ran: src/x.c; the tree tested the earlier copy, rerun to test the current files" in cp.err
