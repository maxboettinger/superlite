# tests/scripts/test_fleet_remote_brief_taken_971.py: a fresh remote one-turn worker that never takes its brief is resent once, then reported not sent (#971)
import json
import os
import sys
import pytest
from test_fleet_remote_worker import world, started, record  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io as fio  # noqa: E402
import fleet_remote as fr  # noqa: E402
import fleet_remote_worker as rw  # noqa: E402

REAL_TOOK = rw._took


def fake_clock(monkeypatch):
    t = [1000]
    monkeypatch.setattr(fio, "now_ms", lambda: t[0])
    monkeypatch.setattr(fio, "sleep", lambda s: t.__setitem__(0, t[0] + int(s * 1000)))
    return t


def syncs(monkeypatch):
    calls = []
    monkeypatch.setattr(fr, "sync", lambda sd, wid: calls.append(wid) or 0)
    return calls


def brief(world):
    b = world.sd / "briefs" / "q.md"
    b.write_text("question")
    return str(b)


def patch_record(world, wid="W1", **kw):
    p = world.sd / "fleet.json"
    d = json.loads(p.read_text())
    d["workers"][wid].update(kw)
    p.write_text(json.dumps(d))


def prompts(world):
    return [c for c in world.fh.calls if c[0] == "prompt"]


def test_constants():
    assert rw.SNAPSHOT_MS == 30000 and rw.SYNC_POLL_S == 2


def test_took_late_stop_record_through_sync(world, monkeypatch):
    t = fake_clock(monkeypatch)
    calls = syncs(monkeypatch)
    monkeypatch.setattr(fio, "latest_stop", lambda sd, wid, after, stops=None: {"t": 9} if len(calls) >= 3 else None)
    assert REAL_TOOK(world.sd, "W1", "sl-proj-w1", 5) is True
    assert len(calls) == 3 and t[0] - 1000 == 4000


def test_took_settles_longer_for_a_write_worker(world, monkeypatch):
    t = fake_clock(monkeypatch)
    syncs(monkeypatch)
    monkeypatch.setattr(fio, "latest_stop", lambda sd, wid, after, stops=None: None)
    assert REAL_TOOK(world.sd, "W1", "sl-proj-w1", 5) is False
    assert t[0] - 1000 == fio.SETTLE_MS
    t[0] = 1000
    assert REAL_TOOK(world.sd, "W1", "sl-proj-w1", 5, write=True) is False
    assert t[0] - 1000 == fio.SETTLE_MS + 30000


def test_took_still_working_counts_as_taken(world, monkeypatch):
    calls = syncs(monkeypatch)
    waits = []

    def wait_state(name, until, ms):
        waits.append((name, until, ms))
        raise world.fh.HerdrError("timeout", "x")
    monkeypatch.setattr(world.fh, "wait_state", wait_state)
    assert REAL_TOOK(world.sd, "W1", "sl-proj-w1", 5) is True
    assert waits == [("sl-proj-w1", ["idle", "done"], fio.TOOK_MS)] and calls == []


def test_took_runs_inside_on(world, monkeypatch):
    started(world)
    world.fh.calls.clear()
    monkeypatch.setattr(rw, "_took", REAL_TOOK)
    syncs(monkeypatch)
    monkeypatch.setattr(fio, "latest_stop", lambda sd, wid, after, stops=None: {"t": 9})
    assert rw.send_brief(world.sd, "W1", brief(world), "Q1") == "Q1"
    inside, outside = world.fh.inside()
    assert any(c[0] == "wait_state" for c in inside) and all(c[0] != "wait_state" for c in outside)


def test_fresh_one_turn_resent_once_then_taken(world, monkeypatch, capsys):
    started(world)
    world.fh.calls.clear()
    answers, seen = [False, True], []
    monkeypatch.setattr(rw, "_took", lambda sd, wid, name, sent, write=False: (seen.append((wid, write)), answers.pop(0))[1])
    assert rw.send_brief(world.sd, "W1", brief(world), "Q1") == "Q1"
    assert len(prompts(world)) == 2 and seen == [("W1", False), ("W1", False)]
    cap = capsys.readouterr()
    assert "W1: brief not taken (the pane went idle with no turn); resending once" in cap.err
    assert "W1 Q1 sent" in cap.out
    assert record(world)["state"] == "busy"


def test_fresh_one_turn_never_taken_raises(world, monkeypatch, capsys):
    started(world)
    world.fh.calls.clear()
    monkeypatch.setattr(rw, "_took", lambda *a, **k: False)
    with pytest.raises(world.fh.HerdrError) as ei:
        rw.send_brief(world.sd, "W1", brief(world), "Q1")
    assert ei.value.code == "brief_not_taken" and ei.value.message == "brief not taken after one resend"
    assert len(prompts(world)) == 2 and record(world)["state"] != "busy"
    assert "Q1 sent" not in capsys.readouterr().out


def test_second_brief_or_multi_turn_not_checked(world, monkeypatch):
    started(world)

    def boom(*a, **k):
        raise AssertionError("_took called")
    patch_record(world, sent=123)
    monkeypatch.setattr(rw, "_took", boom)
    assert rw.send_brief(world.sd, "W1", brief(world), "Q2") == "Q2"
    patch_record(world, sent=None, one_turn=False)
    assert rw.send_brief(world.sd, "W1", brief(world), "Q3") == "Q3"


def test_write_worker_gets_the_longer_settle(world, monkeypatch):
    started(world)
    patch_record(world, remote={**record(world)["remote"], "write": True})
    seen = []
    monkeypatch.setattr(rw, "_took", lambda sd, wid, name, sent, write=False: seen.append(write) or True)
    rw.send_brief(world.sd, "W1", brief(world), "Q1")
    assert seen == [True]


def test_took_reads_the_mirror_the_sync_fills(world, monkeypatch):
    started(world)
    fake_clock(monkeypatch)
    mirror = record(world)["state_dir"]
    sent_ms = 5000

    def sync(sd, wid):
        os.makedirs(mirror, exist_ok=True)
        with open(f"{mirror}/metrics.jsonl", "a") as f:
            f.write(json.dumps({"ev": "stop", "agent_id": "W1", "t": sent_ms + 1}) + "\n")
        return 1
    monkeypatch.setattr(fr, "sync", sync)
    assert REAL_TOOK(world.sd, "W1", "sl-proj-w1", sent_ms) is True
