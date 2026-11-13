# tests/scripts/test_backlog_run_loop_673.py
import json, sys, types
import pytest
from backlog_fixtures import Q, batch as b
from test_backlog_run import bk, put, get, run, running  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402


@pytest.fixture
def clock(monkeypatch):
    """A fake clock: sleep advances monotonic; sleeps are recorded."""
    t, slept = [0.0], []
    def sleep(s):
        slept.append(s); t[0] += s
    monkeypatch.setattr(br, "time", types.SimpleNamespace(monotonic=lambda: t[0], sleep=sleep, time=lambda: t[0]))
    return slept


def merge_on_spawn(bk, monkeypatch):
    """Every started lead is done with its batch merged by the next round."""
    real = sys.modules["fleet_lead"].spawn_lead
    def spy(sd, wt, model="opus", env=None, rc=None):
        rec = real(sd, wt, model, env, rc)
        bid = wt.name.split("-")[1].upper()
        bs.update(bs.path(bk.root), lambda d: bs.batch(d, bid).update(merged=True, pr=200 + int(bid[1:]), version="1.5.8"))
        bk.stops[rec["id"]] = {"t": 9000, "last": "Status: DONE"}
        bk.states[rec["name"]] = "done"
        return rec
    monkeypatch.setattr(sys.modules["fleet_lead"], "spawn_lead", spy)


def test_run_starts_next_planned_after_ship(bk, capsys, clock):
    running(bk, merged=True, pr=201, version="1.5.8"); bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    put(bk, get(bk, "B1"), b("B2", ["b.py"]))
    rc, out = run(capsys, "run", "--cap", "1", "--timeout", "0", "--poll", "0")
    lines = out.splitlines()
    assert rc == 0 and lines[0].startswith("B1 shipped") and lines[1].startswith("B2 running lead=") and lines[-1] == "TIMEOUT"
    assert get(bk, "B2")["state"] == "running"


def test_run_returns_on_needs_decision(bk, capsys, clock):
    wt = running(bk); q = wt / ".superlite" / "question.json"; q.write_text(json.dumps(Q)); bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "run", "--timeout", "60", "--poll", "0") == (0, f"B1 needs_decision question={q}\n")
    assert clock == []


def test_run_one_call_covers_three_ships(bk, capsys, clock, monkeypatch):
    put(bk, b("B1", ["a.py"]), b("B2", ["b.py"]), b("B3", ["c.py"]))
    merge_on_spawn(bk, monkeypatch)
    rc, out = run(capsys, "run", "--cap", "1", "--timeout", "60", "--poll", "0")
    shipped = [x.split()[0] for x in out.splitlines() if " shipped " in x]
    assert rc == 0 and shipped == ["B1", "B2", "B3"] and out.splitlines()[-1] == "no running batch"
    assert [get(bk, x)["state"] for x in ("B1", "B2", "B3")] == ["shipped"] * 3


def test_run_returns_on_parked(bk, capsys, clock):
    running(bk); bk.stops.clear(); bk.states.clear()
    assert run(capsys, "run", "--timeout", "60", "--poll", "0") == (0, "B1 parked: lead pane gone\n")


def test_run_start_refusal_returns_2(bk, capsys, clock, monkeypatch):
    put(bk, b("B2", ["b.py"]))
    def boom(*a, **k):
        raise SystemExit(3)
    monkeypatch.setattr(sys.modules["fleet_lead"], "spawn_lead", boom)
    assert run(capsys, "run", "--timeout", "60", "--poll", "0") == (2, "BLOCKED: B2 lead did not start; B2 keeps its state, rerun sl backlog start B2\n")


def test_run_retries_disk_refusal(bk, capsys, clock, monkeypatch):
    import trees
    monkeypatch.setattr(trees, "disk_gate", lambda root: ("refuse", "disk: 12 GB free on /r, below the 20 GB floor"))
    running(bk); bk.stops.clear(); bk.states["sl-m-W1"] = "working"
    put(bk, get(bk, "B1"), b("B2", ["b.py"]))
    rc, out = run(capsys, "run", "--timeout", "15", "--poll", "10", "--retry", "5")
    assert rc == 0 and out.count("waiting for disk: B2") == 1 and out.splitlines()[-1] == "TIMEOUT"
    assert len(clock) == 2
    put(bk, b("B2", ["b.py"]))
    rc, out = run(capsys, "run", "--timeout", "15", "--poll", "10")
    assert rc == 0 and out.count("waiting for disk: B2") == 1 and out.splitlines()[-1] == "no running batch"


def test_run_refuses_in_fleet_worker(bk, capsys, monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W3")
    assert run(capsys, "run", "--timeout", "0") == (2, "BLOCKED: sl backlog run runs only in the main session\n")


def test_backlog_cli_routes_run(bk, monkeypatch):
    import backlog
    seen = []
    monkeypatch.setattr(backlog, "_root", lambda: bk.root)
    monkeypatch.setenv("SUPERLITE_LEAD_CAP_LIVE", "0")
    import backlog_cap
    monkeypatch.setattr(backlog_cap, "account_state", lambda *a, **k: ("unknown", []))
    monkeypatch.setenv("SUPERLITE_HOME", str(bk.root / "home"))
    monkeypatch.setattr(br, "main", lambda argv=None: seen.append(argv) or 0)
    assert backlog.main(["run", "--timeout", "0"]) == 0 and seen == [["run", "--timeout", "0", "--cap", "2"]]


def test_run_refreshes_standing_before_each_start(bk, capsys, clock, monkeypatch):
    import backlog
    import backlog_brief
    put(bk, b("B1", ["a.py"]))
    bs.update(bs.path(bk.root), lambda d: bs.set_note(d, "keep it short", "/x", 1))
    monkeypatch.setattr(backlog, "_root", lambda: bk.root)
    got = []
    monkeypatch.setattr(br, "cmd_start", lambda a: got.append(dict(backlog_brief.STANDING)) or 0)
    assert run(capsys, "run", "--timeout", "0")[0] == 0
    assert got and got[0]["note"] == "keep it short"


def test_urgent_and_retry_refusal():
    assert br.urgent("B3 needs_decision question=/w/.superlite/question.json")
    assert br.urgent("B3 parked: lead pane gone")
    assert not br.urgent("B3 shipped PR #9 1.5.181 summary=/r/.superlite/backlog/B3.md")
    assert br.retry_refusal("BLOCKED: waiting for disk: B4 not started: 12 GB free on /r, below the 20 GB floor; sl backlog start B4 (B4 keeps its state)")
    assert br.retry_refusal("BLOCKED: B4 not started: busy; rerun sl backlog start B4, or --over-limit")
    assert br.retry_refusal("BLOCKED: no free slot for B4 (cap 1)")
    assert not br.retry_refusal("BLOCKED: B4 lead did not start; B4 keeps its state, rerun sl backlog start B4")
