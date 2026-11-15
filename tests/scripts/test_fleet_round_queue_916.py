"""#916 item 3: a dispatch round starts the workers that fit and queues the rest while a worker is busy, instead of
BLOCKED for every task; #917: the BLOCKED line says when every account's usage is unreadable."""
import pytest
from test_fleet import world, acc  # noqa: F401
from test_fleet_for_dispatch import dwld, FRESH, REAL, _go  # noqa: F401
import fleet
import machine_load as ml

pytestmark = pytest.mark.skipif(REAL, reason="scripted dispatch lines need the in-process fake")
BUSY = "machine busy after 0 s: memory pressure warn, 12% free, floor 15% (9 agents, about 0.4 GB each); largest non-agent process bigd 20.0 GB"
TAIL = "the next round sends it once a worker finishes, or pass --over-limit"


def gate(monkeypatch, answers):
    """ml.gate answers from the list (the last repeats); returns the recorded (what, wait_s) calls."""
    calls = []
    def fake(what, wait_s, over=False, poll_s=10.0):
        calls.append((what, wait_s))
        return answers[min(len(calls) - 1, len(answers) - 1)]
    monkeypatch.setattr(ml, "gate", fake)
    return calls


def test_round_starts_what_fits_and_queues_the_rest(dwld, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"]); capsys.readouterr()
    calls = gate(monkeypatch, [None, BUSY])
    dwld.lines = [("T2", FRESH), ("T3", FRESH), ("T4", FRESH)]
    assert _go(dwld) == 0
    assert capsys.readouterr().out.splitlines() == ["W1 T2 sent", f"QUEUED: T3 not sent ({BUSY}); {TAIL}", f"QUEUED: T4 not sent ({BUSY}); {TAIL}"]
    assert [w for _, w in calls][1:] == [0.0]  # W1 is busy: no wait for room, and T4 is not tried again


def test_a_busy_worker_of_an_earlier_round_queues_without_waiting(dwld, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    gate(monkeypatch, [None])
    dwld.lines = [("T2", FRESH)]
    assert _go(dwld) == 0
    capsys.readouterr()
    calls = gate(monkeypatch, [BUSY])
    dwld.lines = [("T3", FRESH), ("T4", "agent=W9 tier=sonnet")]
    assert _go(dwld) == 3
    assert capsys.readouterr().out.splitlines() == [f"QUEUED: T3 not sent ({BUSY}); {TAIL}", "BLOCKED: T4 not sent (unknown worker W9)"]
    assert calls == [("fleet spawn (implementer)", 0.0)]


def test_no_busy_worker_still_blocks_after_the_wait(dwld, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"]); capsys.readouterr()
    calls = gate(monkeypatch, [BUSY])
    dwld.lines = [("T2", FRESH), ("T3", FRESH)]
    assert _go(dwld) == 3
    out = capsys.readouterr().out.splitlines()
    assert out == [f"BLOCKED: T2 not sent (fleet spawn: {BUSY}; rerun later, or pass --over-limit)", f"BLOCKED: T3 not sent (fleet spawn: {BUSY}; rerun later, or pass --over-limit)"]
    assert calls[0][1] > 99  # nothing in flight frees room: the round waits its budget first


def test_every_account_unreadable_says_so(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    bad = [acc("claude1", 1), acc("claude3", 3)]
    for a in bad:
        a["error"], a["limits"] = "claude exit 1: boom", []
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: {"accounts": bad})
    with pytest.raises(SystemExit) as e:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    out = capsys.readouterr().out.splitlines()
    assert e.value.code == 3
    assert out[0] == "BLOCKED: usage unreadable for every account (claude-profile usage failed); rerun when sl accounts shows a reading"
    assert "claude1: usage unreadable: claude exit 1: boom" in out


def test_a_full_account_among_unreadable_ones_keeps_the_headroom_line(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    bad = acc("claude3", 3); bad["error"], bad["limits"] = "boom", []
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: {"accounts": [acc("claude1", 1, session=99), bad]})
    with pytest.raises(SystemExit):
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert capsys.readouterr().out.splitlines()[0] == "BLOCKED: no account with headroom"
