import sys
import types
from pathlib import Path

import pytest

from backlog_fixtures import APPROVED, batch as b
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402

HEAD = "run end: every batch shipped or parked; "


@pytest.fixture
def rk(tmp_path, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    root = tmp_path / "main"
    (root / ".superlite").mkdir(parents=True)
    ns = types.SimpleNamespace(root=root, sd=root / ".superlite", calls=[], on=True, workers={}, result=0)

    def fmain(argv):
        ns.calls.append(argv)
        if isinstance(ns.result, BaseException):
            raise ns.result
        return ns.result
    monkeypatch.setitem(sys.modules, "fleet", types.SimpleNamespace(main=fmain, hc=types.SimpleNamespace(agent_states=lambda: {}, HerdrError=Exception)))
    monkeypatch.setitem(sys.modules, "fleet_state", types.SimpleNamespace(is_on=lambda sd: ns.on, load=lambda sd: {"workers": ns.workers},
                                                                          name_of=lambda sd, wid, w: w.get("name") or wid))
    monkeypatch.setattr(br, "_root", lambda: root)
    monkeypatch.setattr(br, "_now_ms", lambda: 5000)
    monkeypatch.setattr(br, "sync_main", lambda root, repo="": [])
    return ns


def put(rk, *batches):
    bs.update(bs.path(rk.root), lambda d: d.update({"repo": "o/r", "approved_ship": APPROVED, "batches": list(batches)}))


def end(rk):
    return br.run_end(rk.root, rk.sd, bs.path(rk.root))


def test_run_end_clears_a_fleet_of_stopped_workers(rk):
    put(rk, b("B1", ["a"], "shipped"), b("B2", ["b"], "parked"))
    rk.workers = {"W1": {"state": "stopped"}, "W2": {"state": "stopped"}}
    assert end(rk) == [HEAD + "fleet off (stopped workers cleared: 2)"]
    assert rk.calls == [["off", "--plan", str(rk.sd)]]


def test_run_end_names_fleet_off_for_live_workers(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W1": {"state": "stopped"}, "W10": {"state": "busy"}, "W3": {"state": "idle"}}
    assert end(rk) == [HEAD + "live workers W3 W10 still run: sl fleet off stops and clears them"]
    assert rk.calls == []


def test_run_end_waits_for_open_batches(rk):
    rk.workers = {"W1": {"state": "stopped"}}
    for st in ("planned", "running", "needs_decision"):
        put(rk, b("B1", ["a"], "shipped"), b("B2", ["b"], st))
        assert end(rk) == []
    assert rk.calls == []


def test_run_end_silent(rk, monkeypatch):
    rk.workers = {"W1": {"state": "stopped"}}
    rk.on = False
    put(rk, b("B1", ["a"], "shipped"))
    assert end(rk) == []
    rk.on = True
    put(rk)
    assert end(rk) == []
    put(rk, b("B1", ["a"], "shipped"))
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W2")
    assert end(rk) == [] and rk.calls == []


def test_run_end_reports_a_failed_off(rk):
    put(rk, b("B1", ["a"], "shipped"))
    rk.workers = {"W1": {"state": "stopped"}}
    rk.result = SystemExit(3)
    assert end(rk) == [HEAD + "sl fleet off failed (3): run it again"]


def test_wait_appends_the_run_end_line(rk, capsys, monkeypatch):
    rk.workers = {"W1": {"state": "stopped"}}
    def fake_round(root, sd, p, seen):
        bs.update(p, lambda d: bs.batch(d, "B1").update({"state": "shipped"}))
        return ["B1 shipped PR #1"]
    monkeypatch.setattr(br, "_round", fake_round)
    put(rk, b("B1", ["a"], "running"))
    assert br.main(["wait", "--timeout", "0"]) == 0
    assert capsys.readouterr().out == "B1 shipped PR #1\n" + HEAD + "fleet off (stopped workers cleared: 1)\n"
    put(rk, b("B1", ["a"], "shipped"))
    assert br.main(["wait", "--timeout", "0"]) == 0
    assert capsys.readouterr().out == "no running batch\n" + HEAD + "fleet off (stopped workers cleared: 1)\n"
