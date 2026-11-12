"""dispatch: refuses on a nearly full disk, warns, reaps unneeded trees and drops an evicted worker's tree (GitHub #574)."""
from __future__ import annotations

import json
import subprocess
import sys

from test_dispatch_evict import AGENTS, WORN, pool_file
from test_plan_tools import SCRIPTS, run
from test_routing import mixed
from test_stable_split import DISPATCH

sys.path.insert(0, str(SCRIPTS))
import dispatch as dispatchmod  # noqa: E402
import trees  # noqa: E402


def repo(tmp_path):
    for a in (("init", "-q"), ("config", "user.name", "T"), ("config", "user.email", "t@t"), ("config", "commit.gpgsign", "false")):
        subprocess.run(["git", "-C", str(tmp_path), *a], check=True, capture_output=True)
    (tmp_path / ".gitignore").write_text(".superlite/\n*.md\n", encoding="utf-8")
    (tmp_path / "a.txt").write_text("a\n", encoding="utf-8")
    subprocess.run(["git", "-C", str(tmp_path), "add", ".gitignore", "a.txt"], check=True, capture_output=True)
    subprocess.run(["git", "-C", str(tmp_path), "commit", "-qm", "init"], check=True, capture_output=True)


def go(tmp_path, p, pool, ledger=None, *extra):
    led = ledger or tmp_path / ".superlite" / "progress.md"
    return run(DISPATCH, "--plan", p, "--pool", pool, "--ledger", led, *extra, cwd=tmp_path)


def test_dispatch_refuses_below_the_floor(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "999999")
    cp = go(tmp_path, mixed(tmp_path), pool_file(tmp_path, []))
    assert cp.returncode == 3 and cp.out == "", cp.both
    assert "dispatch: BLOCKED: disk: " in cp.err and "below the 999999 GB floor" in cp.err


def test_dispatch_warns_and_still_dispatches(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "0")
    monkeypatch.setenv("SUPERLITE_DISK_WARN_GB", "999999")
    cp = go(tmp_path, mixed(tmp_path), pool_file(tmp_path, []))
    assert cp.returncode == 0, cp.both
    assert "dispatch: disk: WARNING: " in cp.err
    assert any(ln.startswith("T1 ") for ln in cp.out.splitlines())


def test_dispatch_reaps_committed_and_stopped_trees(tmp_path):
    repo(tmp_path)
    for k in ("T1", "worker-W5", "T2"):
        trees.prepare(tmp_path, k, [])
    led = tmp_path / ".superlite" / "progress.md"
    led.write_text("- commit T1 abcdef1234 t1\n", encoding="utf-8")
    (tmp_path / ".superlite" / "fleet.json").write_text(json.dumps({"workers": {"W5": {"state": "stopped"}}}), encoding="utf-8")
    cp = go(tmp_path, mixed(tmp_path), pool_file(tmp_path, []))
    assert cp.returncode == 0, cp.both
    assert "dispatch: removed 2 tree(s) nothing needs: T1, worker-W5" in cp.err
    assert not trees.tree_path(tmp_path, "T1").exists() and not trees.tree_path(tmp_path, "worker-W5").exists()
    assert trees.tree_path(tmp_path, "T2").is_dir()


def test_dispatch_drops_an_evicted_workers_tree(tmp_path):
    repo(tmp_path)
    trees.prepare(tmp_path, "worker-W9", [])
    w9 = {"id": "W9", "tier": "sonnet", "tasks": WORN, "files": [], "context_k": 20.0, "idle_min": 0, "busy": False}
    cp = go(tmp_path, mixed(tmp_path), pool_file(tmp_path, AGENTS + [w9]))
    assert cp.returncode == 0 and "evict=W9" in cp.err, cp.both
    assert not trees.tree_path(tmp_path, "worker-W9").exists()


def test_run_with_gate_false_skips_the_check(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "999999")
    p, pool = mixed(tmp_path), pool_file(tmp_path, [])
    lines, _ = dispatchmod.run(p, pool, tmp_path / ".superlite" / "progress.md", gate=False)
    assert lines and lines[0][0].startswith("T1")
    assert dispatchmod.run(p, pool, tmp_path / ".superlite" / "progress.md")[0] == []


def test_pool_outside_superlite_does_no_tree_work(tmp_path):
    repo(tmp_path)
    trees.prepare(tmp_path, "T1", [])
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps({"agents": []}), encoding="utf-8")
    led = tmp_path / "l.md"
    led.write_text("- commit T1 abcdef1234 t1\n", encoding="utf-8")
    cp = go(tmp_path, mixed(tmp_path), pool, led)
    assert cp.returncode == 0, cp.both
    assert "nothing needs" not in cp.err and trees.tree_path(tmp_path, "T1").is_dir()
