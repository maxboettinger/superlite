"""finish.unblocked_report measures each task from the lint that offered it; summary hints at takeover (#375)."""
from __future__ import annotations

import json
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402

DAY = "2026-11-09"
YES = "unblocked: yes - every stable task was dispatched before the next patch; "
NOLINES = "max lag n/a (no `unblocked:` lines)"


def entry(when, pending, newly=None):
    t = when if "T" in when else f"{DAY}T{when}"
    return {"time": t, "stable": 1, "fix": 0, "stable_ids": pending, "newly_stable": pending if newly is None else newly,
            "dispatched": [], "pending": pending}


def report(tmp_path, lints, ledger_lines):
    lp, led = tmp_path / "lint-log.jsonl", tmp_path / "progress.md"
    lp.write_text("".join(json.dumps(e) + "\n" for e in lints), encoding="utf-8")
    led.write_text("".join(ln + "\n" for ln in ledger_lines), encoding="utf-8")
    return finish.unblocked_report(led, lp)


def test_lag_from_offering_lint(tmp_path):
    out = report(tmp_path, [entry("10:00:05", ["T1"], ["T1", "T2"]), entry("10:30:00", ["T2"], [])],
                 ["- unblocked: dispatched T1 at 10:00:12; waiting on fixes: none", "- commit T1 abc1234 one",
                  "- unblocked: dispatched T2 at 10:30:09; waiting on fixes: none"])
    assert out == YES + "max lag 9s"


def test_held_names_evidence(tmp_path):
    out = report(tmp_path, [entry("14:04:18", ["D1", "F1"]), entry("14:10:02", ["D1", "F1", "H1"])],
                 ["- unblocked: dispatched D1 F1 at 14:26:29; waiting on fixes: none",
                  "- unblocked: dispatched H1 at 14:26:30; waiting on fixes: none"])
    assert out == ("unblocked: NO - D1 F1 still waiting at the next lint (offered 14:04:18, next lint 14:10:02, "
                   "sent 14:26:29); max lag 1331s")


def test_held_never_logged(tmp_path):
    out = report(tmp_path, [entry("10:00:05", ["T4"]), entry("10:03:30", ["T4"])], [])
    assert out == ("unblocked: NO - T4 still waiting at the next lint (offered 10:00:05, next lint 10:03:30, "
                   "no unblocked: line names it); max lag n/a (no `unblocked:` lines)")


def test_logged_before_next_lint_satisfies(tmp_path):
    out = report(tmp_path, [entry("10:00:05", ["T1"]), entry("10:05:00", ["T1"])],
                 ["- unblocked: dispatched T1 at 10:00:40"])
    assert out == YES + "max lag 35s"


def test_commit_counts_as_dispatched(tmp_path):
    out = report(tmp_path, [entry("10:00:05", ["T1"])], ["- commit T1 abcdef1 x"])
    assert out == YES + NOLINES


def test_never_dispatched(tmp_path):
    out = report(tmp_path, [entry("10:00:05", ["T2"])], [])
    assert out == ("unblocked: NO - never dispatched: T2 (pending at the last lint 10:00:05; no unblocked: line or "
                   "commit names them); " + NOLINES)


def test_clock_forward_over_midnight(tmp_path):
    out = report(tmp_path, [entry("2026-11-08T23:50:00", ["T1"])], ["- unblocked: dispatched T1 at 00:05:00"])
    assert out.endswith("max lag 900s")
    out = report(tmp_path, [entry("14:04:18", ["T1"])], ["- unblocked: dispatched T1 at 13:59:00"])
    assert out.endswith("max lag 0s")


def test_more_than_three_groups(tmp_path):
    lints = [entry("10:00:00", ["A1"]), entry("10:01:00", ["A1", "B1"]), entry("10:02:00", ["B1", "C1"]),
             entry("10:03:00", ["C1", "D1"]), entry("10:04:00", ["D1"])]
    out = report(tmp_path, lints, [])
    assert out.startswith("unblocked: NO - A1 still waiting at the next lint (offered 10:00:00, next lint 10:01:00, "
                          "no unblocked: line names it), B1 (offered 10:01:00, next lint 10:02:00, ")
    assert "), +1 more; max lag n/a" in out


def test_takeover_hint(tmp_path, monkeypatch):
    mine, other = "aaaaaaaa-0000-4000-8000-000000000001", "bbbbbbbb-0000-4000-8000-000000000002"
    home, run = tmp_path / "home", tmp_path / "run" / ".superlite"
    (home / "sessions").mkdir(parents=True)
    run.mkdir(parents=True)
    (run / "session").write_text(other + "\n", encoding="utf-8")
    (home / "sessions" / other).write_text(str(run) + "\n", encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    monkeypatch.setenv("SUPERLITE_SESSION_ID", mine)
    led = run / "progress.md"
    led.write_text("", encoding="utf-8")
    text = finish.summary(led, tmp_path / "incidents.jsonl", str(run / "lint-log.jsonl"))
    assert (f"this run belongs to session {other}: run `sl orchestrator takeover --plan {run.resolve()}` "
            "before `sl orchestrator end`") in text
    (run / "session").unlink()
    assert "belongs to session" not in finish.summary(led, tmp_path / "incidents.jsonl", str(run / "lint-log.jsonl"))
