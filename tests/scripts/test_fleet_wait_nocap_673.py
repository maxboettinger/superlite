# tests/scripts/test_fleet_wait_nocap_673.py: fleet wait --timeout 0 waits without a limit (#673)
import json, sys
from pathlib import Path
import pytest
from test_fleet_io import world, rec, user, assistant, io  # noqa: F401


def _stop(world, tmp_path, wid, at, text="Status: DONE\nFiles: a.py"):
    tr = tmp_path / f"{wid}.jsonl"; rec(tr, user("task"), assistant(text))
    with (world.sd / "metrics.jsonl").open("a") as f:
        f.write(json.dumps({"ev": "stop", "t": at, "agent_id": wid, "type": "x", "transcript": str(tr), "last": text}) + "\n")


def test_wait_zero_timeout_never_times_out(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); start = world.clock.t[0]
    t = [start]
    def clock():
        t[0] += 600_000  # ten minutes per read
        if t[0] - start > 3_600_000 and not (world.sd / "metrics.jsonl").exists():
            _stop(world, tmp_path, "W1", start + 10)
            world.fh.states = [{"sl-proj-w1": "done"}]
        return t[0]
    out = io.wait(world.sd, ["W1"], 0, poll_s=0, clock=clock)
    assert out and out[0]["status"] == "DONE" and "TIMEOUT" not in capsys.readouterr().out and t[0] - start > 3_600_000


def test_wait_any_zero_timeout_ends_on_first_report(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    _stop(world, tmp_path, "W1", sent + 10)
    world.fh.states = [{"sl-proj-w1": "done", "sl-proj-w2": "working"}]
    out = io.wait(world.sd, ["W1", "W2"], 0, poll_s=0, any_=True)
    text = capsys.readouterr().out
    assert len(out) == 1 and "BUSY W2" in text and "TIMEOUT" not in text


def test_parse_zero_forms():
    assert io.parse_timeout("0") == io.parse_timeout("0s") == io.parse_timeout("0m") == 0


def test_cli_zero_timeout_note(world, capsys):
    assert io.main(["wait", "--timeout", "0", "--plan", str(world.sd)]) == 0
    err = capsys.readouterr().err
    assert "--timeout 0 waits without a limit" in err and "background command" in err


def test_nonzero_timeout_unchanged(world, capsys):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl")
    world.fh.states = [{"sl-proj-w1": "working"}]
    assert io.wait(world.sd, ["W1"], 1500, poll_s=1) == []
    assert "TIMEOUT W1" in capsys.readouterr().out
