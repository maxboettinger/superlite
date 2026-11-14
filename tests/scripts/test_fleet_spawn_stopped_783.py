"""#783: `fleet spawn` cut short by a signal or an error ends with one BLOCKED line and leaves no worker in `starting`."""
import json, os, signal
import pytest
from test_fleet import world  # noqa: F401
from test_fleet_for_dispatch import dwld, FRESH  # noqa: F401
import fleet
REAL = os.environ.get("SUPERLITE_REAL") == "1"
pytestmark = pytest.mark.skipif(REAL, reason="scripted signals need the in-process fake")
SIGS = (signal.SIGTERM, signal.SIGHUP, signal.SIGINT)


def data(w):
    return json.loads((w.sd / "fleet.json").read_text())


def term_in_start(w):
    orig = w.fh.start_agent
    def start(name, pane_id, argv, timeout_ms=90000):
        os.kill(os.getpid(), signal.SIGTERM)
        return orig(name, pane_id, argv, timeout_ms)
    w.fh.start_agent = start


def test_sigterm_during_start_blocks_and_closes_worker(world, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"]); capsys.readouterr()
    term_in_start(world)
    assert fleet.main(["spawn", "--role", "fixer", "--plan", str(world.sd)]) == 3
    last = capsys.readouterr().out.splitlines()[-1]
    assert last.startswith("BLOCKED: fleet spawn stopped by SIGTERM after ") and "W1 left blocked" in last
    w1 = data(world)["workers"]["W1"]
    assert w1["state"] == "blocked"
    assert ("close_pane", w1["pane_id"]) in world.fh.calls


def test_sigterm_in_machine_gate_blocks(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"]); capsys.readouterr()
    def gate(*a, **k):
        os.kill(os.getpid(), signal.SIGTERM)
    monkeypatch.setattr(fleet.ml, "gate", gate)
    assert fleet.main(["spawn", "--plan", str(world.sd)]) == 3
    last = capsys.readouterr().out.splitlines()[-1]
    assert last.startswith("BLOCKED: fleet spawn stopped by SIGTERM after ")
    assert "left blocked" not in last and "W1" not in last


def test_unexpected_error_blocks(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"]); capsys.readouterr()
    def boom(sd):
        raise RuntimeError("boom")
    monkeypatch.setattr(fleet.fs, "next_id", boom)
    assert fleet.main(["spawn", "--plan", str(world.sd)]) == 3
    cap = capsys.readouterr()
    assert cap.out.splitlines()[-1] == "BLOCKED: fleet spawn: RuntimeError: boom"
    assert "Traceback" in cap.err


def test_for_dispatch_sigterm_blocks(dwld, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"]); capsys.readouterr()
    term_in_start(dwld)
    dwld.lines = [("T2", FRESH)]
    assert fleet.main(["spawn", "--for-dispatch", "--plan", str(dwld.tasks_plan)]) == 3
    last = capsys.readouterr().out.splitlines()[-1]
    assert last.startswith("BLOCKED: fleet spawn stopped by SIGTERM after ") and "W1 left blocked" in last
    assert data(dwld)["workers"]["W1"]["state"] == "blocked"


def test_handlers_restored(world, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"]); capsys.readouterr()
    before = [signal.getsignal(s) for s in SIGS]
    assert fleet.main(["spawn", "--plan", str(world.sd)]) == 0
    assert [signal.getsignal(s) for s in SIGS] == before
    term_in_start(world)
    assert fleet.main(["spawn", "--plan", str(world.sd)]) == 3
    assert [signal.getsignal(s) for s in SIGS] == before
