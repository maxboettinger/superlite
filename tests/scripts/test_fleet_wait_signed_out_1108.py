"""fleet wait: a turn ended on a sign-in error is BLOCKED-UI with the signed-out suffix, never ASKED (#1108)."""
import json
import types
from test_fleet_io import io, world, stop_at, transcript  # noqa: F401  (world is a fixture)
import fleet  # noqa: E402

LOGIN = "Login reached its time limit · Please run /login"


def _run(world, tmp_path, last, machine=None):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    if machine:
        p = world.sd / "fleet.json"; d = json.loads(p.read_text()); d["workers"]["W1"]["machine"] = machine; p.write_text(json.dumps(d))
    tr = tmp_path / "w1.jsonl"; transcript(tr, last); stop_at(world, tr, sent + 10, last=last)
    world.fh.screen = "idle prompt\n"; world.fh.states = [{"sl-proj-w1": "idle"}]
    n = len([c for c in world.fh.calls if c[0] == "prompt"])
    io.wait(world.sd, ["W1"], 5000)
    return n


def test_signed_out_stop_is_blocked_not_asked(world, tmp_path, capsys):
    n = _run(world, tmp_path, LOGIN)
    o = capsys.readouterr().out
    assert "BLOCKED-UI" in o and "(signed out: account claude1" in o and "ASKED" not in o
    assert len([c for c in world.fh.calls if c[0] == "prompt"]) == n
    assert "claude1" in fleet.signed_out_accounts(world.sd)
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "blocked"


def test_plain_unreported_stop_is_still_asked(world, tmp_path, capsys):
    _run(world, tmp_path, "done thinking")
    assert "ASKED" in capsys.readouterr().out


def test_remote_signed_out_stop_marks_no_account(world, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(io, "_remote", lambda: types.SimpleNamespace(states=lambda sd: {"sl-proj-w1": "idle"}))  # the remote machine's own listing
    _run(world, tmp_path, LOGIN, machine="m1")
    assert "BLOCKED-UI" in capsys.readouterr().out
    assert "claude1" not in fleet.signed_out_accounts(world.sd)
