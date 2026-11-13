"""batch cost row: every lead of a batch (#699)."""
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


def _fake_snapshot(sd, prices=None):
    return {"workers": {}, "tests": {"full": 0, "full_min": 0.0, "fast": 0, "fast_min": 0.0}, "quality": dict(Q0)}


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
        monkeypatch.setattr(metrics, "session_usage", lambda path, **k: _usage(*((2, "opus") if "a" in os.path.basename(str(path)) else (3, "sonnet"))), raising=False)
    monkeypatch.delitem(sys.modules, "batch_cost", raising=False)
    mod = importlib.import_module("batch_cost")
    monkeypatch.setattr(mod.fleet_io, "own_stop", lambda rec, worker: True)
    yield mod
    sys.modules.pop("batch_cost", None)


def _root(tmp_path):
    root = tmp_path / "main"
    sd = root / ".superlite"; sd.mkdir(parents=True)
    stops = [{"ev": "stop", "t": 1, "agent_id": "W1", "transcript": "/x/a1.jsonl"},
             {"ev": "stop", "t": 2, "agent_id": "W4", "transcript": "/x/b1.jsonl"}]
    (sd / "metrics.jsonl").write_text("".join(json.dumps(s) + "\n" for s in stops))
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W1": {"role": "lead", "tier": "opus"}, "W4": {"role": "lead", "tier": "sonnet"}}}))
    return root


LEADS = [{"id": "W1", "phase": "plan", "model": "rec-a"}, {"id": "W4", "phase": "build", "model": "rec-b"}]


def test_two_leads_summed(bc, tmp_path):
    row = bc.build_row(_root(tmp_path), {"id": "B1", "lead": "W4", "leads": LEADS}, "shipped")
    assert row["lead"]["turns"] == 5 and row["lead"]["cost_usd"] == pytest.approx(0.05)
    assert [x["model"] for x in row["leads"]] == ["opus", "sonnet"]
    assert row["leads"][1]["phase"] == "build"
    assert all("wall_s" in x for x in row["leads"])
    assert isinstance(row["grade"], dict)


def test_one_lead_unchanged(bc, tmp_path):
    row = bc.build_row(_root(tmp_path), {"id": "B1", "lead": "W1"}, "shipped")
    assert row["lead"]["turns"] == 2 and row["lead"]["model"] == "opus" and row["lead"]["wall_s"] == 30.0
    assert len(row["leads"]) == 1 and row["leads"][0]["phase"] == "single"


def test_report_names_leads(bc, tmp_path):
    import report
    root = _root(tmp_path)
    row = bc.build_row(root, {"id": "B1", "lead": "W4", "leads": LEADS}, "shipped")
    text = report.batches_text([row])
    assert "leads: plan opus $" in text and ", build sonnet $" in text
    one = bc.build_row(root, {"id": "B2", "lead": "W1"}, "shipped")
    assert "leads:" not in report.batches_text([one])


def test_model_falls_back_to_the_record_without_a_transcript(bc, tmp_path):
    root = _root(tmp_path)
    row = bc.build_row(root, {"id": "B1", "lead": "W9", "leads": [{"id": "W9", "phase": "build", "model": "rec-z"}]}, "shipped")
    assert row["leads"][0]["model"] == "rec-z"
