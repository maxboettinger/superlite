"""#560: backlog start gates each lead on the machine limit and registers it; wait names machine-caused parks."""
import sys
import types

import pytest
from backlog_fixtures import batch as b
from test_backlog_run import bk, get, put, run  # noqa: F401  (bk is a fixture)
import backlog_run as br


@pytest.fixture
def ml(monkeypatch):
    ns = types.SimpleNamespace(gates=[], busy=set())

    def gate(what, wait_s, over=False, poll_s=10.0):
        ns.gates.append((what, wait_s, over))
        return "machine busy after 0 s: memory 10% free, floor 15% (23 agents, about 0.7 GB each)" if what.split()[-1] in ns.busy else None
    ns.gate = gate
    monkeypatch.setitem(sys.modules, "machine_load", ns)
    return ns


def test_start_gates_each_lead(bk, ml, capsys):
    put(bk, b("B7", ["a.py"]), b("B8", ["b.py"]))
    ml.busy = {"B8"}
    rc, out = run(capsys, "start", "B7", "B8", "--cap", "8")
    assert rc == 2
    assert "BLOCKED: B8 not started: machine busy after 0 s: memory 10% free, floor 15% (23 agents, about 0.7 GB each); rerun sl backlog start B8, or --over-limit" in out
    assert (get(bk, "B7")["state"], get(bk, "B8")["state"]) == ("running", "planned")
    assert [g[0] for g in ml.gates] == ["backlog start B7", "backlog start B8"]
    assert not any(c[0] == "spawn" and "b8" in c[1] for c in bk.calls)


def test_over_limit_and_wait_budget(bk, ml, capsys):
    put(bk, b("B1", ["a.py"]))
    run(capsys, "start", "B1", "--over-limit", "--machine-wait", "40")
    what, wait_s, over = ml.gates[0]
    assert over is True and 0 < wait_s <= 40
    put(bk, b("B2", ["a.py"]))
    ml.gates.clear()
    run(capsys, "start", "B2")
    assert ml.gates[0][1] <= 100 and ml.gates[0][1] > 90 and ml.gates[0][2] is False


@pytest.mark.parametrize("reason", ["runner offline", "offline runner", "no GUI session", "Login Session gone", "WindowServer died", "RUNNER OFFLINE"])
def test_machine_park_line(reason):
    assert br.machine_park_line([f"B3 parked: {reason}"]).startswith("machine: ")


def test_machine_park_line_text():
    got = br.machine_park_line(["B3 parked: PR not merged: runner offline", "B5 parked: runner offline", "B6 shipped pr=12"])
    assert got == "machine: runner offline parks B3, B5; fix the machine first, then sl backlog start B3 B5"
    assert br.machine_park_line(["B3 parked: tests red"]) is None


def test_round_prepends_machine_line(bk, ml, capsys, monkeypatch):
    put(bk, b("B3", ["a.py"], "running"))
    monkeypatch.setattr(br, "_round", lambda *a: ["B3 parked: runner offline"])
    rc, out = run(capsys, "wait")
    assert out.splitlines() == ["machine: runner offline parks B3; fix the machine first, then sl backlog start B3",
                                "B3 parked: runner offline"]
