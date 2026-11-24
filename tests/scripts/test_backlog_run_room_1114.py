import sys
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, get, run, running  # noqa: F401
from test_backlog_run_loop_673 import clock  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402

REFUSAL = "BLOCKED: no free slot for B2 (cap 0); rerun once the cap: line shows room"


def test_start_cap_zero_refuses(bk, capsys):
    put(bk, b("B2", ["b.py"]))
    assert run(capsys, "start", "--cap", "0") == (2, REFUSAL + "\n")
    assert get(bk, "B2")["state"] == "planned"


def test_start_cap_zero_without_planned_batch_stays_quiet(bk, capsys):
    put(bk)
    assert run(capsys, "start", "--cap", "0") == (0, "no startable batch\n")


def test_start_full_cap_stays_quiet(bk, capsys):
    running(bk)
    put(bk, get(bk, "B1"), b("B2", ["b.py"]))
    assert run(capsys, "start", "--cap", "1") == (0, "no startable batch\n")


def test_run_waits_for_room_at_cap_zero(bk, capsys, clock):
    put(bk, b("B2", ["b.py"]))
    rc, out = run(capsys, "run", "--cap", "0", "--timeout", "25", "--poll", "10", "--retry", "5")
    assert rc == 0 and out.splitlines() == [REFUSAL, "waiting for room: cap 0; start retried every 5 s until --timeout", "TIMEOUT"]
    assert clock == [10, 10, 10] and get(bk, "B2")["state"] == "planned"


def test_run_starts_once_room_frees(bk, capsys, clock, monkeypatch):
    import backlog_cap
    caps = iter([(0, "cap: 0 (room 0)")])
    monkeypatch.setattr(backlog_cap, "start_cap", lambda *a, **k: next(caps, (1, "cap: 1 (room 2)")))
    put(bk, b("B2", ["b.py"]))
    rc, out = run(capsys, "run", "--timeout", "25", "--poll", "10", "--retry", "5")
    lines = out.splitlines()
    assert lines[:3] == ["cap: 0 (room 0)", REFUSAL, "waiting for room: cap 0; start retried every 5 s until --timeout"]
    assert "cap: 1 (room 2)" in lines and any(x.startswith("B2 running lead=") for x in lines)
    assert get(bk, "B2")["state"] == "running" and "no running batch" not in out


def test_run_ends_when_a_batch_needs_main(bk, capsys, clock):
    put(bk, b("B1", ["a.py"], "needs_decision"), b("B2", ["b.py"]))
    rc, out = run(capsys, "run", "--cap", "0", "--timeout", "25", "--poll", "10")
    assert rc == 0 and "waiting for room" not in out and "no running batch" in out
