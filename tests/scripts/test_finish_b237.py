"""B237: finish counts the plan's rulings, treats the prime dispatch as the send, and archives the plan files."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402
import run_archive  # noqa: E402


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(finish, "drop_trees", lambda sd: None)
    monkeypatch.setattr(finish, "log_auto", lambda *a, **k: 0)
    monkeypatch.setattr(finish, "ci_line", lambda sd: None)


def run_dir(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    return sd


def test_fenced_ruling_ignored(tmp_path):
    p = tmp_path / "p.md"
    p.write_text("Ruling: a\n```\nRuling: in code\n```\n- Ruling: [scope] b\n~~~\nRuling: tilde\n~~~\n", encoding="utf-8")
    assert finish.plan_rulings(str(p)) == ["a", "[scope] b"]
    assert finish.plan_rulings("") == []
    assert finish.plan_rulings(str(tmp_path / "missing.md")) == []


def test_plan_rulings_counted(tmp_path):
    sd = run_dir(tmp_path)
    (sd / "progress.md").write_text("- Ruling: x\n", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text("Ruling: a\nRuling: x\n", encoding="utf-8")
    out = finish.summary(str(sd / "progress.md"), str(sd / "i.jsonl"), plan=str(plan))
    assert "rulings: 2" in out
    lines = out.splitlines()
    assert lines.index("- x") < lines.index("- a")


def test_plan_scope_ruling_listed(tmp_path):
    sd = run_dir(tmp_path)
    (sd / "progress.md").write_text("", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text("Ruling: [scope] drop y\n", encoding="utf-8")
    out = finish.summary(str(sd / "progress.md"), str(sd / "i.jsonl"), plan=str(plan))
    assert "scope rulings: 1" in out and "- drop y" in out


def test_no_plan_keeps_spec_path(tmp_path):
    sd = run_dir(tmp_path)
    (sd / "progress.md").write_text("", encoding="utf-8")
    (sd / "spec.md").write_text("Ruling: from spec\n", encoding="utf-8")
    out = finish.summary(str(sd / "progress.md"), str(sd / "i.jsonl"), plan="")
    assert "rulings: 1" in out and "- from spec" in out


def lint_setup(tmp_path, dispatch=None):
    sd = run_dir(tmp_path)
    (sd / "lint-log.jsonl").write_text(
        json.dumps({"time": "2026-11-12T11:01:07", "pending": ["T1"]}) + "\n"
        + json.dumps({"time": "2026-11-12T11:02:00", "pending": ["T1"]}) + "\n", encoding="utf-8")
    (sd / "progress.md").write_text("- unblocked: dispatched T1 at 11:03:15\n", encoding="utf-8")
    if dispatch is not None:
        (sd / "dispatch-log.jsonl").write_text(dispatch, encoding="utf-8")
    return sd


def unblocked(sd):
    return finish.unblocked_report(str(sd / "progress.md"), str(sd / "lint-log.jsonl"))


def test_prime_dispatch_counts_as_send(tmp_path):
    sd = lint_setup(tmp_path, json.dumps({"time": "2026-11-12T11:01:20", "fresh": ["T1"]}) + "\n")
    line = unblocked(sd)
    assert not line.startswith("unblocked: NO") and "max lag 13s" in line


def test_without_dispatch_log_unchanged(tmp_path):
    sd = lint_setup(tmp_path)
    assert unblocked(sd) == ("unblocked: NO - T1 still waiting at the next lint (offered 11:01:07, next lint 11:02:00, "
                             "sent 11:03:15); max lag 128s")


def test_bad_dispatch_log_lines_skipped(tmp_path):
    sd = lint_setup(tmp_path, "not json\n" + json.dumps({"time": "2026-11-12T11:01:20"}) + "\n")
    assert unblocked(sd).startswith("unblocked: NO - T1 still waiting")


def archive_summary(tmp_path, monkeypatch, result):
    sd = run_dir(tmp_path)
    (sd / "progress.md").write_text("", encoding="utf-8")
    (sd / "metrics.jsonl").write_text("", encoding="utf-8")
    plan = tmp_path / "plan.md"
    plan.write_text("p\n", encoding="utf-8")
    monkeypatch.setattr(run_archive, "keep_in_plans", lambda *a, **k: result)
    monkeypatch.setattr(finish, "history_section", lambda *a, **k: "history: x")
    monkeypatch.chdir(tmp_path)
    return finish.summary(str(sd / "progress.md"), str(sd / "i.jsonl"), plan=str(plan), archive=True)


def test_archived_line_printed(tmp_path, monkeypatch):
    out = archive_summary(tmp_path, monkeypatch, ["docs/plans/a.md", "docs/plans/a.progress.md"])
    assert ("archived: docs/plans/a.md, docs/plans/a.progress.md "
            "(commit them with the branch: they outlive the worktree)") in out


def test_nothing_archived_no_line(tmp_path, monkeypatch):
    assert "archived:" not in archive_summary(tmp_path, monkeypatch, [])
