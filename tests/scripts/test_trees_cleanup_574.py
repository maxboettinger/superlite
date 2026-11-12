"""trees cleanup: busy markers, reap, orphaned DerivedData, module cache, disk gate (GitHub #574)."""
import json
import os
import plistlib
import subprocess
import sys
import time
from collections import namedtuple
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import trees  # noqa: E402

GiB = 1024 ** 3
U = namedtuple("U", "total used free")


def git(root, *a):
    subprocess.run(["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t", *a], check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "r"
    r.mkdir()
    (r / ".gitignore").write_text(".superlite/\n", encoding="utf-8")
    (r / "a.txt").write_text("a\n", encoding="utf-8")
    git(r, "init", "-q")
    git(r, "add", ".")
    git(r, "commit", "-qm", "init")
    return r


def make_dd(home, name, workspace, size=3):
    d = home / name
    (d / "Build").mkdir(parents=True)
    (d / "info.plist").write_bytes(plistlib.dumps({"WorkspacePath": str(workspace)}))
    (d / "Build" / "x.o").write_bytes(b"x" * size)
    return d


def test_derived_data_path_is_inside_the_tree():
    assert trees.derived_data_path("/r/.superlite/trees/T1") == Path("/r/.superlite/trees/T1/.build/DerivedData")


def test_reap_drops_committed_task_and_stopped_worker_trees(repo):
    for k in ("T1", "T2", "worker-W1", "worker-W2"):
        trees.prepare(repo, k, [])
    (trees.tree_path(repo, "T1") / ".build" / "DerivedData").mkdir(parents=True)
    assert trees.reap(repo, {"T1"}, {"W2"}) == ["T1", "worker-W2"]
    assert not trees.tree_path(repo, "T1").exists() and not trees.tree_path(repo, "worker-W2").exists()
    assert trees.tree_path(repo, "T2").is_dir() and trees.tree_path(repo, "worker-W1").is_dir()
    assert not (repo / ".superlite" / "trees" / "T1.overlay.json").exists()


def test_reap_keeps_a_busy_tree_and_the_keep_set(repo):
    trees.prepare(repo, "T1", [])
    trees.prepare(repo, "T2", [])
    with trees.busy(repo, "T1"):
        assert trees.is_busy(repo, "T1")
        assert trees.reap(repo, {"T1", "T2"}, set(), keep={"T2"}) == []
    assert not trees.is_busy(repo, "T1")
    assert trees.reap(repo, {"T1"}, set()) == ["T1"]


def test_a_dead_pid_busy_marker_is_stale(repo):
    trees.prepare(repo, "T1", [])
    marker = repo / ".superlite" / "trees" / "T1.busy.999999"
    marker.write_text("", encoding="utf-8")
    assert not trees.is_busy(repo, "T1") and not marker.exists()


def test_drop_refuses_a_bad_key(repo):
    (repo / "x").mkdir()
    assert trees.drop(repo, "../x") is False and trees.drop(repo, "a/b") is False
    assert (repo / "x").is_dir()
    assert trees.drop(repo, "T9") is False


def test_stopped_workers_reads_fleet_json(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W1": {"state": "stopped"}, "W2": {"state": "busy"}}}), encoding="utf-8")
    assert trees.stopped_workers(sd) == {"W1"}
    assert trees.stopped_workers(tmp_path / "none") == set()


def test_sweep_removes_only_orphaned_tree_derived_data(tmp_path, monkeypatch):
    home = tmp_path / "dd"
    monkeypatch.setenv("SUPERLITE_DERIVED_DATA_HOME", str(home))
    live = tmp_path / "p" / ".superlite" / "trees" / "T2"
    live.mkdir(parents=True)
    orphan = make_dd(home, "App-aaa", tmp_path / "p" / ".superlite" / "trees" / "T1", size=1000)
    alive = make_dd(home, "App-bbb", live)
    user = make_dd(home, "App-ccc", tmp_path / "gone" / "App.xcodeproj")
    (home / "ModuleCache.noindex" / "X").mkdir(parents=True)
    n, freed = trees.sweep_derived_data()
    assert (n, orphan.exists(), alive.exists(), user.exists()) == (1, False, True, True)
    assert freed >= 1000 and (home / "ModuleCache.noindex" / "X").is_dir()
    assert trees.sweep_derived_data(tmp_path / "none") == (0, 0)


def test_prune_module_cache_removes_entries_older_than_hours(tmp_path, monkeypatch):
    home = tmp_path / "dd"
    monkeypatch.setenv("SUPERLITE_DERIVED_DATA_HOME", str(home))
    mc = home / "ModuleCache.noindex"
    old, new = mc / "OLD1", mc / "NEW1"
    old.mkdir(parents=True)
    new.mkdir()
    (old / "a.pcm").write_bytes(b"o" * 10)
    (new / "b.pcm").write_bytes(b"n" * 10)
    t = time.time() - 30 * 3600
    os.utime(old / "a.pcm", (t, t))
    os.utime(old, (t, t))
    assert trees.prune_module_cache(24) == (1, 10)
    assert not old.exists() and new.exists()
    assert trees.prune_module_cache(24, home=tmp_path / "none") == (0, 0)


@pytest.mark.parametrize("free,level", [(12.3, "refuse"), (41.0, "warn"), (80.0, "ok")])
def test_disk_gate_levels(tmp_path, monkeypatch, free, level):
    monkeypatch.delenv("SUPERLITE_DISK_FLOOR_GB", raising=False)
    monkeypatch.delenv("SUPERLITE_DISK_WARN_GB", raising=False)
    monkeypatch.setattr(trees.shutil, "disk_usage", lambda p: U(1000 * GiB, 0, int(free * GiB)))
    got, line = trees.disk_gate(tmp_path)
    shown = tmp_path.resolve()
    assert got == level
    assert line == {"refuse": f"disk: 12.3 GB free on {shown}, below the 20 GB floor; run sl trees clean (trees, orphaned Xcode DerivedData) and free space, then rerun",
                    "warn": f"disk: WARNING: 41.0 GB free on {shown}, below 50 GB; run sl trees clean soon", "ok": ""}[level]


def test_disk_gate_env_zero_never_refuses_and_free_gb(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "0")
    monkeypatch.setenv("SUPERLITE_DISK_WARN_GB", "0")
    monkeypatch.setattr(trees.shutil, "disk_usage", lambda p: U(3 * GiB, 0, 3 * GiB))
    assert trees.disk_gate(tmp_path) == ("ok", "")
    assert trees.free_gb(tmp_path) == 3.0


def test_cli_clean_sweeps_orphans_and_prunes_on_request(repo, monkeypatch, capsys):
    home = repo.parent / "dd"
    monkeypatch.setenv("SUPERLITE_DERIVED_DATA_HOME", str(home))
    trees.prepare(repo, "T1", [])
    make_dd(home, "App-aaa", repo / ".superlite" / "trees" / "T1")
    make_dd(home, "App-bbb", repo / ".superlite" / "trees" / "T9")
    monkeypatch.chdir(repo)
    assert trees.main(["clean"]) == 0
    assert capsys.readouterr().out == "removed 1\nderived data: removed 2 orphaned folder(s), 0.0 GB\n"
    assert trees.main(["clean", "--module-cache-hours", "24"]) == 0
    assert capsys.readouterr().out == "removed 0\nmodule cache: removed 0 entries older than 24 h, 0.0 GB\n"
    assert trees.main(["clean", "--module-cache-hours", "x"]) == 2
    assert "trees: --module-cache-hours needs a number of hours" in capsys.readouterr().err
