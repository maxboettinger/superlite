"""Review packet small fixes: dash file entries (#129), recorded summaries never close incidents (#110)."""
from __future__ import annotations

import json

from test_packet_batch import SCRIPTS, inc, log, packet, proj, summ  # noqa: F401


def test_dash_incident_has_no_file_not_found(proj):
    log(proj, [{"kind": "test-failure", "file": "-", "line": 0, "context": "suite red somewhere",
                "resolution": "open", "agent": "T1"}])
    t = packet(proj)
    assert "suite red somewhere" in t and "(file not found)" not in t


def test_recorded_summary_does_not_close_incidents(proj):
    sl = proj / ".superlite"
    log(proj, [{"kind": "test-failure", "file": "-", "line": 0, "context": "run_tests red",
                "resolution": "open", "agent": "run_tests"}])
    summ(sl / "test-summary.json", {})
    d = json.loads((sl / "test-summary.json").read_text(encoding="utf-8"))
    d["recorded"] = "make test"
    (sl / "test-summary.json").write_text(json.dumps(d), encoding="utf-8")
    t = packet(proj)
    assert "run_tests red" in t and "dropped" not in t
