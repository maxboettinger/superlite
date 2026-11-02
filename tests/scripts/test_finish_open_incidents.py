"""finish.open_incidents and the report count the same open incidents the review packet shows:
stale TDD-red test failures and superseded (later fixed) locations are not open."""
from __future__ import annotations

import json
import os
import sys
from pathlib import Path

import pytest

from test_metrics_history import setup_run
from test_plan_tools import SCRIPTS, run
from test_routing import mech_plan

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402
import report  # noqa: E402

RESOLVED = {"fixed", "resolved", "closed", "wontfix", "accepted"}


@pytest.fixture(autouse=True)
def superseded_double(monkeypatch):
    """Swappable fake of pt_review.superseded (T2): fake by default, the real one when SUPERLITE_REAL=1."""
    if os.environ.get("SUPERLITE_REAL") == "1":
        return
    import pt_review

    def fake(entries):
        newest = {}
        for e in entries:
            if e.get("kind") != "verified":
                newest[(e.get("file", ""), e.get("line", 0))] = str(e.get("resolution", "")).lower() in RESOLVED
        return {loc for loc, done in newest.items() if done}

    monkeypatch.setattr(pt_review, "superseded", fake)


def entry(file="b.py", line=2, kind="exception", resolution="open", context="boom", **extra):
    e = {"file": file, "line": line, "kind": kind, "resolution": resolution, "context": context}
    e.update(extra)
    return e


def write_log(path, entries, raw=()):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join([json.dumps(e) for e in entries] + list(raw)) + "\n", encoding="utf-8")
    return path


STALE = entry(file="tests/test_a.py", line=1, kind="test-failure", context="test_x failed: AssertionError")
GREEN = {"files": {"tests/test_a.py": [3, 0]}, "failures": []}
RED = {"files": {"tests/test_a.py": [2, 1]}, "failures": ["tests/test_a.py::test_x: AssertionError"]}


def test_stale_tdd_red_dropped(tmp_path):
    log = write_log(tmp_path / "incidents.jsonl", [STALE])
    assert finish.open_incidents(log, GREEN) == []
    assert finish.open_incidents(log, RED) == [STALE]


def test_stale_tdd_red_with_test_path_context(tmp_path):
    e = dict(STALE, context="tests/test_a.py::test_x failed")
    assert finish.open_incidents(write_log(tmp_path / "incidents.jsonl", [e]), GREEN) == []


def test_stale_other_test_still_open(tmp_path):
    other = dict(STALE, context="test_y failed")
    log = write_log(tmp_path / "incidents.jsonl", [other])
    summary = {"files": {"tests/test_a.py": [2, 1]}, "failures": ["tests/test_a.py::test_x: boom"]}
    assert finish.open_incidents(log, summary) == []  # test_y is not among the failures: it is green now
    summary["failures"] = ["tests/test_a.py::test_y: boom"]
    assert finish.open_incidents(log, summary) == [other]


def test_superseded_location_dropped(tmp_path):
    log = write_log(tmp_path / "incidents.jsonl",
                    [entry(file="a.py", line=3), entry(file="a.py", line=3, resolution="fixed")])
    assert finish.open_incidents(log) == []


def test_reopened_location_stays_open(tmp_path):
    first = entry(file="a.py", line=3)
    log = write_log(tmp_path / "incidents.jsonl", [first, entry(file="a.py", line=3, resolution="fixed"), first])
    assert finish.open_incidents(log) == [first, first]


def test_superseded_only_its_own_location(tmp_path):
    keep = entry(file="a.py", line=4)
    log = write_log(tmp_path / "incidents.jsonl",
                    [entry(file="a.py", line=3), keep, entry(file="a.py", line=3, resolution="fixed")])
    assert finish.open_incidents(log) == [keep]


def test_open_kept_without_summary(tmp_path):
    e = entry()
    log = write_log(tmp_path / "incidents.jsonl", [e, entry(kind="verified"), entry(file="c.py", resolution="fixed")],
                    raw=["not json", '"a string"', json.dumps({"no": "file"})])
    assert finish.open_incidents(log) == [e]
    assert finish.open_incidents(log, None) == [e]
    assert finish.open_incidents(tmp_path / "missing.jsonl") == []


def test_stale_test_failure_kept_without_summary(tmp_path):
    log = write_log(tmp_path / "incidents.jsonl", [STALE])
    assert finish.open_incidents(log) == [STALE]


