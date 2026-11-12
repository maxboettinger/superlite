import json, sys, types
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run  # noqa: E402
import backlog_ship  # noqa: E402
import backlog_state as bs  # noqa: E402
import ship_lock  # noqa: E402


@pytest.fixture
def calls(monkeypatch):
    c = types.SimpleNamespace(rec=[], snap=[], note=[], main=[])
    bc = types.ModuleType("batch_cost")
    bc.record = lambda root, b, end: c.rec.append((Path(root), dict(b), end))
    bc.save_snapshot = lambda root, bid, wt: c.snap.append((Path(root), bid, str(wt)))
    mc = types.ModuleType("main_cost")
    mc.note_session = lambda root, env=None: c.note.append(Path(root))
    mc.record_main = lambda root, env=None: c.main.append(Path(root))
    monkeypatch.setitem(sys.modules, "batch_cost", bc)
    monkeypatch.setitem(sys.modules, "main_cost", mc)
    monkeypatch.setattr(backlog_run, "_stop", lambda sd, lead: None)
    return c


def mkroot(tmp_path, *batches):
    root = tmp_path / "root"; (root / ".superlite").mkdir(parents=True)
    p = bs.path(root)
    p.write_text(json.dumps({"repo": "", "batches": list(batches)}))
    return root, p


def merge_ctx(root, wt, bid="B1", main=False):
    return {"batch": {"id": bid, "issues": []}, "wt": wt, "root": root, "sd": root / ".superlite", "repo": "", "lock": root / "lock", "pre": [], "main": main}


def merge_env(monkeypatch, tmp_path, rc, seen=None):
    wt = tmp_path / "wt"; wt.mkdir()
    monkeypatch.setattr(backlog_run, "project_cleanup", lambda *a, **k: None)
    monkeypatch.setattr(ship_lock, "release", lambda *a, **k: None)
    monkeypatch.setattr(backlog_ship, "close_jira", lambda *a, **k: [])
    monkeypatch.setattr(backlog_ship, "open_issues", lambda *a, **k: [])

    def fake(cmd, cwd, timeout=None):
        if seen is not None:
            seen.append(seen_path.exists())
        return rc, "merged #5" if rc == 0 else "red"
    seen_path = None
    monkeypatch.setattr(backlog_ship, "_run", fake)
    return wt


def args():
    return types.SimpleNamespace(title="t", body_file=None)


def test_merge_saves_snapshot_before_ship(tmp_path, monkeypatch, calls):
    root, _ = mkroot(tmp_path, {"id": "B1", "state": "running", "issues": []})
    snap = root / ".superlite" / "backlog" / "B1.snapshot.json"
    seen = []
    wt = tmp_path / "wt"; wt.mkdir()
    monkeypatch.setattr(backlog_run, "project_cleanup", lambda *a, **k: None)
    sys.modules["batch_cost"].save_snapshot = lambda r, bid, w: (snap.parent.mkdir(parents=True, exist_ok=True), snap.write_text("{}"))
    monkeypatch.setattr(backlog_ship, "_run", lambda cmd, cwd, timeout=None: (seen.append(snap.exists()) or (3, "red")))
    backlog_ship._merge(args(), merge_ctx(root, wt))
    assert seen == [True]


def test_red_counts_ship_reds(tmp_path, monkeypatch, calls):
    root, p = mkroot(tmp_path, {"id": "B1", "state": "running", "issues": []})
    wt = merge_env(monkeypatch, tmp_path, 3)
    for _ in range(2):
        ctx = merge_ctx(root, wt)
        ctx["batch"] = bs.batch(bs.load(p), "B1")
        backlog_ship._merge(args(), ctx)
    assert bs.batch(bs.load(p), "B1")["ship_reds"] == 2
    assert calls.snap == [(root, "B1", str(wt))] * 2


def test_red_counts_on_main_path(tmp_path, monkeypatch, calls):
    root, p = mkroot(tmp_path, {"id": "B1", "state": "running", "issues": []})
    wt = merge_env(monkeypatch, tmp_path, 3)
    backlog_ship._merge(args(), merge_ctx(root, wt, main=True))
    assert bs.batch(bs.load(p), "B1")["ship_reds"] == 1


def test_snapshot_failure_keeps_merge(tmp_path, monkeypatch, calls):
    root, _ = mkroot(tmp_path, {"id": "B1", "state": "running", "issues": []})
    wt = merge_env(monkeypatch, tmp_path, 3)
    def boom(*a):
        raise RuntimeError("x")
    sys.modules["batch_cost"].save_snapshot = boom
    assert backlog_ship._merge(args(), merge_ctx(root, wt)) == 6


