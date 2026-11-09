# tests/scripts/test_fleet_io_brief_stall.py
import json
import pytest
from test_fleet_io import io, world  # noqa: F401


def stall_cls(world):
    class Stall(world.fh.HerdrError):
        def __init__(self, code, message=""):
            super().__init__(f"{code}: {message}")
            self.code = code
            self.message = message
    return Stall


def setup(world, *outcomes):
    Stall = stall_cls(world)
    records, queue = [], list(outcomes)

    def prompt(name, text, until, timeout_ms):
        records.append((name, text, until, timeout_ms))
        o = queue.pop(0)
        if isinstance(o, Exception):
            raise o
        return o
    world.fh.prompt = prompt
    b = world.sd / "briefs" / "b.md"
    b.parent.mkdir(parents=True, exist_ok=True)
    b.write_text("brief")
    return Stall, records, b


def worker(world, wid):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]


def test_send_brief_resends_once_on_a_stall(world, capsys):
    Stall = stall_cls(world)
    _, records, b = setup(world, Stall("agent_prompt_stalled", "no working state"), "working")
    assert io.send_brief(world.sd, "W2", str(b)) == "b"
    assert len(records) == 2 and records[0] == records[1]
    assert records[0][2] == ["working"] and records[0][3] == 15000
    assert worker(world, "W2")["state"] == "busy" and worker(world, "W2")["task"] == "b"
    assert "W2 b sent" in capsys.readouterr().out


def test_send_brief_second_stall_raises_and_leaves_the_worker_ready(world, capsys):
    Stall = stall_cls(world)
    _, records, b = setup(world, Stall("agent_prompt_stalled", "x"), Stall("agent_prompt_stalled", "x"))
    with pytest.raises(world.fh.HerdrError) as ei:
        io.send_brief(world.sd, "W2", str(b))
    assert ei.value.code == "agent_prompt_stalled"
    assert len(records) == 2
    assert worker(world, "W2")["state"] == "ready" and worker(world, "W2")["task"] is None
    assert "sent" not in capsys.readouterr().out


def test_send_brief_does_not_resend_other_errors(world):
    Stall = stall_cls(world)
    _, records, b = setup(world, Stall("timeout", "15000 ms"))
    with pytest.raises(world.fh.HerdrError) as ei:
        io.send_brief(world.sd, "W2", str(b))
    assert ei.value.code == "timeout" and len(records) == 1
    assert worker(world, "W2")["state"] == "ready"


def test_send_brief_cli_second_stall_exits_1(world, capsys):
    Stall = stall_cls(world)
    _, records, b = setup(world, Stall("agent_prompt_stalled", "no working state"), Stall("agent_prompt_stalled", "no working state"))
    assert io.main(["send", "W1", "--brief", str(b)]) == 1
    assert "error: agent_prompt_stalled: no working state" in capsys.readouterr().err
    assert worker(world, "W1")["state"] == "ready"
