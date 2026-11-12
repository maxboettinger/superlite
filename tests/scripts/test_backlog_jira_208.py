import json
import subprocess
import types

import pytest

from test_backlog_cli import bk, briefed, cli, load, BATCH, bl  # noqa: F401  bk is the CLI fixture

ACLI = [{"key": "PIX-1", "fields": {"summary": "One", "description": {"type": "doc", "version": 1, "content": [
    {"type": "paragraph", "content": [{"type": "text", "text": "body one"}]}]}}},
    {"key": "PIX-2", "fields": {"summary": "Two", "description": None}}]
JB = {"id": "B1", "topic": "first", "issues": ["PIX-1", "PIX-2"], "files": ["a.py"], "depends": [], "decisions": []}


@pytest.fixture
def jk(bk, monkeypatch):
    bk.batches = [JB]
    bk.acli = []
    bk.ret = ACLI

    def acli(args):
        bk.acli.append(args)
        return bk.ret
    monkeypatch.setattr(bl, "_acli", acli)
    return bk


def write(bk, obj):
    f = bk.root / "p.json"
    f.write_text(json.dumps(obj))
    return str(f)


def no_api(bk):
    return not any(g[:1] == ["api"] for g in bk.gh)


def test_jql_plans_batches_with_keys(jk, capsys):
    rc, out = cli(capsys, "plan", "--jql", "project = PIX")
    d = load(jk)
    assert rc == 0 and "B1 | PIX-1 PIX-2 | planned" in out
    assert d["batches"][0]["issues"] == ["PIX-1", "PIX-2"] and d["titles"] == {"PIX-1": "One", "PIX-2": "Two"} and d["outside"] == []
    assert jk.acli == [["jira", "workitem", "search", "--jql", "project = PIX", "--fields", "key,summary,description", "--paginate", "--json"]]
    assert briefed(jk) == [{"number": "PIX-1", "title": "One", "body": "body one"}, {"number": "PIX-2", "title": "Two", "body": ""}]
    assert no_api(jk)


def test_issues_flag_builds_key_jql(jk, capsys):
    assert cli(capsys, "plan", "--issues", "pix-2,PIX-1")[0] == 0
    assert jk.acli[0][4] == "key in (PIX-2, PIX-1)"
    jk.ret = [ACLI[0]]
    jk.ret = []
    assert cli(capsys, "plan", "--reset", "--issues", "pix-2") == (3, "BLOCKED: Jira issue PIX-2 not found\n")


def test_bad_flags_refused_before_any_call(jk, capsys):
    assert cli(capsys, "plan", "--issues", "PIX-1,12") == (2, "BLOCKED: --issues: not a Jira key: 12\n")
    assert cli(capsys, "plan", "--jql", "  ") == (2, "BLOCKED: --jql is empty\n")
    with pytest.raises(SystemExit) as e:
        cli(capsys, "plan", "--jql", "a", "--issues", "PIX-1")
    assert e.value.code == 2
    assert jk.acli == [] and jk.gh == []


def test_unknown_key_rejected_and_named(jk, capsys):
    jk.batches = [{**JB, "issues": ["PIX-1", "PIX-9"]}]
    rc, out = cli(capsys, "plan", "--jql", "x")
    assert rc == 3 and "B1: unknown issue PIX-9" in out and "#PIX-9" not in out
    kept = jk.sd / "backlog-proposal.json"
    assert json.loads(kept.read_text())["batches"][0]["issues"] == ["PIX-1", "PIX-9"]
    jk.batches = [{**JB, "issues": [1]}]
    assert "B1: unknown issue 1" in cli(capsys, "plan", "--jql", "x")[1]
    jk.batches = [{**JB, "issues": "PIX-1"}]
    assert "list of Jira keys" in cli(capsys, "plan", "--jql", "x")[1]


def test_key_in_two_batches_named(jk, capsys):
    jk.batches = [{**JB, "issues": ["PIX-1"]}, {**JB, "id": "B2", "topic": "second", "issues": ["PIX-1"], "files": ["b.py"]}]
    rc, out = cli(capsys, "plan", "--jql", "x")
    assert rc == 3 and "PIX-1 is in B1 and B2" in out


def test_lowercase_key_in_proposal_matches(jk, capsys):
    jk.batches = [{**JB, "issues": ["pix-2"]}]
    assert cli(capsys, "plan", "--jql", "x")[0] == 0
    d = load(jk)
    assert d["batches"][0]["issues"] == ["PIX-2"]
    assert d["outside"] == [{"number": "PIX-1", "title": "One", "reason": "not planned (triage)"}]


def test_proposal_file_with_jql(jk, capsys):
    f = write(jk, {"batches": [JB]})
    rc, _ = cli(capsys, "plan", "--proposal", f, "--jql", "x")
    assert rc == 0 and jk.calls == [] and load(jk)["batches"][0]["issues"] == ["PIX-1", "PIX-2"]


