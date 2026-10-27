"""metrics.py: the fable and mythos families and their prices; an unknown model is not labelled sonnet."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import metrics  # noqa: E402

PER_M = 1_000_000


def test_fable_family_and_price():
    assert metrics.family("claude-fable-5-1") == "fable"
    p = metrics.load_prices()["fable"]  # per-token: input, output, cache write 5m, cache write 1h, cache read
    assert abs(p[0] * PER_M - 10.0) < 1e-9
    assert abs(p[1] * PER_M - 50.0) < 1e-9
    assert abs(p[4] * PER_M - 0.25) < 1e-9


def test_mythos_same_prices():
    assert metrics.family("claude-mythos-5-1") == "mythos"
    prices = metrics.load_prices()
    assert prices["mythos"] == prices["fable"]


def test_unknown_model_not_labelled_sonnet(tmp_path):
    transcript = tmp_path / "sess.jsonl"
    msg = {"id": "m1", "model": "claude-new-9", "content": [{"type": "text", "text": "x"}],
           "usage": {"input_tokens": 100, "output_tokens": 200, "cache_read_input_tokens": 1000,
                     "cache_creation_input_tokens": 500}}
    transcript.write_text(json.dumps({"type": "assistant", "timestamp": "2026-10-18T10:00:00Z", "message": msg}) + "\n",
                          encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "metrics.jsonl").write_text(json.dumps({"session_transcript": str(transcript)}) + "\n", encoding="utf-8")
    co = metrics.coordinator_record(sl)
    assert set(co["cost_by_model"]) == {"unknown:claude-new-9"}
    # priced as the known family with the highest input price (fable, 10 USD per M input)
    expected = (100 * 10.0 + 200 * 50.0 + 500 * 12.5 + 1000 * 0.25) / PER_M
    assert abs(co["cost_usd"] - expected) < 1e-6


def test_task_record_with_unknown_model_is_not_sonnet(tmp_path):
    agent = tmp_path / "agent.jsonl"
    msg = {"id": "m1", "model": "claude-new-9", "content": [{"type": "text", "text": "Status: DONE"}],
           "usage": {"input_tokens": 100, "output_tokens": 200, "cache_read_input_tokens": 1000,
                     "cache_creation_input_tokens": 500}}
    agent.write_text(json.dumps({"type": "assistant", "timestamp": "2026-10-18T10:00:00Z", "message": msg}) + "\n",
                     encoding="utf-8")
    sl = tmp_path / ".superlite"
    sl.mkdir()
    rows = [{"ev": "launch", "t": 1_700_000_000_000, "agent_id": "a", "type": "superlite:implementer",
             "model": "claude-new-9", "desc": "T1 slug"},
            {"ev": "stop", "t": 1_700_000_050_000, "agent_id": "a", "type": "superlite:implementer",
             "transcript": str(agent), "last": "Status: DONE"}]
    (sl / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    rec = {r["task"]: r for r in metrics.task_records(sl)}["T1"]
    assert rec["model"] == "unknown:claude-new-9"
    expected = (100 * 10.0 + 200 * 50.0 + 500 * 12.5 + 1000 * 0.25) / PER_M
    assert abs(rec["cost_usd"] - expected) < 1e-6
