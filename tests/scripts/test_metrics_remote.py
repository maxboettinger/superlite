"""metrics: mirrored remote stop records (`<sd>/remote/<wid>/metrics.jsonl`) count like local ones."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

import metrics  # noqa: E402

IMPL = "superlite:implementer"


def jl(path, rows):  # O(R)
    path.parent.mkdir(parents=True, exist_ok=True)  # O(1)
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")  # O(bytes)


def transcript(path):  # O(1)
    jl(path, [{"type": "assistant", "message": {"id": "m1", "model": "claude-sonnet-4-5", "content": [{"type": "text", "text": "hi"}],
                                                "usage": {"input_tokens": 1000, "output_tokens": 500}}}])  # O(1)


def test_remote_records_counted(tmp_path):  # O(1)
    sd = tmp_path / ".superlite"  # O(1)
    jl(sd / "metrics.jsonl", [{"ev": "launch", "agent_id": "W3", "type": IMPL, "desc": "T1 build", "t": 1000}])  # O(1)
    tr = sd / "remote" / "W3" / "s.jsonl"  # O(1)
    transcript(tr)  # O(1)
    jl(sd / "remote" / "W3" / "metrics.jsonl", [{"ev": "stop", "agent_id": "W3", "type": IMPL, "t": 2000, "transcript": str(tr)}])  # O(1)
    recs = metrics.agent_records(sd)  # O(1)
    assert [a["agent"] for a in recs] == ["W3"] and recs[0]["complete"] and len(recs[0]["segments"]) == 1  # O(1)
    assert metrics.agents_cost(sd) > 0  # O(1)


def test_local_only_unchanged(tmp_path):  # O(1)
    sd = tmp_path / ".superlite"  # O(1)
    jl(sd / "metrics.jsonl", [{"ev": "launch", "agent_id": "i1", "type": IMPL, "desc": "T1", "t": 1000},
                              {"ev": "stop", "agent_id": "i1", "type": IMPL, "t": 2000}])  # O(1)
    recs = metrics.agent_records(sd)  # O(1)
    assert [a["agent"] for a in recs] == ["i1"] and recs[0]["segments"] == [] and metrics.agents_cost(sd) == 0  # O(1)