def test_skip_takes_a_key(jk, capsys, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    assert cli(capsys, "plan", "--jql", "x")[0] == 0
    assert cli(capsys, "skip", "pix-2") == (0, "skipped PIX-2 (B1 keeps PIX-1)\n")
    assert "PIX-2" in load(jk)["skipped"]
    jk.batches = [{**JB, "issues": ["PIX-1"]}]
    assert cli(capsys, "plan", "--reset", "--jql", "x")[0] == 0
    assert [i["number"] for i in briefed(jk)] == ["PIX-1"]
    with pytest.raises(SystemExit) as e:
        cli(capsys, "skip", "PIX")
    assert e.value.code == 2
    assert cli(capsys, "skip", "3")[0] == 0 and 3 in load(jk)["skipped"]


def test_adf_text_shapes():
    doc = {"type": "doc", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "Hi"}, {"type": "hardBreak"}, {"type": "text", "text": "there"}]},
                                      {"type": "bulletList", "content": [{"type": "listItem", "content": [{"type": "paragraph", "content": [{"type": "text", "text": "a"}]}]}]}]}
    assert bl.adf_text(doc) == "Hi\nthere\n- a"
    assert bl.adf_text(None) == "" and bl.adf_text("plain") == "plain"
    assert bl.adf_text({"type": "mention", "attrs": {"text": "@max"}}) == "@max"
    assert bl.adf_text({"type": "inlineCard", "attrs": {"url": "http://x"}}) == "http://x"
    p = lambda t=None: {"type": "paragraph", "content": [{"type": "text", "text": t}] if t else []}
    assert bl.adf_text({"type": "doc", "content": [{"type": "heading", "content": [{"type": "text", "text": "H"}]}, p(), p(), p(), p("x")]}) == "H\n\nx"
    assert bl.adf_text({"type": "text"}) == "" and bl.adf_text([1, 2]) == ""
    assert bl.jira_keys("pix-1272, PIX-725 pix-1272") == ["PIX-1272", "PIX-725"]


def test_adf_text_deep_tree():
    node = {"type": "text", "text": "x"}
    for _ in range(5000):
        node = {"type": "blockquote", "content": [node]}
    assert isinstance(bl.adf_text(node), str)


def test_acli_errors_become_blocked(bk, capsys, monkeypatch):
    def boom(*a, **k):
        raise FileNotFoundError("acli")
    monkeypatch.setattr(bl.subprocess, "run", boom)
    rc, out = cli(capsys, "plan", "--jql", "x")
    assert rc == 3 and out.startswith("BLOCKED: acli not found: install the Atlassian CLI")

    def run(rc, so="", se=""):
        monkeypatch.setattr(bl.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=rc, stdout=so, stderr=se))
        return cli(capsys, "plan", "--jql", "x")
    msg = "failed to parse JQL query: the value 'nope' does not exist for the field 'project'."
    assert run(1, se="✗ Error: " + msg + "\n") == (3, "BLOCKED: acli jira workitem search failed: Error: " + msg + "\n")
    assert run(0, so="not json") == (3, "BLOCKED: acli jira workitem search gave no JSON\n")
    assert run(0, so="{}") == (3, "BLOCKED: acli search gave no issue list\n")


def test_cap_lists_rest_as_not_triaged(jk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "ISSUE_LIMIT", 1)
    jk.batches = [{**JB, "issues": ["PIX-1"]}]
    assert cli(capsys, "plan", "--jql", "x")[0] == 0
    assert {"number": "PIX-2", "title": "Two", "reason": "not triaged (1 cap)"} in load(jk)["outside"]


def test_github_path_unchanged(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "_acli", lambda a: pytest.fail("acli called"))
    bk.batches = [BATCH]
    rc, out = cli(capsys, "plan")
    assert rc == 0 and "B1 | #1 #2 | planned" in out
    assert load(bk)["outside"] == [{"number": 3, "title": "Three", "author": "eve"}]


def test_hash_digits_in_other_errors_not_rewritten(jk, capsys):
    jk.batches = [{**JB, "files": ["/#1"]}]
    rc, out = cli(capsys, "plan", "--jql", "x")
    assert rc == 3 and "file '/#1' is not a plain" in out and "PIX-1" not in out.split("proposal kept")[0]


def test_acli_undecodable_output_becomes_blocked(bk, capsys, monkeypatch):
    def run(*a, **k):
        raise UnicodeDecodeError("utf-8", b"\xff", 0, 1, "invalid start byte")
    monkeypatch.setattr(bl.subprocess, "run", run)
    rc, out = cli(capsys, "plan", "--jql", "x")
    assert rc == 3 and out.startswith("BLOCKED: acli jira workitem search failed:")


def test_key_with_trailing_newline_refused(jk, capsys):
    with pytest.raises(SystemExit) as e:
        bl.main(["skip", "PIX-1\n"])
    assert e.value.code == 2
    assert bl.jira_issues(None, ["PIX-1"]) and bl.jira_keys("pix-1\n pix-2") == ["PIX-1", "PIX-2"]


def test_non_string_summary_becomes_text(jk):
    jk.ret = [{"key": "PIX-3", "fields": {"summary": 5, "description": None}}]
    assert bl.jira_issues("x", None)[0]["title"] == "5"
