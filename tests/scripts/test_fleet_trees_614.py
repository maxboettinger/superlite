"""fleet stop drops the worker's tree; fleet spawn gates the disk (#614)."""
import os
import subprocess

from test_fleet import fleet, world  # noqa: F401,E402  (world is a fixture; it puts the scripts on sys.path)

import trees  # noqa: E402


def _git_proj(world):
    for a in (["init", "-q"], ["config", "user.email", "a@b"], ["config", "user.name", "n"],
              ["commit", "-q", "--allow-empty", "-m", "i"]):
        subprocess.run(["git", "-C", str(world.proj), *a], check=True, capture_output=True)


def _on_and_spawn(world):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    return fleet.spawn(world.sd, world.plan, "sonnet", world.proj)


def test_stop_drops_the_worker_tree(world):
    _git_proj(world)
    _on_and_spawn(world)
    trees.prepare(world.proj, "worker-W1", [])
    assert trees.tree_path(world.proj, "worker-W1").is_dir()
    assert fleet.stop(world.sd, ["W1"]) == ["W1"]
    assert not trees.tree_path(world.proj, "worker-W1").exists()


def test_stop_keeps_a_busy_worker_tree(world):
    _git_proj(world)
    _on_and_spawn(world)
    trees.prepare(world.proj, "worker-W1", [])
    (world.proj / trees.TREES / f"worker-W1.busy.{os.getpid()}").write_text("")
    fleet.stop(world.sd, ["W1"])
    assert trees.tree_path(world.proj, "worker-W1").is_dir()


def test_spawn_refused_below_floor_opens_no_pane(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "1000000")
    world.fh.calls.clear()
    assert fleet.main(["spawn", "--tier", "sonnet"]) == 3
    out = capsys.readouterr().out
    assert out.startswith("BLOCKED: fleet spawn: disk: ")
    assert world.fh.calls == []


def test_spawn_warns_below_warn_level(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    capsys.readouterr()
    monkeypatch.setenv("SUPERLITE_DISK_WARN_GB", "1000000")
    assert fleet.main(["spawn", "--tier", "sonnet"]) == 0
    cap = capsys.readouterr()
    assert "fleet: disk: WARNING: " in cap.err
    assert "W1 account=" in cap.out


def test_for_dispatch_not_gated_twice(world, monkeypatch):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    import trees as t
    calls = []
    monkeypatch.setattr(t, "disk_gate", lambda p: calls.append(p) or ("ok", ""))
    monkeypatch.setattr(fleet, "for_dispatch", lambda *a, **k: 0)
    assert fleet.main(["spawn", "--for-dispatch", "--plan", str(world.plan)]) == 0
    assert calls == []
