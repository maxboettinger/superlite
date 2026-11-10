"""finish names a review packet older than the full run that changed its test results, and offers the bulk
close `sl incident resolve --kind K --reason R` with the open kinds and agents (#416)."""
import json
import os
import sys
import time

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402

FAST = {"passed": 3, "failed": 1, "skipped": 0, "seconds": 10.0, "mode": "fast", "started": 1000.0,
        "failures": ["tests/test_a.py::test_gone: assert 1 == 2"], "files": {"tests/test_a.py": [2, 1]}}
FULL = {"passed": 10, "failed": 1, "skipped": 0, "seconds": 50.0, "mode": "full", "started": 2100.0,
        "failures": ["tests/test_b.py::test_new: boom"], "files": {"tests/test_a.py": [3, 0], "tests/test_b.py": [6, 1]}}


def clock(t):
    return time.strftime("%H:%M:%S", time.localtime(t))


def run_dir(root, packet_at=2000.0, full=FULL, fast=FAST):
    sl = root / ".superlite"
    sl.mkdir(parents=True)
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    (sl / "test-summary.json").write_text(json.dumps(fast), encoding="utf-8")
    os.utime(sl / "test-summary.json", (1010.0, 1010.0))
    if full is not None:
        p = sl / "test-summary-20261110T100000-1-aaaaaa.json"
        p.write_text(json.dumps(full), encoding="utf-8")
        os.utime(p, (2150.0, 2150.0))
    if packet_at is not None:
        (sl / "review-packet.md").write_text("# packet\n", encoding="utf-8")
        os.utime(sl / "review-packet.md", (packet_at, packet_at))
    return sl


def finish_out(root, sl):
    cp = run(SCRIPTS / "finish.py", "--ledger", sl / "progress.md", "--log", sl / "incidents.jsonl", cwd=root)
    assert cp.returncode == 0, cp.both
    return cp.out


def test_packet_older_than_a_full_run_that_changed_the_results(tmp_path):
    sl = run_dir(tmp_path)
    lines = finish.packet_lines(sl)
    assert lines == [f"review packet: older than the last full run (packet {clock(2000.0)}, full run done {clock(2150.0)}: "
                     "10 passed, 1 failed); rebuild it with `sl plan_tools packet` before trusting its test findings",
                     "- green since the packet: tests/test_a.py::test_gone",
                     "- red since the packet: tests/test_b.py::test_new"]
    out = finish_out(tmp_path, sl)
    assert "\n".join(lines) in out


def test_no_line_when_the_packet_is_newer_than_every_full_run(tmp_path):
    assert finish.packet_lines(run_dir(tmp_path, packet_at=3000.0)) == []


def test_no_line_when_the_full_run_kept_the_packet_results(tmp_path):
    same = dict(FULL, failures=list(FAST["failures"]))
    sl = run_dir(tmp_path, full=same)
    assert finish.packet_lines(sl) == []
    assert "review packet:" not in finish_out(tmp_path, sl)


def test_no_line_without_a_packet_or_a_full_run(tmp_path):
    assert finish.packet_lines(run_dir(tmp_path / "a", packet_at=None)) == []
    assert finish.packet_lines(run_dir(tmp_path / "b", full=None)) == []
    assert finish.packet_lines(tmp_path / "missing") == []


def test_a_recorded_or_timeless_full_run_is_ignored(tmp_path):
    assert finish.packet_lines(run_dir(tmp_path / "a", full=dict(FULL, recorded=True))) == []
    timeless = {k: v for k, v in FULL.items() if k != "started"}
    assert finish.packet_lines(run_dir(tmp_path / "b", full=timeless)) == []


def test_more_than_five_changes_are_cut(tmp_path):
    fast = dict(FAST, failures=[f"tests/test_a.py::test_{i}: x" for i in range(7)])
    lines = finish.packet_lines(run_dir(tmp_path, fast=fast, full=dict(FULL, failures=[], failed=0)))
    assert len(lines) == 7 and lines[-1] == "- (+2 more)"
    assert lines[1] == "- green since the packet: tests/test_a.py::test_0"


def test_finish_offers_the_bulk_close_with_the_open_kinds_and_agents(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    rows = [{"file": "src/x.py", "line": 5, "kind": "exception", "agent": "probe_run", "context": "probe crash", "resolution": "open"},
            {"file": "src/y.py", "line": 6, "kind": "perf", "agent": "probe_run", "context": "probe hang", "resolution": "open"},
            {"file": "src/y.py", "line": 6, "kind": "perf", "agent": "probe_run", "context": "probe hang", "resolution": "open"},
            {"file": "src/z.py", "line": 7, "kind": "exception", "context": "boom"}]
    (sl / "incidents.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = finish_out(tmp_path, sl)
    close_one = "- close one: sl incident resolve --file F --line N --ruling \"TEXT\" (file and line as listed)"
    bulk = ("- close all of one kind or tool: sl incident resolve --kind K --reason \"TEXT\" "
            "(open by kind: exception=2, perf=1; by agent: probe_run=2)")
    assert f"{close_one}\n{bulk}" in out
    assert finish.bulk_close_line([]) is None
    assert finish.bulk_close_line([rows[3]]) == ("- close all of one kind or tool: sl incident resolve --kind K "
                                                 "--reason \"TEXT\" (open by kind: exception=1)")


def test_no_bulk_line_without_open_incidents(tmp_path):
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "progress.md").write_text("# Progress ledger\n", encoding="utf-8")
    assert "--kind K" not in finish_out(tmp_path, sl)
