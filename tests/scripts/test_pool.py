"""pool.py: add/busy/free/list/sync on pool.json, and dispatch syncing before it plans."""
from __future__ import annotations

import json
import os
import shutil
import sys
import time

import pytest

from test_plan_tools import SCRIPTS, run
from test_stable_split import DISPATCH
from test_wave0 import PY, plan

sys.path.insert(0, str(SCRIPTS))
import pool as poolmod  # noqa: E402 (the swappable seam: real pool.py is the only implementation; SUPERLITE_REAL has no fake to swap)

POOL = SCRIPTS / "pool.py"
FIX = SCRIPTS.parents[2] / "tests" / "scripts" / "fixtures" / "capture_real"
REAL = os.environ.get("SUPERLITE_REAL") == "1"  # noqa: F841


def pl(tmp_path, *args):
    return run(POOL, *args, "--pool", tmp_path / ".superlite" / "pool.json", cwd=tmp_path)


def read(tmp_path):
    return json.loads((tmp_path / ".superlite" / "pool.json").read_text(encoding="utf-8"))


def fixture_transcript(tmp_path, name="agent.jsonl"):
    dst = tmp_path / name
    shutil.copy(FIX / "agent.jsonl", dst)
    return dst


def fixture_k():
    last = [json.loads(x) for x in (FIX / "agent.jsonl").read_text(encoding="utf-8").splitlines()
            if '"type": "assistant"' in x or '"type":"assistant"' in x][-1]["message"]["usage"]
    cc = last["cache_creation"]
    return round((last["input_tokens"] + last["cache_read_input_tokens"]
                  + cc["ephemeral_5m_input_tokens"] + cc["ephemeral_1h_input_tokens"]) / 1000, 1)


def metrics(sl, *stops):
    sl.mkdir(exist_ok=True)
    (sl / "metrics.jsonl").write_text(
        "".join(json.dumps({"ev": "stop", "t": t, "agent_id": aid, "type": "x", "transcript": str(tr), "last": ""}) + "\n"
                for aid, t, tr in stops), encoding="utf-8")


def test_add_busy_free_roundtrip(tmp_path):
    assert poolmod.add({"agents": []}, "a5be", "sonnet", "T3") == {
        "id": "a5be", "tier": "sonnet", "tasks": [], "files": [], "context_k": 20.0, "idle_min": 0, "busy": True, "current": "T3"}
    assert "current" not in poolmod.add({"agents": []}, "x", "haiku") and poolmod.add({"agents": []}, "x", "haiku")["busy"] is False
    assert pl(tmp_path, "add", "a5be", "--tier", "sonnet", "--current", "T3").returncode == 0
    r = pl(tmp_path, "free", "a5be")
    assert r.returncode == 0 and len(r.out.splitlines()) == 1
    ag = read(tmp_path)["agents"][0]
    assert ag["busy"] is False and "current" not in ag and "busy_since" not in ag
    assert pl(tmp_path, "busy", "a5be", "T4").returncode == 0
    ag = read(tmp_path)["agents"][0]
    assert ag["busy"] is True and ag["current"] == "T4" and isinstance(ag["busy_since"], int)
    r = pl(tmp_path, "list")
    assert r.out.strip() == "a5be tier=sonnet busy=True current=T4 tasks=0 context_k=20.0 idle_min=0"
    assert not list((tmp_path / ".superlite").glob("*.tmp"))


def test_add_existing_updates_in_place():
    data = {"agents": [{"id": "a", "tier": "haiku", "tasks": ["T1"], "files": ["f"], "context_k": 40.0, "idle_min": 3, "busy": False}]}
    poolmod.add(data, "a", "sonnet", "T2")
    assert len(data["agents"]) == 1 and data["agents"][0]["tasks"] == ["T1"] and data["agents"][0]["context_k"] == 40.0
    assert data["agents"][0]["tier"] == "sonnet" and data["agents"][0]["current"] == "T2" and data["agents"][0]["busy"] is True


def test_context_k_reads_last_assistant_message(tmp_path):
    assert poolmod.context_k(FIX / "agent.jsonl") == fixture_k() > 0
    empty = tmp_path / "e.jsonl"
    empty.write_text('{"type":"user"}\n', encoding="utf-8")
    assert poolmod.context_k(empty) is None
    assert poolmod.context_k(tmp_path / "missing.jsonl") is None


def test_sync_reads_real_context(tmp_path):
    tr = fixture_transcript(tmp_path)
    sl = tmp_path / ".superlite"
    metrics(sl, ("a5be", 5000, tr))
    data = {"agents": [poolmod.add({"agents": []}, "a5be", "sonnet", "T3")]}
    data["agents"][0]["busy_since"] = 1000
    poolmod.sync(data, sl, 65000)
    ag = data["agents"][0]
    assert ag["context_k"] == fixture_k() and ag["idle_min"] == 1.0 and ag["busy"] is False and ag["current"] == "T3"


