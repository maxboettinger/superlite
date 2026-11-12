import importlib, json, os, sys, types
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import metrics  # noqa: E402

TOK0 = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "thinking": 0}
WAKE0 = {"report": 0, "busy": 0, "timeout": 0, "test_wait": 0, "lock": 0, "prompt": 0}
Q0 = {"tasks": 0, "first_time_pass": 0, "package_findings": 0, "final_rounds": 0, "final_verdicts": [], "fixer_rounds": 0}


def _usage(turns, model="opus"):
    t = dict(TOK0, input=turns, output=100 * turns, thinking=10 * turns)
    return {"turns": turns, "tokens": t, "cost_usd": 0.01 * turns, "model": model, "first": 1.0, "last": 31.0, "wall_s": 30.0,
            "kinds": {"wait": {"turns": turns, "cost_usd": 0.01 * turns}}}


def _fake_snapshot(sd, prices=None):  # fake batch_grade.snapshot: reads a marker file
    p = os.path.join(str(sd), "marker.json")
    if not os.path.isfile(p):
        return {"workers": {}, "tests": {"full": 0, "full_min": 0.0, "fast": 0, "fast_min": 0.0}, "quality": dict(Q0)}
    return json.load(open(p))


def _fake_grade(q, b):
    return dict(Q0, **q, ci_red=0, ship_reruns=0, ship_waits=0, questions=0, points=0, letter="A")


@pytest.fixture
def bc(monkeypatch):
    if os.environ.get("SUPERLITE_REAL") != "1":
        w = types.ModuleType("batch_waits")
        w.lead_kind = lambda blocks: "wait"
        w.waits = lambda p: {"wakeups": dict(WAKE0, report=1), "blocked_wait_s": 5.0}
        g = types.ModuleType("batch_grade")
        g.snapshot, g.grade = _fake_snapshot, _fake_grade
        monkeypatch.setitem(sys.modules, "batch_waits", w)
        monkeypatch.setitem(sys.modules, "batch_grade", g)
        monkeypatch.setattr(metrics, "session_usage", lambda path, **k: _usage(2 if "a" in os.path.basename(str(path)) else 3), raising=False)
    monkeypatch.delitem(sys.modules, "batch_cost", raising=False)
    mod = importlib.import_module("batch_cost")
    yield mod
    sys.modules.pop("batch_cost", None)


def _root(tmp_path, stops=(), argv=None):
    root = tmp_path / "main"
    sd = root / ".superlite"; sd.mkdir(parents=True)
    (sd / "metrics.jsonl").write_text("".join(json.dumps(s) + "\n" for s in stops))
    w = {"role": "lead", "tier": "opus"}
    if argv:
        w["launch"] = {"argv": argv}
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W3": w}}))
    return root


def _stop(name, wid="W3"):
    return {"ev": "stop", "t": 1000, "agent_id": wid, "transcript": f"/x/{name}.jsonl"}


def _wt(tmp_path, marker):
    wt = tmp_path / "wt"; (wt / ".superlite").mkdir(parents=True)
    (wt / ".superlite" / "marker.json").write_text(json.dumps(marker))
    return wt


MARK = {"workers": {"implementer": {"n": 2, "tokens": dict(TOK0, output=50), "cost_usd": 0.4}},
        "tests": {"full": 1, "full_min": 2.0, "fast": 3, "fast_min": 0.5}, "quality": dict(Q0, tasks=2)}


def test_snapshot_used_when_worktree_gone(bc, tmp_path):
    root = _root(tmp_path)
    snap = root / ".superlite" / "backlog" / "B1.snapshot.json"
    snap.parent.mkdir(parents=True); snap.write_text(json.dumps(MARK))
    row = bc.build_row(root, {"id": "B1", "lead": "W3", "worktree": str(tmp_path / "gone")}, "shipped")
    assert row["workers"]["implementer"]["n"] == 2 and row["workers_total"]["n"] == 2 and row["workers_total"]["cost_usd"] == 0.4
    assert row["tests"]["full"] == 1 and row["grade"]["tasks"] == 2


