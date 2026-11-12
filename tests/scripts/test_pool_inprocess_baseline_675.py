"""#675: pool.sync stores baseline_k (the READY context) for an in-process agent, so eviction counts only what it added."""
import json
import sys
import time

import pytest

from test_plan_tools import SCRIPTS, make_plan

sys.path.insert(0, str(SCRIPTS))
import assign  # noqa: E402
import dispatch  # noqa: E402
import pool  # noqa: E402


def rec(kind, **kw):
    return json.dumps({"type": kind, **kw})


def asst(text, usage):
    content = text if isinstance(text, str) else [{"type": "text", "text": text[0]}]
    return rec("assistant", message={"role": "assistant", "content": content, "usage": usage})


def transcript(path, ready_k=49.0, end_k=55.0, first_text="READY"):
    ready_usage = {"input_tokens": 3, "cache_read_input_tokens": int(ready_k * 1000) - 3 - 8997, "cache_creation_input_tokens": 8997}
    lines = [
        rec("user", message={"role": "user", "content": "Read /x/.superlite/prime.md, then reply READY"}),
        asst([first_text], ready_usage),
        json.dumps({"type": "user", "isMeta": True, "origin": {"kind": "coordinator"}, "message": {"role": "user", "content": [
            {"type": "text", "text": "The coordinator sent a message while you were working: Task T2"}]}}),
        asst(["DONE"], {"input_tokens": 5, "cache_read_input_tokens": int(end_k * 1000) - 5}),
    ]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def metrics(sd, tr, t=1000):
    sd.mkdir(exist_ok=True)
    (sd / "metrics.jsonl").write_text(json.dumps({"ev": "stop", "t": t, "agent_id": "a1", "type": "superlite:implementer",
                                                  "transcript": str(tr), "last": "DONE"}) + "\n", encoding="utf-8")


def agent(**kw):
    return {"id": "a1", "tier": "sonnet", "tasks": ["T1"], "files": [], "context_k": 20, "idle_min": 0, "busy": False, **kw}


def test_ready_k_reads_first_ready_reply(tmp_path):
    assert pool.ready_k(str(transcript(tmp_path / "agent-a1.jsonl"))) == 49.0


def test_ready_k_none_when_first_text_is_not_ready(tmp_path):
    p = transcript(tmp_path / "agent-a1.jsonl", first_text="Working on T2")
    with p.open("a", encoding="utf-8") as f:
        f.write(asst(["READY"], {"input_tokens": 1}) + "\n")
    assert pool.ready_k(str(p)) is None


def test_ready_k_missing_file(tmp_path):
    assert pool.ready_k(str(tmp_path / "missing.jsonl")) is None


def test_ready_k_skips_bad_lines(tmp_path):
    p = transcript(tmp_path / "agent-a1.jsonl")
    p.write_text("not json\n" + p.read_text(encoding="utf-8"), encoding="utf-8")
    assert pool.ready_k(str(p)) == 49.0


def test_ready_k_string_content(tmp_path):
    p = tmp_path / "agent-a1.jsonl"
    usage = {"input_tokens": 3, "cache_read_input_tokens": 40000, "cache_creation_input_tokens": 8997}
    p.write_text(asst("READY\n", usage) + "\n", encoding="utf-8")
    assert pool.ready_k(str(p)) == 49.0


def test_context_k_unchanged(tmp_path):
    assert pool.context_k(str(transcript(tmp_path / "agent-a1.jsonl"))) == 55.0


@pytest.mark.parametrize("end_k,expect", [(55.0, None), (129.0, "context over 80k")])
def test_sync_fills_in_process_baseline(tmp_path, end_k, expect):
    sd = tmp_path / ".superlite"
    metrics(sd, transcript(tmp_path / "agent-a1.jsonl", end_k=end_k))
    data = {"agents": [agent()]}
    pool.sync(data, sd, 2000)
    ag = data["agents"][0]
    assert ag["baseline_k"] == 49.0
    assert ag["context_k"] == end_k
    assert assign.eligibility(ag, 20.0, None, 2.0) == expect


def test_sync_keeps_existing_baseline(tmp_path):
    sd = tmp_path / ".superlite"
    metrics(sd, transcript(tmp_path / "agent-a1.jsonl"))
    data = {"agents": [agent(baseline_k=30.0)]}
    pool.sync(data, sd, 2000)
    assert data["agents"][0]["baseline_k"] == 30.0


def test_sync_never_reads_ready_for_herdr(tmp_path, monkeypatch):
    sd = tmp_path / ".superlite"
    metrics(sd, transcript(tmp_path / "agent-a1.jsonl"))

    def boom(*a, **k):
        raise AssertionError("ready_k called")
    monkeypatch.setattr(pool, "ready_k", boom)
    data = {"agents": [agent(backend="herdr")]}
    pool.sync(data, sd, 2000)
    assert "baseline_k" not in data["agents"][0]


def test_sync_no_ready_reply_keeps_fallback(tmp_path):
    sd = tmp_path / ".superlite"
    metrics(sd, transcript(tmp_path / "agent-a1.jsonl", first_text="DONE"))
    data = {"agents": [agent()]}
    pool.sync(data, sd, 2000)
    assert "baseline_k" not in data["agents"][0]


def dworld(tmp_path, end_k):
    plan = make_plan(tmp_path, [{"id": "T1", "owns": "src/t1.py"}, {"id": "T2", "owns": "src/t2.py"}])
    sd = tmp_path / ".superlite"
    metrics(sd, transcript(tmp_path / "agent-a1.jsonl", end_k=end_k), t=time.time() * 1000)  # a fresh stop: not idle
    pf = sd / "pool.json"
    pf.write_text(json.dumps({"agents": [agent()]}), encoding="utf-8")
    ledger = sd / "progress.md"
    ledger.write_text("", encoding="utf-8")
    return plan, pf, ledger


def test_dispatch_keeps_in_process_agent_after_one_task(tmp_path):
    plan, pf, ledger = dworld(tmp_path, 55.0)
    lines, evict = dispatch.run(plan, pf, ledger, committed="T1", gate=False)
    assert "a1" not in evict
    assert any("a1" in str(ln) for ln in lines)
    assert json.loads(pf.read_text(encoding="utf-8"))["agents"][0]["baseline_k"] == 49.0


def test_dispatch_evicts_in_process_agent_past_80k_added(tmp_path):
    plan, pf, ledger = dworld(tmp_path, 129.0)
    lines, evict = dispatch.run(plan, pf, ledger, committed="T1", gate=False)
    assert evict["a1"] == "context over 80k"


def test_ready_k_blank_text_before_ready_is_skipped(tmp_path):
    p = tmp_path / "agent-a1.jsonl"
    usage = {"input_tokens": 1, "cache_read_input_tokens": 1000}
    p.write_text(asst(["  "], usage) + "\n" + asst(["READY"], {"input_tokens": 3, "cache_read_input_tokens": 48997}) + "\n", encoding="utf-8")
    assert pool.ready_k(str(p)) == 49.0
