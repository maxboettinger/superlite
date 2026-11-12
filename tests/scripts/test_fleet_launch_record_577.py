"""fleet.py records the launch and session of a worker, delegates restore, names it after a death (#577)."""
import json, sys, types
from pathlib import Path
import pytest
from test_fleet import world, FakeHerdr, SCRIPTS  # noqa: F401
import fleet  # noqa: E402


def _workers(world):
    return json.loads((world.sd / "fleet.json").read_text())["workers"]


def test_spawn_records_launch(world, monkeypatch):
    seen = {}
    real = world.fh.create_workspace
    def cw(label, cwd, env):
        seen["env"] = env
        return real(label, cwd, env)
    world.fh.create_workspace = cw
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent")
    assert _workers(world)["W1"]["launch"] == {"argv": argv, "env": seen["env"], "cwd": str(world.proj)}


def test_spawn_records_session(world):
    world.fh.agent_session = lambda name: "sid-1"
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert _workers(world)["W1"]["session"] == "sid-1"


def test_spawn_without_agent_session_still_works(world):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    w = _workers(world)["W1"]
    assert "session" not in w and w["state"] == "ready"


def test_spawn_session_error_is_ignored(world):
    def boom(name): raise RuntimeError("x")
    world.fh.agent_session = boom
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert "session" not in _workers(world)["W1"]


def test_mark_dead_keeps_was(world):
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    import fleet_state as fs
    fs.set_state(world.sd, "W1", "busy")
    data = json.loads((world.sd / "fleet.json").read_text()); data["workers"]["W1"]["task"] = "T3"
    (world.sd / "fleet.json").write_text(json.dumps(data))
    fleet.mark_dead(world.sd, "W1")
    w = _workers(world)["W1"]
    assert (w["state"], w["dead"], w["was"], w["last_task"], w["task"]) == ("stopped", True, "busy", "T3", None)


def test_restore_is_delegated(world, monkeypatch):
    calls = []
    mod = types.ModuleType("fleet_restore")
    mod.main = lambda argv: (calls.append(argv), 7)[1]
    monkeypatch.setitem(sys.modules, "fleet_restore", mod)
    assert fleet.main(["restore", "--plan", str(world.sd)]) == 7
    assert calls == [["--plan", str(world.sd)]]


def test_status_names_restore_after_dead(world, capsys):
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    world.fh.gone.add(fleet.fs.name_of(world.sd, "W1", _workers(world)["W1"]))
    capsys.readouterr()
    fleet.main(["status", "--plan", str(world.sd)])
    out = capsys.readouterr().out
    assert f"restore: after a Herdr restart, sl fleet restore --plan {world.sd.resolve()} resumes the workers in their own sessions" in out


def test_status_without_dead_has_no_restore_line(world, capsys):
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    capsys.readouterr()
    fleet.main(["status", "--plan", str(world.sd)])
    assert "restore:" not in capsys.readouterr().out


def test_docstring_lists_checker_and_writer():
    doc = fleet.__doc__
    assert "checker, writer" in doc and "fleet restore" in doc and "--note" in doc and "Output:" in doc


def test_mark_dead_twice_keeps_first_was(world):
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    import fleet_state as fs
    fs.set_state(world.sd, "W1", "busy")
    fleet.mark_dead(world.sd, "W1")
    fleet.mark_dead(world.sd, "W1")
    assert _workers(world)["W1"]["was"] == "busy"