def shipped(tmp_path, monkeypatch, calls, **extra):
    wt = tmp_path / "wt"
    root, p = mkroot(tmp_path, {"id": "B1", "state": "running", "lead": "W1", "issues": [], **extra})
    order = []
    sys.modules["batch_cost"].record = lambda r, b, end: (order.append(("record", end, wt.exists())), calls.rec.append((r, b, end)))
    b = bs.batch(bs.load(p), "B1")
    wt.mkdir()
    monkeypatch.setattr(backlog_run, "project_cleanup", lambda *a, **k: None)
    monkeypatch.setattr(backlog_run, "_run", lambda cmd, cwd, **k: (order.append(("ship", wt.exists())) or (0, "")), raising=False)
    out = backlog_run._shipped(p, root / ".superlite", root, b, wt)
    return calls, order, out


def test_shipped_records_before_cleanup(tmp_path, monkeypatch, calls):
    c, order, _ = shipped(tmp_path, monkeypatch, calls)
    assert [r[2] for r in c.rec] == ["shipped"]
    assert order[0] == ("record", "shipped", True)
    assert [o for o in order if o[0] == "ship"] == [] or order.index(("record", "shipped", True)) == 0


def test_no_change_records_no_change(tmp_path, monkeypatch, calls):
    c, _, _ = shipped(tmp_path, monkeypatch, calls, no_change="nothing to do")
    assert [r[2] for r in c.rec] == ["no-change"]


def test_park_records_parked(tmp_path, monkeypatch, calls):
    root, p = mkroot(tmp_path, {"id": "B1", "state": "running", "lead": "W1", "issues": []})
    out = []
    b = bs.batch(bs.load(p), "B1")
    backlog_run._park(p, root / ".superlite", "", b, "stuck", out)
    assert [(r[0], r[2], r[1]["state"], r[1]["reason"]) for r in calls.rec] == [(root, "parked", "parked", "stuck")]
    assert out == ["B1 parked: stuck"]


def test_round_lead_parked_records_parked(tmp_path, monkeypatch, calls):
    root, p = mkroot(tmp_path, {"id": "B1", "state": "parked", "lead": "W1", "agent": "a1", "reason": "why", "issues": []})
    monkeypatch.setattr(backlog_run.fleet.hc if hasattr(backlog_run, "fleet") else __import__("fleet").hc, "agent_states", lambda: {"a1": 1})
    out = backlog_run._round(root, root / ".superlite", p, {})
    assert [(r[2], r[1]["id"]) for r in calls.rec] == [("parked", "B1")]
    assert out == ["B1 parked: why"]


def test_record_failure_keeps_output(tmp_path, monkeypatch, calls):
    def boom(*a):
        raise RuntimeError("x")
    c, _, good = shipped(tmp_path / "a", monkeypatch, calls) if False else (None, None, None)
    (tmp_path / "a").mkdir(); (tmp_path / "b").mkdir()
    _, _, base = shipped(tmp_path / "a", monkeypatch, calls)
    sys.modules["batch_cost"].record = boom
    _, _, out = shipped(tmp_path / "b", monkeypatch, calls)
    norm = lambda o, d: [x.replace(str(d), "D") for x in o]
    assert norm(out, tmp_path / "b") == norm(base, tmp_path / "a")
    root, p = mkroot(tmp_path / "b" / "c" if False else tmp_path / "pk", {"id": "B1", "state": "running", "lead": "W1", "issues": []}) if (tmp_path / "pk").mkdir() is None else (None, None)
    o = []
    backlog_run._park(p, root / ".superlite", "", bs.batch(bs.load(p), "B1"), "stuck", o)
    assert o == ["B1 parked: stuck"]


def test_run_end_records_main(tmp_path, monkeypatch, calls):
    root, p = mkroot(tmp_path, {"id": "B1", "state": "shipped", "issues": []})
    import fleet_state
    monkeypatch.setattr(fleet_state, "is_on", lambda sd: False)
    assert backlog_run.run_end(root, root / ".superlite", p) == []
    assert calls.main == []
    monkeypatch.setattr(fleet_state, "is_on", lambda sd: True)
    monkeypatch.setattr(fleet_state, "load", lambda sd: {"workers": {}})
    backlog_run.run_end(root, root / ".superlite", p)
    assert calls.main == [root]
