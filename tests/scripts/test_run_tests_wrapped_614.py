"""run_tests: wrapped xcodebuild builds in the tree, warning once, module cache prune (GitHub #614)."""
import json
import os
import subprocess
import sys
import time
from pathlib import Path

from test_plan_tools import SCRIPTS
from test_run_tests_plan_fallback import OUT, setup
from test_run_tests_disk_574 import run_env, set_cmd

sys.path.insert(0, str(SCRIPTS))
import run_tests as rt  # noqa: E402

WRAP = "lockf -t 1800 /tmp/l Scripts/test.sh"
RAW = 'xcodebuild test -scheme App'
FIXED = 'xcodebuild test -scheme App -derivedDataPath "$SUPERLITE_DERIVED_DATA_PATH"'


def project(tmp_path, body):
    root = tmp_path / "root"
    tree = tmp_path / "tree"
    (root / "App.xcodeproj").mkdir(parents=True)
    (tree / "Scripts").mkdir(parents=True)
    (tree / "Scripts" / "test.sh").write_text(body, encoding="utf-8")
    return tree, root


def test_warning_line_for_a_script_that_ignores_the_variable(tmp_path):
    tree, root = project(tmp_path, RAW)
    want = f"run_tests: WARNING: the test command `{WRAP}` has no xcodebuild word to rewrite and no script it names reads SUPERLITE_DERIVED_DATA_PATH, so it builds in the shared DerivedData; pass -derivedDataPath \"$SUPERLITE_DERIVED_DATA_PATH\" to xcodebuild in that script"
    assert rt.wrapped_build_warning(WRAP, tree, root, "swift") == want


def test_no_warning_when_the_script_reads_the_variable(tmp_path):
    tree, root = project(tmp_path, FIXED)
    assert rt.wrapped_build_warning(WRAP, tree, root, "swift") is None


def test_no_warning_without_an_xcode_project(tmp_path):
    root = tmp_path / "root"
    root.mkdir()
    (root / "Package.swift").write_text("//", encoding="utf-8")
    assert rt.wrapped_build_warning("swift test", tmp_path, root, "swift") is None
    assert rt.wrapped_build_warning(WRAP, tmp_path, root, "python") is None


def test_long_command_is_cut(tmp_path):
    tree, root = project(tmp_path, RAW)
    cmd = "lockf " + "x" * 300
    line = rt.wrapped_build_warning(cmd, tree, root, "swift")
    assert f"`{cmd[:200]}...`" in line


def wrapped_run(tmp_path, body=RAW, cmd="sh Scripts/test.sh", extra_env=None, args=("--task", "T1")):
    plan = setup(tmp_path)
    (tmp_path / "App.xcodeproj").mkdir()
    (tmp_path / "Scripts").mkdir()
    sh = tmp_path / "Scripts" / "test.sh"
    sh.write_text(f'#!/bin/sh\nenv | grep "^SUPERLITE_DERIVED_DATA_P" | cut -d= -f2- > "{tmp_path}/seen.txt"\necho "{OUT}"\n# {body}\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "s"], cwd=tmp_path, check=True)
    set_cmd(tmp_path, cmd)
    a = list(args) + (["--plan", str(plan)] if args else [])
    return run_env(tmp_path, "--full", *a, env=extra_env)


def test_script_sees_the_trees_derived_data_path(tmp_path):
    cp = wrapped_run(tmp_path)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    tree = (tmp_path / ".superlite" / "trees" / "T1").resolve()
    seen = (tmp_path / "seen.txt").read_text(encoding="utf-8").strip()
    assert Path(seen).resolve() == tree / ".build" / "DerivedData"


def test_root_run_exports_nothing(tmp_path):
    cp = wrapped_run(tmp_path, args=())
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert (tmp_path / "seen.txt").read_text(encoding="utf-8").strip() == ""


def test_env_entry_wins(tmp_path):
    plan = setup(tmp_path)
    (tmp_path / "App.xcodeproj").mkdir()
    (tmp_path / "Scripts").mkdir()
    (tmp_path / "Scripts" / "test.sh").write_text(f'#!/bin/sh\nenv | grep "^SUPERLITE_DERIVED_DATA_P" | cut -d= -f2- > "{tmp_path}/seen.txt"\necho "{OUT}"\n', encoding="utf-8")
    subprocess.run(["git", "add", "-A"], cwd=tmp_path, check=True)
    subprocess.run(["git", "commit", "-q", "-m", "s"], cwd=tmp_path, check=True)
    c = "sh Scripts/test.sh"
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": c, "test_file": c, "env": {"SUPERLITE_DERIVED_DATA_PATH": "/x"}}), encoding="utf-8")
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan)
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert (tmp_path / "seen.txt").read_text(encoding="utf-8").strip() == "/x"


def test_warning_once_per_command(tmp_path):
    first = wrapped_run(tmp_path)
    assert "no xcodebuild word to rewrite" in first.stderr
    plan = next((tmp_path / "docs" / "plans").glob("p.md"))
    again = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan)
    assert "no xcodebuild word to rewrite" not in again.stderr
    set_cmd(tmp_path, "sh ./Scripts/test.sh")
    third = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan)
    assert "no xcodebuild word to rewrite" in third.stderr


def test_rewritten_xcodebuild_does_not_warn(tmp_path):
    plan = setup(tmp_path)
    (tmp_path / "App.xcodeproj").mkdir()
    b = tmp_path / "bin"
    b.mkdir()
    x = b / "xcodebuild"
    x.write_text(f'#!/bin/sh\necho "{OUT}"\n', encoding="utf-8")
    x.chmod(0o755)
    set_cmd(tmp_path, "xcodebuild test -scheme App")
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env={"PATH": f"{b}{os.pathsep}{os.environ['PATH']}"})
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "WARNING: the test command" not in cp.stderr


def old_entry(home, name, hours):
    mc = home / "ModuleCache.noindex"
    mc.mkdir(parents=True, exist_ok=True)
    p = mc / name
    p.write_text("x", encoding="utf-8")
    t = time.time() - hours * 3600
    os.utime(p, (t, t))
    return p


def test_prune_below_warn_removes_old_entries(tmp_path):
    plan = setup(tmp_path)
    home = tmp_path / "dd"
    old, new = old_entry(home, "old", 25), old_entry(home, "new", 1)
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env={"SUPERLITE_DISK_FLOOR_GB": "0", "SUPERLITE_DISK_WARN_GB": "1000000", "SUPERLITE_DERIVED_DATA_HOME": str(home)})
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "module cache: removed 1 entries older than 24 h" in cp.stderr
    assert not old.exists() and new.exists()


def test_prune_runs_below_warn_only(tmp_path):
    plan = setup(tmp_path)
    home = tmp_path / "dd"
    old = old_entry(home, "old", 25)
    cp = run_env(tmp_path, "--full", "--task", "T1", "--plan", plan, env={"SUPERLITE_DISK_FLOOR_GB": "0", "SUPERLITE_DISK_WARN_GB": "0", "SUPERLITE_DERIVED_DATA_HOME": str(home)})
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "module cache" not in cp.stderr
    assert old.exists()