def test_summary_header_matches_filtered_count(tmp_path):
    sl = tmp_path / ".superlite"
    write_log(sl / "incidents.jsonl", [entry(), STALE, dict(STALE, line=2)])
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    (sl / "test-summary.json").write_text(json.dumps(GREEN), encoding="utf-8")
    cp = run(SCRIPTS / "finish.py", "--ledger", sl / "progress.md", "--log", sl / "incidents.jsonl", cwd=tmp_path)
    assert "open incidents: 1 (1 distinct)" in cp.out
    assert "- b.py:2 [exception] boom" in cp.out
    assert "tests/test_a.py" not in cp.out


def test_summary_header_without_test_summary(tmp_path):
    sl = tmp_path / ".superlite"
    write_log(sl / "incidents.jsonl", [entry(), STALE])
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    cp = run(SCRIPTS / "finish.py", "--ledger", sl / "progress.md", "--log", sl / "incidents.jsonl", cwd=tmp_path)
    assert "open incidents: 2 (2 distinct)" in cp.out


def test_summary_follows_latest_pointer(tmp_path):
    sl = tmp_path / ".superlite"
    write_log(sl / "incidents.jsonl", [entry(), STALE])
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    (sl / "test-summary.json").write_text(json.dumps(RED), encoding="utf-8")  # the old fast run: still red
    full = sl / "test-summary-20260101T000000-1-abc.json"
    full.write_text(json.dumps(GREEN), encoding="utf-8")  # the newest full run: green
    (sl / "test-summary.latest").write_text(json.dumps({"summary": str(full), "mode": "full"}), encoding="utf-8")
    text = finish.summary(sl / "progress.md", sl / "incidents.jsonl")
    assert "open incidents: 1 (1 distinct)" in text
    assert finish.load_test_summary(sl) == GREEN


def test_report_open_incidents_filtered(tmp_path):
    plan = mech_plan(tmp_path, 2)
    setup_run(tmp_path)
    sl = tmp_path / ".superlite"
    write_log(sl / "incidents.jsonl", [entry(), STALE, entry(file="a.py", line=3),
                                       entry(file="a.py", line=3, resolution="fixed")])
    (sl / "test-summary.json").write_text(json.dumps(GREEN), encoding="utf-8")
    assert report.collect(plan, sl)["quality"]["open_incidents"] == 1
    (sl / "test-summary.json").write_text(json.dumps(RED), encoding="utf-8")
    assert report.collect(plan, sl)["quality"]["open_incidents"] == 2  # the red test is open again


def test_stale_dropped_before_superseded_like_the_packet(tmp_path):
    """The packet drops stale test failures first, then finds superseded locations: an older open entry at a
    location whose newest non-stale entry is resolved is not open, even when a stale test-failure follows it."""
    older = entry(file="tests/test_a.py", line=1)
    fixed = entry(file="tests/test_a.py", line=1, resolution="fixed")
    log = write_log(tmp_path / "incidents.jsonl", [older, fixed, STALE])
    assert finish.open_incidents(log, GREEN) == []
    assert finish.open_incidents(log, RED) == [older, STALE]  # the red test is open again, so the location is too


def test_pt_review_import_failure_falls_back(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "pt_review", None)  # `import pt_review` now raises ImportError
    sl = tmp_path / ".superlite"
    log = write_log(sl / "incidents.jsonl", [entry(), STALE])
    (sl / "test-summary.json").write_text(json.dumps(GREEN), encoding="utf-8")
    assert finish.load_test_summary(sl) is None
    assert finish.open_incidents(log, GREEN) == [entry(), STALE]  # the plain filter: nothing dropped


def test_malformed_test_summary_keeps_incidents(tmp_path):
    sl = tmp_path / ".superlite"
    write_log(sl / "incidents.jsonl", [entry(), STALE])
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    (sl / "test-summary.json").write_text("{not json", encoding="utf-8")
    cp = run(SCRIPTS / "finish.py", "--ledger", sl / "progress.md", "--log", sl / "incidents.jsonl", cwd=tmp_path)
    assert "open incidents: 2 (2 distinct)" in cp.out
    log = sl / "incidents.jsonl"
    for bad in ({"files": {"tests/test_a.py": [2, 1]}, "failures": 5}, {"files": ["x"]}, ["not", "a", "dict"]):
        assert finish.open_incidents(log, bad) == [entry(), STALE]
