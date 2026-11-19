# tests/scripts/test_fleet_brief_taken_909.py: a fresh one-turn worker that never takes its brief is resent once, then reported not sent (#909)
import json
import sys
import pytest
from test_fleet_io import io, world  # noqa: F401
from test_fleet import world as fleet_world  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_io  # noqa: E402

TOOK_MS = 10000


def worker(world, wid):
    return json.loads((world.sd / "fleet.json").read_text())["workers"][wid]


def patch_worker(world, wid, **kw):
    p = world.sd / "fleet.json"
    d = json.loads(p.read_text())
    d["workers"][wid].update(kw)
    p.write_text(json.dumps(d))


def brief(world):
    b = world.sd / "briefs" / "b.md"
    b.parent.mkdir(parents=True, exist_ok=True)
    b.write_text("brief")
    return b


def test_took_brief_examples(world, monkeypatch):
    calls = []

    def run(result, stop):
        def wait_state(name, until, ms):
            calls.append((name, until, ms))
            if isinstance(result, Exception):
                raise result
            return result
        monkeypatch.setattr(world.fh, "wait_state", wait_state, raising=False)
        monkeypatch.setattr(io, "latest_stop", lambda sd, wid, after, stops=None: stop)
        return io.took_brief(world.sd, "W1", "sl-proj-w1", 5)
    assert run(world.fh.HerdrError("timeout", "x"), None) is True
    assert run("idle", None) is False
    assert run("done", {"t": 6}) is True
    assert run(world.fh.HerdrError("missing", "x"), None) is True
    assert calls[0] == ("sl-proj-w1", ["idle", "done"], 10000)
    assert io.TOOK_MS == TOOK_MS


def test_fresh_one_turn_resent_once_then_taken(world, monkeypatch, capsys):
    patch_worker(world, "W1", one_turn=True)
    prompts, answers = [], [False, True]
    monkeypatch.setattr(io, "_prompt", lambda name, msg: prompts.append(name))
    monkeypatch.setattr(io, "took_brief", lambda sd, wid, name, sent: answers.pop(0))
    assert io.send_brief(world.sd, "W1", str(brief(world)), "R1") == "R1"
    assert len(prompts) == 2
    cap = capsys.readouterr()
    assert "W1: brief not taken (the pane went idle with no turn); resending once" in cap.err
    assert "W1 R1 sent" in cap.out
    assert worker(world, "W1")["state"] == "busy"


def test_fresh_one_turn_never_taken_raises(world, monkeypatch, capsys):
    patch_worker(world, "W1", one_turn=True)
    monkeypatch.setattr(io, "_prompt", lambda name, msg: None)
    monkeypatch.setattr(io, "took_brief", lambda *a: False)
    with pytest.raises(world.fh.HerdrError) as ei:
        io.send_brief(world.sd, "W1", str(brief(world)), "R1")
    assert ei.value.code == "brief_not_taken" and ei.value.message == "brief not taken after one resend"
    assert worker(world, "W1")["state"] != "busy"
    assert "sent" not in capsys.readouterr().out


def test_primed_or_resent_worker_not_checked(world, monkeypatch):
    prompts = []
    monkeypatch.setattr(io, "_prompt", lambda name, msg: prompts.append(name))

    def boom(*a):
        raise AssertionError("took_brief called")
    monkeypatch.setattr(io, "took_brief", boom)
    b = str(brief(world))
    io.send_brief(world.sd, "W1", b, "R1")
    patch_worker(world, "W2", one_turn=True, sent=5)
    io.send_brief(world.sd, "W2", b, "R2")
    assert len(prompts) == 2


def test_brief_cli_prints_not_sent(fleet_world, monkeypatch, capsys):
    fleet.main(["on"])
    f = fleet_world.proj / "b.md"
    f.write_text("do it\n")

    def boom(*a, **k):
        raise fleet_world.fh.HerdrError("brief_not_taken", "brief not taken after one resend")
    monkeypatch.setattr(fleet_io, "send_brief", boom)
    monkeypatch.setattr(fleet_io, "hc", fleet_world.fh)
    capsys.readouterr()
    assert fleet.main(["spawn", "--role", "research", "--brief", str(f), "--label", "R1"]) == 3
    assert "BLOCKED: W1 R1 not sent (brief not taken after one resend)" in capsys.readouterr().out
