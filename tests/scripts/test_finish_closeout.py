"""#140: `finish` names the superlite-side stops of the run (guard blocks, no-result test runs, commit scope blocks),
logs each as an `auto` feedback entry and asks for friction; #178: `finish --plan P` reads P's run folder."""
from __future__ import annotations

import json
import os
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import feedback  # noqa: E402
import finish  # noqa: E402
import state  # noqa: E402

FRICTION = "superlite friction this run"
SID = "finish-closeout-1"


@pytest.fixture
def auto_calls(monkeypatch):
    """Swappable fake of feedback.add_auto (T1): records the calls by default; the real one (into the isolated
    SUPERLITE_HOME) when SUPERLITE_REAL=1."""
    calls: list[tuple] = []
    if os.environ.get("SUPERLITE_REAL") == "1":
        real = feedback.add_auto

        def spy(*a):
            calls.append(a)
            return real(*a)

        monkeypatch.setattr(feedback, "add_auto", spy)
    else:
        monkeypatch.setattr(feedback, "add_auto", lambda *a: calls.append(a) or True)
    return calls


def hook(kind, tool, target, agent="coordinator"):
    return {"kind": kind, "agent": agent, "tool": tool, "target": target}


def no_result(reason="pytest produced no results"):
    return {"file": "-", "line": 0, "context": reason, "agent": "run_tests", "kind": "no-result", "resolution": "open"}


def run_folder(root, incidents, commit="T1 abc1234567 slug"):
    """<root>/.superlite with a run marker, a ledger and an incident log; <root>/docs/plans/plan.md -> the plan path."""
    sl = root / ".superlite"
    sl.mkdir(parents=True)
    (sl / "pool.json").write_text(json.dumps({"agents": []}), encoding="utf-8")
    (sl / "progress.md").write_text(f"- commit {commit}\n", encoding="utf-8")
    (sl / "incidents.jsonl").write_text("".join(json.dumps(e) + "\n" for e in incidents), encoding="utf-8")
    plan = root / "docs" / "plans" / "plan.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# plan\n", encoding="utf-8")
    return plan


def finish_out(capsys, *args):
    assert finish.main(list(args)) == 0
    return capsys.readouterr().out


def test_finish_reports_stops_and_logs_auto(tmp_path, capsys, auto_calls):
    plan = run_folder(tmp_path, [hook("rule-block", "block-coordinator-edits", "src/a.py"),
                                 hook("rule-block", "block-coordinator-edits", "src/b.py"), no_result()])
    out = finish_out(capsys, "--plan", str(plan))
    line = "superlite stops this run: 2 rule-block (block-coordinator-edits), 1 no-result (run_tests)"
    assert line in out.splitlines()
    assert out.index(line) < out.index(FRICTION)  # the friction prompt closes the section
    assert len(auto_calls) == 3
    tools = sorted((tool, reason) for tool, reason, _target, _ver in auto_calls)
    assert tools == [("block-coordinator-edits", "rule-block")] * 2 + [("run_tests", "no-result")]
    assert {t for _tool, _reason, t, _ver in auto_calls} >= {"src/a.py", "src/b.py"}
    assert all(ver == feedback.version() for *_rest, ver in auto_calls)


def test_no_stops_no_line(tmp_path, capsys, auto_calls):
    plan = run_folder(tmp_path, [{"file": "a.py", "line": 1, "context": "boom", "kind": "exception", "resolution": "open"},
                                 {"kind": "verified", "file": "t.py", "line": 0, "context": "ok"}])
    out = finish_out(capsys, "--plan", str(plan))
    assert "superlite stops" not in out and FRICTION in out
    assert auto_calls == []


def test_commit_scope_blocks_count_and_resolved_ones_do_not(tmp_path, capsys, auto_calls):
    scope = {"file": "src/x.py", "line": 0, "context": "T1: change outside Owns blocked by commit_task; nothing committed",
             "kind": "exception", "agent": "commit_task", "resolution": "open"}
    plan = run_folder(tmp_path, [scope, {**scope, "context": "T1: src/x.py committed with T1; earlier block resolved", "resolution": "resolved"},
                                 {**scope, "file": "src/y.py", "kind": "workaround", "resolution": "accepted",
                                  "context": "T1: shared test adjusted"},
                                 {"file": "a.py", "line": 1, "context": "boom", "kind": "exception", "agent": "implementer", "resolution": "open"}])
    out = finish_out(capsys, "--plan", str(plan))
    assert "superlite stops this run: 1 exception (commit_task)" in out.splitlines()
    assert [(c[0], c[1], c[2]) for c in auto_calls] == [("commit_task", "exception", "src/x.py")]


def test_all_stop_kinds_are_counted(tmp_path, capsys, auto_calls):
    plan = run_folder(tmp_path, [hook("rule-rewrite", "rewrite-test-runs", "pytest -x"), hook("guard-error", "Bash", "ValueError: x"),
                                 hook("rule-block", "lint --stable", "shared checkout"), hook("rule-block", "lint --stable", "human gate")])
    out = finish_out(capsys, "--plan", str(plan))
    assert ("superlite stops this run: 2 rule-block (lint --stable), 1 rule-rewrite (rewrite-test-runs), "
            "1 guard-error (Bash)") in out.splitlines()
    assert len(auto_calls) == 4


def test_feedback_failure_never_fails_finish(tmp_path, capsys, monkeypatch):
    def boom(*a):
        raise OSError("disk full")

    monkeypatch.setattr(feedback, "add_auto", boom)
    plan = run_folder(tmp_path, [hook("rule-block", "block-coordinator-edits", "src/a.py")])
    out = finish_out(capsys, "--plan", str(plan))
    assert "superlite stops this run: 1 rule-block (block-coordinator-edits)" in out and FRICTION in out
    monkeypatch.setattr(feedback, "add_auto", lambda *a: False)  # the inbox cannot be written
    assert "superlite stops this run: 1 rule-block" in finish_out(capsys, "--plan", str(plan))


def test_finish_defaults_follow_plan(tmp_path, capsys, monkeypatch, auto_calls):
    """The session is bound to run A; `finish --plan B` reads B's ledger and log, not A's (#178)."""
    run_a, run_b = tmp_path / "wa", tmp_path / "wb"
    run_folder(run_a, [hook("rule-block", "block-coordinator-edits", "a-only.py")], commit="T1 aaaaaaaaaa from-a")
    plan_b = run_folder(run_b, [no_result()], commit="T2 bbbbbbbbbb from-b")
    for w in (run_a, run_b):
        (w / ".git").write_text("gitdir: x\n", encoding="utf-8")  # linked worktrees
    launch = tmp_path / "launch"
    launch.mkdir()
    monkeypatch.chdir(launch)
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", SID)
    state.bind(run_a / ".superlite")
    own = finish_out(capsys)  # no --plan: the binding's run
    assert "from-a" in own and "from-b" not in own and "1 rule-block (block-coordinator-edits)" in own
    auto_calls.clear()
    out = finish_out(capsys, "--plan", str(plan_b))
    assert "from-b" in out and "from-a" not in out
    assert "superlite stops this run: 1 no-result (run_tests)" in out.splitlines()
    assert [c[0] for c in auto_calls] == ["run_tests"]
    explicit = finish_out(capsys, "--plan", str(plan_b), "--ledger", str(run_a / ".superlite" / "progress.md"))
    assert "from-a" in explicit  # an explicit --ledger still wins