def test_fresh_worktree_wins_and_is_saved(bc, tmp_path):
    root = _root(tmp_path)
    snap = root / ".superlite" / "backlog" / "B1.snapshot.json"
    snap.parent.mkdir(parents=True); snap.write_text(json.dumps({**MARK, "workers": {}}))
    wt = _wt(tmp_path, MARK)
    row = bc.build_row(root, {"id": "B1", "lead": "W3", "worktree": str(wt)}, "parked")
    assert row["workers_total"]["n"] == 2
    assert json.loads(snap.read_text())["workers"]["implementer"]["n"] == 2
    assert bc.save_snapshot(root, "B1", wt) == snap
    assert bc.save_snapshot(root, "B1", tmp_path / "nope") is None


def test_two_lead_transcripts_sum(bc, tmp_path, monkeypatch):
    root = _root(tmp_path, [_stop("a1"), _stop("a1"), _stop("b1"), _stop("child"), _stop("z", "W9")])
    monkeypatch.setattr(bc.fleet_io, "own_stop", lambda rec, worker: "child" not in rec["transcript"])
    row = bc.build_row(root, {"id": "B1", "lead": "W3"}, "shipped")
    lead = row["lead"]
    assert lead["turns"] == 5 and lead["tokens"]["input"] == 5 and lead["tokens"]["thinking"] == 50
    assert lead["wall_s"] == 60.0 and lead["blocked_wait_s"] == 10.0 and lead["wakeups"]["report"] == 2
    assert lead["kinds"]["wait"]["turns"] == 5 and lead["model"] == "opus"


def test_effort_from_launch_argv(bc, tmp_path):
    assert bc.build_row(_root(tmp_path, argv=["claude", "--effort", "high"]), {"id": "B1", "lead": "W3"}, "shipped")["lead"]["effort"] == "high"
    r2 = tmp_path / "two"; r2.mkdir()
    assert bc.build_row(_root(r2), {"id": "B1", "lead": "W3"}, "shipped")["lead"]["effort"] is None


def test_record_never_raises(bc, tmp_path):
    root = _root(tmp_path)
    assert bc.record(root, {"lead": "W3"}, "parked") is None
    assert not bc.costs_path(root).exists()


def test_record_appends_and_read_rows(bc, tmp_path):
    root = _root(tmp_path)
    assert bc.read_rows(tmp_path / "missing") == []
    r = bc.record(root, {"id": "B1", "issues": [7], "lead": "W3", "pr": 9, "version": "1.0.1"}, "shipped")
    assert r["batch"] == "B1" and r["row"] == "batch" and r["end"] == "shipped" and r["v"] == 1 and r["issues"] == [7]
    bc.costs_path(root).open("a").write("not json\n[1]\n")
    bc.record(root, {"id": "B2"}, "parked")
    assert [x["batch"] for x in bc.read_rows(root)] == ["B1", "B2"]
    assert bc.costs_path(root) == root / ".superlite" / "batch-costs.jsonl"


def test_row_has_no_paths(bc, tmp_path):
    root = _root(tmp_path, [_stop("a1")])
    row = bc.build_row(root, {"id": "B1", "lead": "W3", "worktree": str(_wt(tmp_path, MARK))}, "shipped")
    def walk(v):
        if isinstance(v, dict):
            for x in v.values():
                yield from walk(x)
        elif isinstance(v, list):
            for x in v:
                yield from walk(x)
        else:
            yield v
    assert not [v for v in walk(row) if isinstance(v, str) and v.startswith("/")]


def test_lead_counts_only_batch_worktree_transcripts(bc, tmp_path):
    wt, other = tmp_path / "wt", tmp_path / "other-wt"
    mine = f"/x/{bc.fleet_io.project_dir(wt)}/a1.jsonl"
    theirs = f"/x/{bc.fleet_io.project_dir(other)}/b1.jsonl"
    stops = [{"ev": "stop", "t": 1, "agent_id": "W2", "transcript": mine},
             {"ev": "stop", "t": 2, "agent_id": "W2", "transcript": theirs}]
    root = tmp_path / "main"
    sd = root / ".superlite"; sd.mkdir(parents=True)
    (sd / "metrics.jsonl").write_text("".join(json.dumps(s) + "\n" for s in stops))
    (sd / "fleet.json").write_text(json.dumps({"workers": {}}))
    row = bc.build_row(root, {"id": "B1", "lead": "W2", "worktree": str(wt)}, "shipped")
    assert row["lead"]["turns"] == 2
