# tests/scripts/test_fleet_wait_once_578.py: fleet wait honours its timeout and returns each report once (#578)
import json, sys
import pytest
from test_fleet_io import world, FakeHerdr, transcript  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_io as io  # noqa: E402


def stop(w, wid, tr, t):
    with open(w.sd / "metrics.jsonl", "a") as f:
        f.write(json.dumps({"ev": "stop", "t": t, "agent_id": wid, "type": "x", "transcript": str(tr), "last": ""}) + "\n")


def fj(w): return json.loads((w.sd / "fleet.json").read_text())["workers"]


def busy_done(w, tmp_path, wid="W1", task="T3"):
    io.send(w.sd, w.plan, wid, [task], "/sl/sl", "/sl"); sent = w.clock.t[0]
    tr = tmp_path / f"{wid}.jsonl"; transcript(tr, "Status: DONE")
    stop(w, wid, tr, sent + 10)
    return sent


def test_parse_timeout_units():
    for v, ms in [("540000", 540000), ("580", 580000), ("580s", 580000), ("9m", 540000), ("1500ms", 1500), ("0", 0), ("1000", 1000)]:
        assert io.parse_timeout(v) == ms
    for v in ["abc", "-5", "5h", ""]:
        with pytest.raises(ValueError):
            io.parse_timeout(v)


def test_cli_small_timeout_reads_seconds(world, monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(io, "wait", lambda sd, ids, t, *a, **k: seen.append(t))
    assert io.main(["wait", "--timeout", "580"]) == 0
    assert seen == [580000] and "--timeout 580 read as 580 s" in capsys.readouterr().err
    assert io.main(["wait", "--timeout", "540000"]) == 0
    assert seen[-1] == 540000 and capsys.readouterr().err == ""


def test_cli_bad_timeout_exits_2(world, capsys):
    assert io.main(["wait", "--timeout", "abc"]) == 2
    assert capsys.readouterr().err.startswith("error: --timeout abc")


def test_claim_once(world):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); s = world.clock.t[0]
    assert io.claim(world.sd, "W1", s) is True
    assert io.claim(world.sd, "W1", s) is False
    assert fj(world)["W1"]["collected"] == s
    assert io.claim(world.sd, "W1", s + 1) is False
    assert io.claim(world.sd, "W2", s) is False  # ready
    assert io.claim(world.sd, "W9", s) is False  # unknown


def test_concurrent_finish_reports_once(world, tmp_path, capsys):
    s = busy_done(world, tmp_path); world.fh.states = [{"sl-proj-w1": "done"}]
    assert io.claim(world.sd, "W1", s) is True  # another wait got it first
    assert io.wait(world.sd, ["W1"], 5000) == []
    out = capsys.readouterr().out
    assert "W1 T3 already collected" in out and "W1 T3 DONE" not in out
    assert not (world.sd / "fleet" / "reports" / "T3.json").exists()


def test_second_wait_returns_nothing_new(world, tmp_path, capsys):
    busy_done(world, tmp_path); world.fh.states = [{"sl-proj-w1": "done"}]
    assert len(io.wait(world.sd, ["W1"], 5000)) == 1
    assert "W1 T3 DONE" in capsys.readouterr().out
    assert io.wait(world.sd, ["W1"], 5000) == []
    assert f"W1 T3 already collected: {world.sd}/fleet/reports/T3.json" in capsys.readouterr().out


def test_worker_collected_mid_wait_leaves_pending(world, tmp_path, capsys, monkeypatch):
    io.send(world.sd, world.plan, "W1", ["T3"], "/sl/sl", "/sl"); io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl"); sent = world.clock.t[0]
    tr = tmp_path / "w2.jsonl"; transcript(tr, "Status: DONE")
    world.fh.states = [{"sl-proj-w1": "working", "sl-proj-w2": "working"}]
    calls = []
    def fake_sleep(s):
        calls.append(s)
        world.clock.t[0] += int(s * 1000)
        if len(calls) == 1:
            io._ready(world.sd, "W1", "T3")  # another process collected W1
            stop(world, "W2", tr, sent + 10); world.fh.states = [{"sl-proj-w1": "idle", "sl-proj-w2": "done"}]
    monkeypatch.setattr(io, "sleep", fake_sleep)
    out = io.wait(world.sd, ["W1", "W2"], 60000)
    text = capsys.readouterr().out
    assert [r["id"] for r in out] == ["W2"] and "W1 T3 already collected" in text and "W2 T4 DONE" in text


def test_wait_any_busy_line_names_finisher(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl"); busy_done(world, tmp_path)
    world.fh.states = [{"sl-proj-w1": "done", "sl-proj-w2": "working"}]
    io.wait(world.sd, None, 60000, any_=True)
    assert capsys.readouterr().out.strip().splitlines()[-1] == f"BUSY W2 (reported: W1 {world.sd}/fleet/reports/T3.json)"


def test_timeout_line_names_finishers(world, tmp_path, capsys):
    io.send(world.sd, world.plan, "W2", ["T4"], "/sl/sl", "/sl"); busy_done(world, tmp_path)
    world.fh.states = [{"sl-proj-w1": "done", "sl-proj-w2": "working"}]
    io.wait(world.sd, None, 5000)
    assert capsys.readouterr().out.strip().splitlines()[-1] == f"TIMEOUT W2 (reported: W1 {world.sd}/fleet/reports/T3.json)"
    world.fh.states = [{"sl-proj-w2": "working"}]
    io.wait(world.sd, ["W2"], 5000)
    assert capsys.readouterr().out.strip().splitlines()[-1] == "TIMEOUT W2"
