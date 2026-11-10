"""run_tests task trees: a .superlite link into the root, mtime refresh of changed overlay files (GitHub #511, #507)."""
from __future__ import annotations

import json
import os
import sys
import time

from test_plan_tools import SCRIPTS, run
from test_run_tests_plan_fallback import OUT, setup

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"


def set_cmd(tmp_path, cmd):
    (tmp_path / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "swift", "test": cmd, "test_file": cmd}), encoding="utf-8")


def test_tree_has_superlite_link(tmp_path):
    plan = setup(tmp_path)
    set_cmd(tmp_path, f"""sh -c 'test -d ./.superlite && echo x > ./.superlite/seen; echo "{OUT}"'""")
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert (tmp_path / ".superlite" / "seen").exists()
    link = tmp_path / ".superlite" / "trees" / "T1" / ".superlite"
    assert link.is_symlink()
    assert link.resolve() == (tmp_path / ".superlite").resolve()


def test_tree_real_superlite_folder_kept(tmp_path):
    plan = setup(tmp_path)
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    link = tmp_path / ".superlite" / "trees" / "T1" / ".superlite"
    link.unlink()
    link.mkdir()
    (link / "mine.txt").write_text("m", encoding="utf-8")
    cp = run(RUN_TESTS, "--full", "--task", "T1", "--plan", str(plan), cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    assert link.is_dir() and not link.is_symlink()
    assert (link / "mine.txt").exists()


def test_refresh_touches_changed_only(tmp_path):
    tree = tmp_path / "trees" / "T1"
    tree.mkdir(parents=True)
    f = tree / "a.txt"
    f.write_text("one", encoding="utf-8")
    assert run_tests.refresh_mtimes(tree, "T1", ["a.txt"]) == 1
    os.utime(f, (1000, 1000))
    assert run_tests.refresh_mtimes(tree, "T1", ["a.txt"]) == 0
    assert int(f.stat().st_mtime) == 1000
    f.write_text("two", encoding="utf-8")
    os.utime(f, (1000, 1000))
    assert run_tests.refresh_mtimes(tree, "T1", ["a.txt"]) == 1
    assert abs(f.stat().st_mtime - time.time()) < 5
