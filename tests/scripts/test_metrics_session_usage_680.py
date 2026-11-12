"""metrics.session_usage reads one session transcript (#680): dedup by message id, thinking from output_tokens_details."""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import metrics  # noqa: E402

T0 = 1794520000.0


def stamp(off):
    return datetime.fromtimestamp(T0 + off, timezone.utc).isoformat().replace("+00:00", "Z")


def entry(mid, off, output=10, details=None, text="hi", thinking=None, side=False, model="claude-opus-4-8", extra=None):
    usage = {"input_tokens": 2, "cache_read_input_tokens": 1500,
             "cache_creation": {"ephemeral_5m_input_tokens": 250, "ephemeral_1h_input_tokens": 0}, "output_tokens": output}
    if details is not None:
        usage["output_tokens_details"] = {"thinking_tokens": details}
    content = [{"type": "text", "text": text}] + ([{"type": "thinking", "thinking": thinking}] if thinking else []) + (extra or [])
    e = {"type": "assistant", "timestamp": stamp(off), "message": {"id": mid, "model": model, "usage": usage, "content": content}}
    if side:
        e["isSidechain"] = True
    return e


def write(tmp_path, entries, raw=None):
    p = tmp_path / "t.jsonl"
    p.write_bytes(b"\n".join(raw or [json.dumps(e).encode() for e in entries]) + b"\n")
    return p


def test_streamed_snapshots_count_once(tmp_path):
    u = metrics.session_usage(write(tmp_path, [entry("m1", 0, 10), entry("m1", 1, 40), entry("m1", 2, 25)]))
    assert u["tokens"]["output"] == 40 and u["turns"] == 1


def test_thinking_from_details_else_text(tmp_path):
    assert metrics.session_usage(write(tmp_path, [entry("m1", 0, 500, details=120)]))["tokens"]["thinking"] == 120
    u = metrics.session_usage(write(tmp_path, [entry("m1", 0, 1, text="", thinking="x" * 350)]))
    assert u["tokens"]["thinking"] == 100 and u["tokens"]["output"] == 100


def test_sidechain_skipped_unless_asked(tmp_path):
    p = write(tmp_path, [entry("m1", 0), entry("m2", 1, side=True)])
    assert metrics.session_usage(p)["turns"] == 1
    assert metrics.session_usage(p, sidechain=True)["turns"] == 2


def test_window_keeps_messages_inside(tmp_path):
    p = write(tmp_path, [entry("a", 0), entry("b", 10), entry("b", 50), entry("c", 20), entry("d", 30)])
    assert metrics.session_usage(p, since=T0 + 10, until=T0 + 20)["turns"] == 2
    assert metrics.session_usage(p, since=T0 + 11)["turns"] == 2


def test_bad_lines_and_non_utf8(tmp_path):
    p = write(tmp_path, None, raw=[b"not json", b"\xff\xfe\x80", json.dumps(entry("m1", 0)).encode()])
    assert metrics.session_usage(p)["turns"] == 1


def test_totals_cost_and_empty(tmp_path):
    p = write(tmp_path, [entry("a", 0, 150, details=60), entry("b", 90, 150, details=60)])
    u = metrics.session_usage(p)
    assert u["tokens"] == {"input": 4, "cache_read": 3000, "cache_write": 500, "output": 300, "thinking": 120}
    assert u["model"] == "opus" and u["wall_s"] == 90.0 and u["first"] == T0 and u["last"] == T0 + 90 and u["kinds"] == {}
    pr = metrics.load_prices()["opus"]
    assert u["cost_usd"] == round(4 * pr[0] + 3000 * pr[4] + 500 * pr[2] + 300 * pr[1], 6)
    e = metrics.session_usage(tmp_path / "missing.jsonl")
    assert e["turns"] == 0 and e["model"] is None and e["wall_s"] is None and e["cost_usd"] == 0.0


def test_kind_groups_turns(tmp_path):
    p = write(tmp_path, [entry("a", 0), entry("b", 1)])
    u = metrics.session_usage(p, kind=lambda blocks: "read")
    assert u["kinds"]["read"]["turns"] == 2 and u["kinds"]["read"]["cost_usd"] == u["cost_usd"]


def test_timestampless_message_not_in_window(tmp_path):
    e = entry("a", 0)
    del e["timestamp"]
    p = write(tmp_path, [e, entry("b", 5)])
    assert metrics.session_usage(p)["turns"] == 2
    assert metrics.session_usage(p, since=T0, until=T0 + 10)["turns"] == 1
    assert metrics.session_usage(p, since=T0 + 11)["turns"] == 0


def test_one_hour_cache_write_priced_at_1h_rate(tmp_path):
    e = entry("a", 0)
    e["message"]["usage"]["cache_creation"] = {"ephemeral_5m_input_tokens": 100, "ephemeral_1h_input_tokens": 400}
    u = metrics.session_usage(write(tmp_path, [e]))
    pr = metrics.load_prices()["opus"]
    assert u["tokens"]["cache_write"] == 500
    assert u["cost_usd"] == round(2 * pr[0] + 1500 * pr[4] + 100 * pr[2] + 400 * pr[3] + 10 * pr[1], 6)
