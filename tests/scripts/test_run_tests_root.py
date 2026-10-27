"""run_tests started below the project root runs from the root."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests as rt  # noqa: E402


def proj(tmp_path):
    root = tmp_path.resolve() / "proj"
    sub = root / "config" / "skills" / "x"
    (root / ".superlite").mkdir(parents=True)
    (sub / "tests").mkdir(parents=True)
    (sub / "tests" / "test_a.py").write_text("def test_a():\n    assert True\n", encoding="utf-8")
    return root, sub


def go(cwd, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=cwd, capture_output=True, text=True, encoding="utf-8")


def test_project_root(tmp_path):
    root, sub = proj(tmp_path)
    assert rt.project_root(sub) == root
    assert rt.project_root(root) == root
    assert rt.project_root(tmp_path.resolve() / "nowhere-under-no-superlite") is None


def test_fast_from_subdirectory(tmp_path):
    root, sub = proj(tmp_path)
    cp = go(sub, "--fast", "tests/test_a.py")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert cp.stdout.split()[:3] == ["1", "0", "0"]
    assert f"run_tests: running from {root}" in cp.stderr


def test_background_from_subdirectory(tmp_path):
    root, sub = proj(tmp_path)
    cp = go(sub, "--fast", "tests/test_a.py", "--background")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    lines = cp.stdout.splitlines()
    assert lines[0].startswith("summary: ") and lines[1].startswith("wait: ")
    path = lines[0].split("summary: ", 1)[1]
    assert str(root) in path
    w = go(sub, "--timeout", "60", "--wait", path)
    assert w.returncode == 0, w.stdout + w.stderr
    assert '"passed": 1' in w.stdout


def test_absolute_paths_kept(tmp_path):
    root, sub = proj(tmp_path)
    cp = go(sub, "--fast", str(sub / "tests" / "test_a.py"))
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert cp.stdout.split()[:3] == ["1", "0", "0"]


def test_root_cwd_unchanged(tmp_path):
    root, sub = proj(tmp_path)
    cp = go(root, "--fast", "config/skills/x/tests/test_a.py")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "running from" not in cp.stderr


def test_fast_equals_spelling_from_subdirectory(tmp_path):
    root, sub = proj(tmp_path)
    cp = go(sub, "--fast=tests/test_a.py")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert cp.stdout.split()[:3] == ["1", "0", "0"]
