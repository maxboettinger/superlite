"""run_tests: a green full run stamps the unit layer (#229)."""
from __future__ import annotations

import importlib.util
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

REPO = Path(__file__).resolve().parents[2]
RUN_TESTS = SCRIPTS / "run_tests.py"
OK = "def test_ok():\n    assert True\n"
ENV_DROP = ("SUPERLITE_STATE_DIR", "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR")


def env():
    return {k: v for k, v in os.environ.items() if k not in ENV_DROP}


def git(cwd, *args):
    subprocess.run(["git", "-c", "user.email=t@t", "-c", "user.name=t", *args], cwd=cwd, check=True, capture_output=True)


def make_repo(tmp_path, test_body=OK, sub="", layers=True):
    """A git repo (project in `sub` when given) with the real layer scripts and one test."""
    repo = tmp_path / "repo"
    proj = repo / sub if sub else repo
    (proj / ".superlite").mkdir(parents=True)
    (proj / "tests/scripts").mkdir(parents=True)
    (proj / "pytest.ini").write_text("[pytest]\ntestpaths = tests\n")
    (proj / "tests/scripts/test_ok.py").write_text(test_body)
    if layers:
        (proj / "scripts").mkdir()
        for name in ("test_layers.py", "layer_store.py"):
            shutil.copy(REPO / "scripts" / name, proj / "scripts" / name)
    (repo / ".gitignore").write_text("__pycache__/\n.pytest_cache/\n")
    git(repo, "init", "-q")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "init")
    return repo, proj


def rt(proj, *args):
    return subprocess.run([sys.executable, str(RUN_TESTS), *args], cwd=proj, env=env(), capture_output=True, text=True)


def unit_line(proj):
    r = subprocess.run([sys.executable, "scripts/test_layers.py", "status"], cwd=proj, env=env(), capture_output=True, text=True)
    return next(ln for ln in r.stdout.splitlines() if ln.startswith("unit "))


def test_green_full_run_stamps_unit(tmp_path):
    _, proj = make_repo(tmp_path)
    cp = rt(proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "unit layer stamped" in cp.stderr
    assert unit_line(proj).startswith("unit green")


def test_background_full_run_stamps_unit(tmp_path):
    _, proj = make_repo(tmp_path)
    cp = rt(proj, "--full", "--background")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    path = re.search(r"^summary: (.+)$", cp.stdout, re.M).group(1).strip()
    w = rt(proj, "--wait", path)
    assert w.returncode == 0, w.stdout + w.stderr
    assert unit_line(proj).startswith("unit green")


def test_red_full_run_does_not_stamp(tmp_path):
    _, proj = make_repo(tmp_path, "def test_bad():\n    assert False\n")
    cp = rt(proj, "--full")
    assert cp.returncode == 1
    assert unit_line(proj).startswith("unit stale")


def test_fast_and_task_runs_do_not_stamp(tmp_path):
    _, proj = make_repo(tmp_path)
    assert rt(proj, "--fast", "tests/scripts/test_ok.py").returncode == 0
    assert unit_line(proj).startswith("unit stale")
    rt(proj, "--full", "--task", "T1")
    assert unit_line(proj).startswith("unit stale")


def test_file_changed_during_run_is_not_stamped(tmp_path):
    body = ("from pathlib import Path\n\n"
            "def test_ok():\n    (Path(__file__).resolve().parents[2] / 'scripts' / 'extra.py').write_text('x = 1\\n')\n")
    _, proj = make_repo(tmp_path, body)
    cp = rt(proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    line = unit_line(proj)
    assert line.startswith("unit stale") and "scripts/extra.py" in line


def test_subfolder_root_does_not_stamp(tmp_path):
    repo, proj = make_repo(tmp_path, sub="app", layers=False)
    cp = rt(proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert not (repo / ".git/superlite/test-layers.json").exists()


def test_no_layer_script_no_stamp(tmp_path):
    repo, proj = make_repo(tmp_path, layers=False)
    cp = rt(proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert not (repo / ".git/superlite/test-layers.json").exists()


def test_stamp_error_keeps_exit_code(tmp_path):
    _, proj = make_repo(tmp_path)
    (proj / "scripts/test_layers.py").write_text(
        "import sys\nfrom pathlib import Path\nsys.path.insert(0, str(Path(__file__).resolve().parent))\n"
        "import layer_store\nLAYERS = ('unit',)\n\n"
        "def layer_digests(layer, root):\n    return {}\n\n"
        "def write_stamp(*a, **k):\n    raise RuntimeError('x')\n")
    cp = rt(proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "unit layer not stamped: x" in cp.stderr


def test_write_stamp_takes_digests(tmp_path):
    spec = importlib.util.spec_from_file_location("superlite_test_layers_t3", REPO / "scripts" / "test_layers.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    store = tmp_path / "store.json"
    mod.write_stamp(tmp_path, store, "unit", {"a.py": "1"})
    assert mod.layer_store.is_green(store, "unit", mod.hash_digests({"a.py": "1"}))


def test_configured_test_command_does_not_stamp(tmp_path):
    _, proj = make_repo(tmp_path)
    cmd = f'{sys.executable} -c "print(\'1 passed\')"'
    (proj / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "python", "test": cmd}), encoding="utf-8")
    cp = rt(proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert "unit layer stamped" not in cp.stderr
    assert unit_line(proj).startswith("unit stale")


def test_snapshot_leaves_sys_path_alone(tmp_path, monkeypatch):
    import argparse
    sys.path.insert(0, str(SCRIPTS))
    import run_tests as mod
    monkeypatch.chdir(tmp_path)
    git(tmp_path, "init", "-q")
    (tmp_path / "scripts").mkdir()
    for name in ("test_layers.py", "layer_store.py"):
        shutil.copy(REPO / "scripts" / name, tmp_path / "scripts" / name)
    before = list(sys.path)
    snap = mod.unit_snapshot(argparse.Namespace(task=None), "full")
    assert snap is not None
    assert sys.path == before
