"""metrics.agent_records: sidecar stop events (empty type, no launch) are not counted as agents."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS  # noqa: E402

sys.path.insert(0, str(SCRIPTS))

import metrics  # noqa: E402

IMPL = "superlite:implementer"


def write_metrics(sl, rows):  # O(R)
    sl.mkdir(parents=True, exist_ok=True)  # O(1)
    (sl / "metrics.jsonl").write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")  # O(bytes)


def test_sidecar_stop_skipped(tmp_path):  # O(M)
    sl = tmp_path / ".superlite"  # O(1)
    write_metrics(sl, [
        {"ev": "launch", "agent_id": "i1", "type": IMPL, "desc": "T1 build", "t": 1000},  # O(1)
        {"ev": "stop", "agent_id": "i1", "type": IMPL, "t": 2000},  # O(1)
        {"ev": "stop", "agent_id": "s1", "type": "", "t": 2100},  # O(1)
    ])
    assert [a["agent"] for a in metrics.agent_records(sl)] == ["i1"]  # O(A)


def test_stop_only_with_type_kept(tmp_path):  # O(M)
    sl = tmp_path / ".superlite"  # O(1)
    write_metrics(sl, [{"ev": "stop", "agent_id": "i2", "type": IMPL, "t": 2000}])  # O(1)
    assert [a["agent"] for a in metrics.agent_records(sl)] == ["i2"]  # O(A)


def test_launch_without_type_kept(tmp_path):  # O(M)
    sl = tmp_path / ".superlite"  # O(1)
    write_metrics(sl, [
        {"ev": "launch", "agent_id": "i3", "type": "", "desc": "T3 build", "t": 1000},  # O(1)
        {"ev": "stop", "agent_id": "i3", "type": "", "t": 2000},  # O(1)
    ])
    assert [a["agent"] for a in metrics.agent_records(sl)] == ["i3"]  # O(A)


def test_report_agent_count_ignores_sidecars(tmp_path):  # O(M)
    sl = tmp_path / ".superlite"  # O(1)
    write_metrics(sl, [
        {"ev": "launch", "agent_id": "i1", "type": IMPL, "desc": "T1 build", "t": 1000},  # O(1)
        {"ev": "stop", "agent_id": "i1", "type": IMPL, "t": 2000},  # O(1)
        {"ev": "stop", "agent_id": "s1", "type": "", "t": 2100},  # O(1)
    ])
    assert len(metrics.agent_records(sl)) == 1  # O(A); report.py counts agents with this same call
