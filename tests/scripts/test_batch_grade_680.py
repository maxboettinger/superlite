import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import batch_grade as bg  # noqa: E402
import metrics  # noqa: E402

ZERO = {"input": 0, "cache_read": 0, "cache_write": 0, "output": 0, "thinking": 0}


def _fake_usage(path, since=None, until=None, kind=None, prices=None, sidechain=False):
    n = int(Path(path).stem.split("-")[-1]) if Path(path).exists() else 0
    return {"tokens": {"input": n, "cache_read": 10 * n, "cache_write": 0, "output": 5 * n, "thinking": 0}, "cost_usd": n / 1000}


def _sd(tmp_path):
    sd = tmp_path / ".superlite"
    (sd / "fleet" / "reports").mkdir(parents=True)
    return sd


def _rep(sd, name, **kw):
    (sd / "fleet" / "reports" / f"{name}.json").write_text(json.dumps(kw), encoding="utf-8")


def _wire(sd, workers, stops):
    (sd / "fleet.json").write_text(json.dumps({"workers": workers}), encoding="utf-8")
    (sd / "metrics.jsonl").write_text("".join(json.dumps(s) + "\n" for s in stops), encoding="utf-8")


def test_role_from_type_when_fleet_json_lacks_it(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "session_usage", _fake_usage, raising=False)
    sd = _sd(tmp_path)
    t1, t2 = tmp_path / "a-1.jsonl", tmp_path / "b-2.jsonl"
    t1.write_text("x"); t2.write_text("x")
    _wire(sd, {}, [
        {"ev": "launch", "t": 1, "agent_id": "a", "type": "fleet:superlite:fixer-sonnet-high"},
        {"ev": "stop", "t": 2, "agent_id": "a", "type": "fleet:superlite:fixer-sonnet-high", "transcript": str(t1)},
        {"ev": "launch", "t": 1, "agent_id": "b", "type": "superlite:implementer-haiku"},
        {"ev": "stop", "t": 2, "agent_id": "b", "type": "superlite:implementer-haiku", "transcript": str(t2)},
    ])
    w = bg.workers(sd)
    assert set(w) == {"fixer", "implementer"}
    assert w["fixer"]["n"] == 1 and w["fixer"]["tokens"]["input"] == 1
    assert w["implementer"]["cost_usd"] == 0.002


def test_lead_is_not_a_worker(tmp_path, monkeypatch):
    monkeypatch.setattr(metrics, "session_usage", _fake_usage, raising=False)
    sd = _sd(tmp_path)
    _wire(sd, {"w1": {"role": "lead"}, "w2": {"role": "implementer"}}, [
        {"ev": "launch", "t": 1, "agent_id": "w3", "type": "lead"}])
    w = bg.workers(sd)
    assert list(w) == ["implementer"] and w["implementer"]["n"] == 1
    assert w["implementer"]["tokens"] == ZERO


def test_batch_label_counts_each_task(tmp_path):
    sd = _sd(tmp_path)
    _rep(sd, "T1", role="implementer", label="T1,T2", status="DONE")
    q = bg.quality(sd)
    assert q["tasks"] == 2 and q["first_time_pass"] == 2


def test_fixer_label_marks_rework(tmp_path):
    sd = _sd(tmp_path)
    _rep(sd, "T1", role="implementer", label="T1", status="DONE")
    _rep(sd, "F-T1-3", role="fixer", label="F-T1-3", status="DONE")
    q = bg.quality(sd)
    assert q["tasks"] == 1 and q["first_time_pass"] == 0 and q["fixer_rounds"] == 1


def test_findings_int_or_list(tmp_path):
    sd = _sd(tmp_path)
    _rep(sd, "PK1", role="package-reviewer", label="review-T1", findings=2)
    _rep(sd, "PK2", role="package-reviewer", label="review-T2,T3", findings=[{"a": 1}, {"b": 2}])
    assert bg.quality(sd)["package_findings"] == 4


def test_real_fleet_report_shapes(tmp_path):
    sd = _sd(tmp_path)
    _rep(sd, "a", role="implementer", label="T1,T3", status="DONE", findings=5)
    _rep(sd, "b", role="package-reviewer", label="review-T1,T3", status="DONE", findings=2)
    _rep(sd, "c", role="final-reviewer", label="FR1", status="APPROVED", findings=7)
    _rep(sd, "d", role="fixer", label="F-T1-1", status="DONE", findings=3)
    _rep(sd, "e", label="layer-headless", status="DONE", findings=4)
    q = bg.quality(sd)
    assert q["package_findings"] == 2
    assert (q["tasks"], q["first_time_pass"], q["fixer_rounds"], q["final_rounds"]) == (2, 1, 1, 1)


def test_verdicts_by_round_number(tmp_path):
    sd = _sd(tmp_path)
    _rep(sd, "FR10", role="reviewer", label="FR10", status="APPROVED")
    _rep(sd, "FR2", role="reviewer", label="FR2", status="CHANGES_REQUESTED")
    q = bg.quality(sd)
    assert q["final_rounds"] == 2 and q["final_verdicts"] == ["CHANGES_REQUESTED", "APPROVED"]


def test_summary_copy_skipped(tmp_path):
    sd = _sd(tmp_path)
    (sd / "test-summary.json").write_text(json.dumps({"mode": "full", "seconds": 600}))
    (sd / "test-summary-20260101.json").write_text(json.dumps({"mode": "full", "seconds": 300}))
    (sd / "test-summary-b.json").write_text(json.dumps({"mode": "fast", "seconds": 30}))
    assert bg.test_runs(sd) == {"full": 1, "full_min": 5.0, "fast": 1, "fast_min": 0.5}


def test_bad_report_json_skipped(tmp_path):
    sd = _sd(tmp_path)
    (sd / "fleet" / "reports" / "T9.json").write_text("{nope")
    (sd / "test-summary-x.json").write_text("{nope")
    _rep(sd, "T1", role="implementer", label="T1", status="DONE_WITH_CONCERNS")
    assert bg.quality(sd)["first_time_pass"] == 1
    assert bg.test_runs(sd)["full"] == 0


def test_grade_examples():
    q = {"tasks": 3, "first_time_pass": 2, "package_findings": 1, "final_rounds": 2,
         "final_verdicts": ["CHANGES_REQUESTED", "APPROVED"], "fixer_rounds": 2}
    g = bg.grade(q, {"ship_runs": 1, "ship_waits": 3, "questions": 1})
    assert g["points"] == 7 and g["letter"] == "C" and g["ship_reruns"] == 1 and g["ci_red"] == 0
    e = bg.grade({}, {})
    assert e["points"] == 0 and e["letter"] == "A" and e["final_verdicts"] == []
    assert bg.grade({}, {"ship_reds": 1})["letter"] == "B"
    assert bg.grade({"tasks": 9, "first_time_pass": 0}, {})["letter"] == "D"


def test_missing_folder_and_snapshot():
    assert bg.snapshot("/missing") == {
        "workers": {}, "tests": {"full": 0, "full_min": 0.0, "fast": 0, "fast_min": 0.0},
        "quality": {"tasks": 0, "first_time_pass": 0, "package_findings": 0, "final_rounds": 0,
                    "final_verdicts": [], "fixer_rounds": 0}}
