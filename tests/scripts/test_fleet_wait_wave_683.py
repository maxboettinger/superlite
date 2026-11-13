# tests/scripts/test_fleet_wait_wave_683.py - fleet wait --wave and --tests (#683)
import json, subprocess, sys
import pytest
from test_fleet_io import FakeHerdr, world, transcript, io, fs, make_plan  # noqa: F401  (the Herdr fake and the world fixture are reused)
import run_tests  # noqa: E402

FINDINGS = "Verdict: APPROVED\na.py:1 - bad name - rename it - tier 1\nb.py:2 - dead code - drop it - tier 2\n"


def fleet(world, n=4):  # n busy workers W1..Wn on tasks T1..Tn; the Herdr fake lists them all working
    data = json.loads((world.sd / "fleet.json").read_text())
    for i in range(1, n + 1):
        data["workers"][f"W{i}"] = {**data["workers"]["W1"], "name": f"sl-proj-w{i}", "pane_id": f"w6:p{i}"}
    (world.sd / "fleet.json").write_text(json.dumps(data))
    plan = make_plan(world.proj, [{"id": f"T{i}", "title": f"t{i}"} for i in range(1, n + 1)])
    for i in range(1, n + 1):
        io.send(world.sd, plan, f"W{i}", [f"T{i}"], "/sl/sl", "/sl")
    world.fh.states = [{f"sl-proj-w{i}": "working" for i in range(1, n + 1)}]
    world.sent = world.clock.t[0]
    world.todo = []
    real_sleep = io.sleep

    def sleep(s):  # advance the fake clock, then fire what is due
        real_sleep(s)
        for item in list(world.todo):
            if world.clock.t[0] - world.sent >= item[0] * 1000:
                world.todo.remove(item); item[1]()
    io.sleep = sleep
    return plan


@pytest.fixture(autouse=True)
def _sleep(monkeypatch):
    monkeypatch.setattr(io, "sleep", io.sleep)  # restored after the test; fleet() replaces it


def stop(world, tmp_path, wid, secs, text):  # a stop record for WID appears SECS after the send
    def fire():
        tr = tmp_path / f"{wid}.jsonl"; transcript(tr, text)
        with open(world.sd / "metrics.jsonl", "a") as f:
            f.write(json.dumps({"ev": "stop", "t": world.sent + secs * 1000, "agent_id": wid, "type": "x", "transcript": str(tr), "last": text.splitlines()[0]}) + "\n")
    world.todo.append((secs, fire))


def summary_at(world, path, secs, data):
    world.todo.append((secs, lambda: path.write_text(json.dumps(data) if isinstance(data, dict) else data)))


def staggered(world, tmp_path):
    fleet(world)
    for i in range(1, 5):
        stop(world, tmp_path, f"W{i}", i * 10, "Status: DONE")


def test_wave_waits_for_all(world, tmp_path, capsys):
    staggered(world, tmp_path)
    out = io.wait(world.sd, None, 600000, wave=True)
    assert [r["id"] for r in out] == ["W1", "W2", "W3", "W4"] and "BUSY" not in capsys.readouterr().out


def test_any_needs_one_call_per_finisher(world, tmp_path, capsys):
    staggered(world, tmp_path)
    got = [io.wait(world.sd, None, 600000, any_=True) for _ in range(4)]
    assert [len(g) for g in got] == [1, 1, 1, 1] and capsys.readouterr().out.count("BUSY") == 3


def test_wave_ends_at_first_failure(world, tmp_path, capsys):
    fleet(world, 2)
    stop(world, tmp_path, "W1", 10, "Status: BLOCKED - stuck"); stop(world, tmp_path, "W2", 40, "Status: DONE")
    out = io.wait(world.sd, None, 600000, wave=True)
    assert [r["id"] for r in out] == ["W1"] and "BUSY W2" in capsys.readouterr().out
    assert [r["id"] for r in io.wait(world.sd, None, 600000, wave=True)] == ["W2"]


