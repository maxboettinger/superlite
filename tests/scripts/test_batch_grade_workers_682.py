import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import batch_grade  # noqa: E402


def _transcript(p, mid):
    e = {
        "type": "assistant",
        "isSidechain": True,
        "message": {
            "id": mid,
            "model": "claude-sonnet-4-5",
            "usage": {"input_tokens": 4, "cache_read_input_tokens": 1000, "cache_creation_input_tokens": 200, "output_tokens": 50},
        },
    }
    p.write_text(json.dumps(e) + "\n", encoding="utf-8")


def _fixture(tmp_path):
    sd = tmp_path / "sd"
    sd.mkdir()
    (sd / "fleet.json").write_text(json.dumps({"workers": {"W1": {"role": "implementer"}, "W2": {"role": "fixer"}}}), encoding="utf-8")
    t1 = tmp_path / "w1.jsonl"
    _transcript(t1, "m1")
    lines = [
        {"ev": "launch", "t": 1, "agent_id": "W1", "type": "fleet:superlite:implementer"},
        {"ev": "stop", "t": 2, "agent_id": "W1", "type": "fleet:superlite:implementer", "transcript": str(t1)},
    ]
    return sd, "".join(json.dumps(x) + "\n" for x in lines)


def test_worker_cost_live_file(tmp_path):
    sd, text = _fixture(tmp_path)
    (sd / "metrics.jsonl").write_text(text, encoding="utf-8")
    w = batch_grade.workers(sd)
    assert w["implementer"]["tokens"]["cache_read"] == 1000
    assert w["implementer"]["cost_usd"] > 0


def test_worker_cost_after_run_end(tmp_path):
    sd, text = _fixture(tmp_path)
    r = sd / "runs" / "20261112-101500"
    r.mkdir(parents=True)
    (r / "metrics.jsonl").write_text(text, encoding="utf-8")
    w = batch_grade.workers(sd)
    assert w["implementer"]["tokens"]["cache_read"] == 1000
    assert w["implementer"]["cost_usd"] > 0


def test_two_archived_runs_no_double_count(tmp_path):
    sd, text = _fixture(tmp_path)
    (sd / "metrics.jsonl").write_text(text, encoding="utf-8")
    for n in ("20261112-101500", "20261112-111500"):
        r = sd / "runs" / n
        r.mkdir(parents=True)
        (r / "metrics.jsonl").write_text(text, encoding="utf-8")
    w = batch_grade.workers(sd)
    assert w["implementer"]["tokens"]["cache_read"] == 1000
    assert w["implementer"]["n"] == 1


def test_test_runs_after_run_end(tmp_path):
    sd = tmp_path / "sd"
    r = sd / "runs" / "20261112-101500"
    r.mkdir(parents=True)
    (r / "test-summary-20261112T100000-1-a.json").write_text(json.dumps({"mode": "full", "seconds": 120}), encoding="utf-8")
    (sd / "test-summary-20261112T110000-2-b.json").write_text(json.dumps({"mode": "fast", "seconds": 30}), encoding="utf-8")
    assert batch_grade.test_runs(sd) == {"full": 1, "full_min": 2.0, "fast": 1, "fast_min": 0.5}
