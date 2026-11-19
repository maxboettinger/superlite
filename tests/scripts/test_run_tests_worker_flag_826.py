"""#826: run_tests --worker NAME gives a fleet-off (in-process Agent) reviewer or fixer its own tree."""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_isolated_review_builds_479 import cwd, go, repo  # noqa: E402  # puts the scripts folder on sys.path
import run_tests as rt  # noqa: E402

TREES = ".superlite/trees"


def test_worker_tree_name_flag_and_env():
    fleet = {"SUPERLITE_FLEET_WORKER": "W3", "SUPERLITE_FLEET_AGENT": "fixer-sonnet"}
    lead = {"SUPERLITE_FLEET_WORKER": "W9", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_FLEET_AGENT": "lead"}
    assert rt.worker_tree_name({}, "fix-F-T1-1") == "worker-fix-F-T1-1"
    assert rt.worker_tree_name(fleet, "fix-F-T1-1") == "worker-W3"
    assert rt.worker_tree_name(lead, "rev-T2") == "worker-rev-T2"
    assert rt.worker_tree_name({}, None) is None
    assert rt.worker_tree_name(lead) is None
    assert rt.worker_tree_name({}, "../x") is None


def test_fleet_off_fast_run_with_worker_uses_its_own_tree(tmp_path):
    plan = repo(tmp_path)
    cp = go(tmp_path, plan, "--fast", "src/b.py", "--worker", "fix-F-T1-1")
    assert cp.returncode == 0, cp.err
    assert f"run_tests: tree {TREES}/worker-fix-F-T1-1 = base + all working-tree changes (--fast)" in cp.err
    assert cwd(tmp_path) == (tmp_path / TREES / "worker-fix-F-T1-1").resolve()


def test_two_fleet_off_workers_get_separate_trees(tmp_path):
    plan = repo(tmp_path)
    go(tmp_path, plan, "--fast", "src/b.py", "--worker", "rev-P1")
    first = cwd(tmp_path)
    go(tmp_path, plan, "--fast", "src/b.py", "--worker", "fix-F-T2-1")
    assert cwd(tmp_path) != first
    assert (tmp_path / TREES / "worker-rev-P1/.git").exists()
    assert (tmp_path / TREES / "worker-fix-F-T2-1/.git").exists()


def test_fleet_worker_env_wins_over_flag(tmp_path):
    plan = repo(tmp_path)
    cp = go(tmp_path, plan, "--fast", "src/b.py", "--worker", "fix-F-T1-1", WORKER="W3", AGENT="fixer-sonnet")
    assert cp.returncode == 0, cp.err
    assert cwd(tmp_path) == (tmp_path / TREES / "worker-W3").resolve()
    assert not (tmp_path / TREES / "worker-fix-F-T1-1").exists()


def test_lead_env_honours_flag(tmp_path):
    plan = repo(tmp_path)
    cp = go(tmp_path, plan, "--fast", "src/b.py", "--worker", "rev-T2", WORKER="W9", ROLE="lead", AGENT="lead")
    assert cp.returncode == 0, cp.err
    assert cwd(tmp_path) == (tmp_path / TREES / "worker-rev-T2").resolve()


def test_task_and_full_runs_ignore_flag(tmp_path):
    plan = repo(tmp_path)
    cp = go(tmp_path, plan, "--fast", "src/b.py", "--task", "T2", "--worker", "fix-F-T2-1")
    assert f"{TREES}/T2" in cp.err
    assert not (tmp_path / TREES / "worker-fix-F-T2-1").exists()
    go(tmp_path, plan, "--full", "--worker", "fix-F-T2-1")
    assert cwd(tmp_path) == tmp_path.resolve()
    assert not (tmp_path / TREES / "worker-fix-F-T2-1").exists()


def test_bad_worker_name_is_a_usage_error(tmp_path):
    plan = repo(tmp_path)
    for bad in ("../x", "a b", "x" * 65, ""):
        cp = go(tmp_path, plan, "--fast", "src/b.py", "--worker", bad)
        assert cp.returncode == 2, (bad, cp.err)
        assert f"--worker NAME: 1 to 64 letters, digits, - or _ (got {bad[:80]!r})" in cp.err
    long = "y" * 100 + " "
    cp = go(tmp_path, plan, "--fast", "src/b.py", "--worker", long)
    assert cp.returncode == 2 and f"(got {long[:80]!r})" in cp.err and "y" * 81 not in cp.err
    assert not list((tmp_path / TREES).glob("worker-*"))