def test_sync_matches_transcript_basename(tmp_path):
    tr = fixture_transcript(tmp_path, "agent-a5be.jsonl")
    sl = tmp_path / ".superlite"
    metrics(sl, ("longer-id", 5000, tr))
    data = {"agents": [poolmod.add({"agents": []}, "a5be", "sonnet")]}
    poolmod.sync(data, sl, 5000)
    assert data["agents"][0]["context_k"] == fixture_k()


def test_sync_keeps_busy_when_stop_is_older(tmp_path):
    tr = fixture_transcript(tmp_path)
    sl = tmp_path / ".superlite"
    metrics(sl, ("a5be", 500, tr))
    data = {"agents": [poolmod.add({"agents": []}, "a5be", "sonnet", "T3")]}
    data["agents"][0]["busy_since"] = 1000
    poolmod.sync(data, sl, 2000)
    assert data["agents"][0]["busy"] is True


def test_sync_unreadable_transcript_keeps_context(tmp_path):
    sl = tmp_path / ".superlite"
    metrics(sl, ("a5be", 5000, tmp_path / "gone.jsonl"))
    ag = poolmod.add({"agents": []}, "a5be", "sonnet")
    ag["context_k"] = 44.5
    poolmod.sync({"agents": [ag]}, sl, 65000)
    assert ag["context_k"] == 44.5 and ag["idle_min"] == 1.0


def test_sync_agent_without_stop_is_unchanged(tmp_path):
    tr = fixture_transcript(tmp_path)
    sl = tmp_path / ".superlite"
    metrics(sl, ("other", 5000, tr))
    ag = poolmod.add({"agents": []}, "a5be", "sonnet")
    before = dict(ag)
    poolmod.sync({"agents": [ag]}, sl, 65000)
    assert ag == before


def test_sync_without_metrics_is_noop(tmp_path):
    (tmp_path / ".superlite").mkdir()
    data = {"agents": [poolmod.add({"agents": []}, "a5be", "sonnet", "T3")]}
    before = json.dumps(data)
    assert json.dumps(poolmod.sync(data, tmp_path / ".superlite", 9)) == before
    pl(tmp_path, "add", "a5be", "--tier", "sonnet")
    r = pl(tmp_path, "sync")
    assert r.returncode == 0 and r.out.strip() == "synced 0 agent(s)"


def test_sync_cli_counts_agents(tmp_path):
    tr = fixture_transcript(tmp_path)
    pl(tmp_path, "add", "a5be", "--tier", "sonnet")
    metrics(tmp_path / ".superlite", ("a5be", 5000, tr))
    assert pl(tmp_path, "sync").out.strip() == "synced 1 agent(s)"
    assert read(tmp_path)["agents"][0]["context_k"] == fixture_k()


def test_unknown_agent_exits_2(tmp_path):
    pl(tmp_path, "add", "a5be", "--tier", "sonnet")
    for args in (("busy", "nope", "T1"), ("free", "nope")):
        r = pl(tmp_path, *args)
        assert r.returncode == 2 and len(r.err.strip().splitlines()) == 1 and "nope" in r.err


def test_dispatch_syncs_before_planning(tmp_path):
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    tr = tmp_path / "t.jsonl"
    tr.write_text(json.dumps({"type": "assistant", "message": {"id": "m", "usage": {
        "input_tokens": 10, "cache_read_input_tokens": 20000, "cache_creation_input_tokens": 10000,
        "cache_creation": {"ephemeral_5m_input_tokens": 10000, "ephemeral_1h_input_tokens": 0}}}}) + "\n", encoding="utf-8")
    sl = tmp_path / ".superlite"
    metrics(sl, ("a1", int(time.time() * 1000) - 60000, tr))
    ag = poolmod.add({"agents": []}, "a1", "sonnet")
    ag["context_k"] = 95
    poolmod.save(sl / "pool.json", {"agents": [ag]})
    r = run(DISPATCH, "--plan", p, "--pool", sl / "pool.json", "--ledger", tmp_path / "l.md", cwd=tmp_path)
    assert "evict=" not in r.err
    assert 30.0 <= read(tmp_path)["agents"][0]["context_k"] < 31.0


def test_corrupt_pool_gives_one_stderr_line(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "pool.json").write_text("{not json", encoding="utf-8")
    for args in (("list",), ("sync",), ("busy", "a", "T1")):
        r = pl(tmp_path, *args)
        assert r.returncode != 0 and "Traceback" not in r.err and len(r.err.strip().splitlines()) == 1
    p = plan(tmp_path, "**Tech stack:** Python", "x", PY)
    r = run(DISPATCH, "--plan", p, "--pool", sl / "pool.json", "--ledger", tmp_path / "l.md", cwd=tmp_path)
    assert r.returncode != 0 and "Traceback" not in r.err
