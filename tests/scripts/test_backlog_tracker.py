# tests/scripts/test_backlog_tracker.py
import json
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog  # noqa: E402
import backlog_tracker as bt  # noqa: E402


def fake_gh(monkeypatch, reply, calls):
    def run(cmd, **kw):
        calls.append(cmd)
        r = reply(cmd) if callable(reply) else reply
        if isinstance(r, Exception):
            raise r
        return r
    monkeypatch.setattr(bt.subprocess, "run", run)


def done(payload, rc=0):
    return SimpleNamespace(returncode=rc, stdout=json.dumps(payload), stderr="")


def gql(states):
    return {"data": {"repository": {f"i{n}": ({"state": s} if s else None) for n, s in states.items()}}}


def test_open_now_mixed(monkeypatch):
    calls = []
    fake_gh(monkeypatch, done(gql({5: "OPEN", 6: "CLOSED"})), calls)
    acli = []
    monkeypatch.setattr(backlog, "_acli", lambda a: acli.append(a) or [{"key": "PIX-1"}])
    assert bt.open_now("o/r", [5, 6, "PIX-1", "PIX-2"], Path(".")) == [5, "PIX-2"]
    assert len(calls) == 1 and len(acli) == 1


def test_gh_failure_keeps_all(monkeypatch):
    fake_gh(monkeypatch, OSError("no gh"), [])
    assert bt.open_now("o/r", [5, 6], Path(".")) == [5, 6]
    fake_gh(monkeypatch, SimpleNamespace(returncode=0, stdout="nope", stderr=""), [])
    assert bt.open_now("o/r", [5, 6], Path(".")) == [5, 6]


def test_one_graphql_call_for_many_numbers(monkeypatch):
    calls = []
    fake_gh(monkeypatch, done(gql({})), calls)
    bt.open_now("o/r", list(range(1, 151)), Path("."))
    assert [c[-1].count("issue(number:") for c in calls] == [100, 50]
    calls.clear()
    bt.open_now("o/r", [1, 2, 3], Path("."))
    assert len(calls) == 1


def test_one_jira_search_for_many_keys(monkeypatch):
    acli = []
    monkeypatch.setattr(backlog, "_acli", lambda a: acli.append(a) or [{"key": "PIX-2"}])
    assert bt.open_now("o/r", ["PIX-1", "PIX-2", "PIX-3"], Path(".")) == ["PIX-1", "PIX-3"]
    assert len(acli) == 1 and all(k in " ".join(acli[0]) for k in ("PIX-1", "PIX-2", "PIX-3"))
    monkeypatch.setattr(backlog, "_acli", lambda a: (_ for _ in ()).throw(RuntimeError("x")))
    assert bt.open_now("o/r", ["PIX-1"], Path(".")) == ["PIX-1"]


def test_bad_repo_or_key_is_kept_unread(monkeypatch):
    calls, acli = [], []
    fake_gh(monkeypatch, done(gql({})), calls)
    monkeypatch.setattr(backlog, "_acli", lambda a: acli.append(a) or [])
    assert bt.open_now("o/r; x", [5], Path(".")) == [5]
    assert bt.open_now("o/r", ["pix 1"], Path(".")) == ["pix 1"]
    assert calls == [] and acli == []


def test_null_alias_keeps_issue_open(monkeypatch):
    out = SimpleNamespace(returncode=1, stdout=json.dumps(gql({5: None, 6: "MERGED", 7: "CLOSED"})), stderr="err")
    fake_gh(monkeypatch, out, [])
    assert bt.open_now("o/r", [5, 6, 7], Path(".")) == [5]


def test_bool_is_not_a_number(monkeypatch):
    calls = []
    fake_gh(monkeypatch, done(gql({})), calls)
    assert bt.open_now("o/r", [True], Path(".")) == [True]
    assert calls == []


def test_jira_by_key(monkeypatch):
    monkeypatch.setattr(backlog, "_acli", lambda a: {"key": "PIX-2", "fields": {"summary": "Two", "description": None}})
    assert bt.jira_by_key(["PIX-2"]) == ([{"number": "PIX-2", "title": "Two", "body": ""}], [])
    monkeypatch.setattr(backlog, "_acli", lambda a: (_ for _ in ()).throw(RuntimeError("x")))
    assert bt.jira_by_key(["PIX-2"]) == ([], ["PIX-2"])
    monkeypatch.setattr(backlog, "_acli", lambda a: [{"key": "PIX-9"}, {"key": "PIX-3", "fields": {"summary": "T"}}])
    assert bt.jira_by_key(["PIX-3", "PIX-4"]) == ([{"number": "PIX-3", "title": "T", "body": ""}], ["PIX-4"])


def test_view_body_is_flattened_and_capped(monkeypatch):
    adf = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "x" * (backlog.BODY_LIMIT + 50)}]}]}
    monkeypatch.setattr(backlog, "_acli", lambda a: {"key": "PIX-2", "fields": {"summary": "S", "description": adf}})
    found, _ = bt.jira_by_key(["PIX-2"])
    assert found[0]["body"] == backlog._body(backlog.adf_text(adf)) and found[0]["body"].endswith("[truncated]")