def test_findings_end_the_wave(world, tmp_path, capsys):
    fleet(world, 2)
    stop(world, tmp_path, "W1", 10, FINDINGS); stop(world, tmp_path, "W2", 40, "Status: DONE")
    out = io.wait(world.sd, None, 600000, wave=True)
    assert [(r["id"], r["findings"]) for r in out] == [("W1", 2)] and "BUSY W2" in capsys.readouterr().out


def test_wave_failure_values():
    assert io.wave_failure({"status": "DONE", "findings": 0}) is False
    assert io.wave_failure({"status": "BLOCKED", "findings": 0}) is True
    assert io.wave_failure({"status": "APPROVED", "findings": 0, "partial": True}) is True
    assert io.wave_failure({"status": "RED", "findings": 0}) is True


def test_tests_green_joins(world, tmp_path, capsys):
    fleet(world, 1); world.fh.states = [{}]
    s = tmp_path / "S.json"
    world.sd.joinpath("fleet.json").write_text(json.dumps({**json.loads(world.sd.joinpath("fleet.json").read_text()), "workers": {}}))
    summary_at(world, s, 6, {"passed": 3, "failed": 0, "mode": "full"})
    out = io.wait(world.sd, None, 600000, wave=True, tests=[str(s)])
    assert [r["status"] for r in out] == ["GREEN"] and f"tests {s} GREEN tests (full): 3 passed, 0 failed" in capsys.readouterr().out


def test_tests_red_ends_wave(world, tmp_path, capsys):
    fleet(world, 1)
    s = tmp_path / "S.json"
    summary_at(world, s, 6, {"passed": 1, "failed": 2, "mode": "full"})
    stop(world, tmp_path, "W1", 100, "Status: DONE")
    out = io.wait(world.sd, None, 600000, wave=True, tests=[str(s)])
    o = capsys.readouterr().out
    assert [r["status"] for r in out] == ["RED"] and f"tests {s} RED" in o and o.index("RED") < o.index("BUSY W1")


def test_half_written_summary_waits(world, tmp_path, capsys):
    fleet(world, 1)
    s = tmp_path / "S.json"; s.write_text('{"pass')
    assert io.wait(world.sd, None, 5000, wave=True, tests=[str(s)]) == [] and f"TIMEOUT W1 tests:{s}" in capsys.readouterr().out


def test_died_run(world, tmp_path, capsys):
    fleet(world, 1)
    s = tmp_path / "S.json"
    p = subprocess.Popen([sys.executable, "-c", "pass"]); p.wait()
    s.with_suffix(".pid").write_text(str(p.pid))
    out = io.wait(world.sd, [], 600000, wave=True, tests=[str(s)])
    assert [r["status"] for r in out] == ["DIED"] and f"tests {s} DIED (pid {p.pid}, no summary); log {s.with_suffix('.log')}" in capsys.readouterr().out


def test_timeout_lists_tests(world, tmp_path, capsys):
    fleet(world, 2); s = tmp_path / "S.json"
    assert io.wait(world.sd, None, 5000, wave=True, tests=[str(s)]) == []
    assert capsys.readouterr().out.strip().splitlines()[-1] == f"TIMEOUT W1 W2 tests:{s}"


def test_any_and_wave_exclusive(world, capsys, monkeypatch):
    monkeypatch.setattr(io.state, "resolve", lambda *a, **k: pytest.fail("state call"))
    assert io.main(["wait", "--any", "--wave"]) == 2
    assert "error: --any and --wave exclude each other" in capsys.readouterr().err


def test_partial_flag_in_result(world, tmp_path):
    fleet(world, 1)
    stop(world, tmp_path, "W1", 10, "Verdict: APPROVED (partial: packet lines unread)")
    out = io.wait(world.sd, None, 600000, wave=True)
    assert out[0]["status"] == "APPROVED" and out[0]["partial"] is True


def test_restore_rearms_wave():
    import fleet_restore
    assert "fleet wait --wave --timeout {WAIT_MS}" in open(fleet_restore.__file__).read()
