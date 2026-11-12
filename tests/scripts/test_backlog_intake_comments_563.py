import copy
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog  # noqa: E402
import backlog_intake as bi  # noqa: E402


def node(assoc, body, login="max", state=None):
    return {"authorAssociation": assoc, "author": {"login": login} if login else None, "body": body}


def gql(per_issue):
    """per_issue: {n: (stateReason, [nodes])} -> graphql response."""
    repo = {f"i{n}": {"stateReason": s, "comments": {"nodes": ns}} for n, (s, ns) in per_issue.items()}
    return {"data": {"repository": repo}}


def fake_gh(monkeypatch, fn):
    calls = []

    def _gh(args):
        calls.append(args)
        return fn(args)
    monkeypatch.setattr(backlog, "_gh", _gh)
    return calls


def test_with_comments_examples(monkeypatch):
    fake_gh(monkeypatch, lambda a: gql({5: ("REOPENED", [node("OWNER", "Regressed in 1.5.104"), node("NONE", "me too", "x")])}))
    got = bi.with_comments([{"number": 5, "title": "A", "body": "b"}], "o/r", True)
    assert got == ([{"number": 5, "title": "A", "body": "b", "comments": [{"author": "max", "body": "Regressed in 1.5.104"}], "reopened": True}], [])

    def boom(a):
        raise RuntimeError("gh api failed: boom")
    fake_gh(monkeypatch, boom)
    got = bi.with_comments([{"number": 6, "title": "B", "body": ""}], "o/r", True)
    assert got == ([{"number": 6, "title": "B", "body": "", "comments": []}],
                   ["comments: not read (gh api failed: boom); triage sees the issue bodies only"])

    monkeypatch.setattr(backlog, "_acli", lambda a: {"comments": [{"author": "Ann", "body": "newest"}, {"author": "Bo", "body": "older"}]})
    got = bi.with_comments([{"number": "PIX-1", "title": "C", "body": ""}], "", False, True)
    assert got == ([{"number": "PIX-1", "title": "C", "body": "",
                     "comments": [{"author": "Bo", "body": "older"}, {"author": "Ann", "body": "newest"}]}], [])


def test_public_repo_drops_outside_comments(monkeypatch):
    resp = gql({5: (None, [node("OWNER", "a"), node("NONE", "b", "x")])})
    fake_gh(monkeypatch, lambda a: resp)
    pub, _ = bi.with_comments([{"number": 5}], "o/r", True)
    priv, _ = bi.with_comments([{"number": 5}], "o/r", False)
    assert [c["body"] for c in pub[0]["comments"]] == ["a"]
    assert [c["body"] for c in priv[0]["comments"]] == ["a", "b"]
    assert "reopened" not in pub[0]


def test_repo_name_with_quote_is_not_queried(monkeypatch):
    calls = fake_gh(monkeypatch, lambda a: gql({}))
    items, lines = bi.with_comments([{"number": 1}], 'o/r" x', True)
    assert calls == []
    assert lines == ['comments: not read (bad repo name o/r" x); triage sees the issue bodies only']
    assert items == [{"number": 1, "comments": []}]


def test_chunks_of_50(monkeypatch):
    calls = fake_gh(monkeypatch, lambda a: gql({}))
    items, lines = bi.with_comments([{"number": n} for n in range(1, 121)], "o/r", True)
    assert len(calls) == 3 and lines == [] and len(items) == 120
    assert all(i["comments"] == [] for i in items)


def test_keeps_latest_three_oldest_first(monkeypatch):
    fake_gh(monkeypatch, lambda a: gql({5: (None, [node("OWNER", f"c{i}") for i in range(1, 6)])}))
    got, _ = bi.with_comments([{"number": 5}], "o/r", True)
    assert [c["body"] for c in got[0]["comments"]] == ["c3", "c4", "c5"]


def test_null_author_is_ghost(monkeypatch):
    fake_gh(monkeypatch, lambda a: gql({5: (None, [node("OWNER", "x", None)])}))
    got, _ = bi.with_comments([{"number": 5}], "o/r", True)
    assert got[0]["comments"] == [{"author": "ghost", "body": "x"}]


def test_long_comment_is_cut(monkeypatch):
    fake_gh(monkeypatch, lambda a: gql({5: (None, [node("OWNER", "x" * 2500)])}))
    got, _ = bi.with_comments([{"number": 5}], "o/r", True)
    assert got[0]["comments"][0]["body"] == "x" * 2000 + "\n[truncated]"


def test_input_not_mutated(monkeypatch):
    fake_gh(monkeypatch, lambda a: gql({5: ("REOPENED", [node("OWNER", "x")])}))
    src = [{"number": 5, "title": "A"}]
    before = copy.deepcopy(src)
    bi.with_comments(src, "o/r", True)
    assert src == before


def test_empty_list_makes_no_call(monkeypatch):
    calls = fake_gh(monkeypatch, lambda a: gql({}))
    assert bi.with_comments([], "o/r", True) == ([], [])
    assert calls == []


def test_jira_failure_line(monkeypatch):
    def boom(a):
        raise RuntimeError("acli failed")
    monkeypatch.setattr(backlog, "_acli", boom)
    got, lines = bi.with_comments([{"number": "PIX-1"}], "", False, True)
    assert got[0]["comments"] == []
    assert lines == ["comments: not read for PIX-1 (acli failed)"]


def test_reopened_merged_issue_is_planned_again():
    kept, dropped, lines = bi.split_shipped([{"number": 6, "reopened": True}], [], {6: "PR #20"}, [])
    assert [i["number"] for i in kept] == [6] and dropped == []
    assert lines == ["reopened: #6 named by merged PR #20: planned again"]


def test_reopened_shipped_issue_is_planned_again():
    b = [{"id": "B7", "state": "shipped", "issues": [5], "pr": 608}]
    kept, dropped, lines = bi.split_shipped([{"number": 5, "reopened": True}], b, {}, [])
    assert [i["number"] for i in kept] == [5] and dropped == []
    assert lines == ["reopened: #5 was shipped in B7 (PR #608): planned again"]
    b = [{"id": "B7", "state": "shipped", "issues": [5]}]
    _, _, lines = bi.split_shipped([{"number": 5, "reopened": True}], b, {}, [])
    assert lines == ["reopened: #5 was shipped in B7: planned again"]


def test_reopened_unnamed_issue_is_kept_silently():
    kept, _, lines = bi.split_shipped([{"number": 9, "reopened": True}], [], {}, [])
    assert len(kept) == 1 and lines == []
