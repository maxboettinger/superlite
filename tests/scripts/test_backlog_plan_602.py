# tests/scripts/test_backlog_plan_602.py
import sys
import pytest
import test_backlog_cli as tc
from test_backlog_cli import bk, cli, BATCH, bs, bl  # noqa: F401
import backlog_intake
import backlog_ship


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(bl, "_tracked", lambda root: [])
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: [])


def test_overlap_line_for_append_only_shared_file():
    new = [{"id": "B3", "files": ["a.md", "x.py"], "append_only": ["a.md"]}]
    old = [{"id": "B1", "state": "running", "files": ["a.md"], "append_only": ["a.md"]}]
    assert bl.overlap_lines(new, old) == ["overlap: B3 shares a.md with B1 (running): append-only in both, no hold; conflicts resolve at the ship rebase"]


def test_overlap_line_names_only_serialising_files():
    new = [{"id": "B3", "files": ["a.md", "b.py"], "append_only": ["a.md"]}]
    old = [{"id": "B1", "state": "planned", "files": ["a.md", "b.py"], "append_only": ["a.md"]}]
    assert bl.overlap_lines(new, old) == ["overlap: B3 shares b.py with B1 (planned): whichever starts first holds the files"]


def test_open_batches_carries_append_only():
    data = {"batches": [{"id": "B2", "state": "planned", "files": ["a.md"], "append_only": ["a.md"]},
                        {"id": "B1", "state": "running", "files": ["b.py"]},
                        {"id": "B0", "state": "shipped", "files": ["c.py"]}]}
    assert bl.open_batches(data) == [{"id": "B1", "state": "running", "files": ["b.py"]},
                                     {"id": "B2", "state": "planned", "files": ["a.md"], "append_only": ["a.md"]}]


def test_notes_routes_to_ship_notes(monkeypatch):
    seen = []
    monkeypatch.setattr(backlog_ship, "main", lambda argv: seen.append(list(argv)) or 0)
    assert bl.main(["notes", "B4"]) == 0
    assert bl.main(["notes", "B4", "--plan", ".superlite"]) == 0
    assert seen == [["B4", "notes"], ["B4", "notes", "--plan", ".superlite"]]


def test_notes_without_batch_is_refused(monkeypatch, capsys):
    seen = []
    monkeypatch.setattr(backlog_ship, "main", lambda argv: seen.append(list(argv)) or 0)
    for argv in (["notes"], ["notes", "--plan", "x"]):
        assert bl.main(argv) == 2
        assert capsys.readouterr().out == "BLOCKED: usage: sl backlog notes B\n"
    assert seen == []


def test_help_lists_notes(capsys):
    with pytest.raises(SystemExit) as e:
        bl.main(["--help"])
    assert e.value.code == 0 and "notes" in capsys.readouterr().out


def test_plan_reads_comments_and_plans_a_reopened_shipped_issue(bk, capsys, monkeypatch):
    bs.update(bs.path(bk.root), lambda d: d["batches"].append({**BATCH, "id": "B1", "issues": [7], "state": "shipped", "pr": 70}))
    bk.batches = [{**BATCH, "id": "B2", "issues": [7]}]
    issues = [{"number": 7, "title": "Seven", "author": {"login": "max"}, "authorAssociation": "OWNER", "body": "b7"}]
    gql = {"data": {"repository": {"i7": {"stateReason": "REOPENED", "comments": {"nodes": [
        {"authorAssociation": "OWNER", "author": {"login": "max"}, "body": "still broken"}]}}}}}

    def gh(args):
        if args[:2] == ["repo", "view"]:
            return {"nameWithOwner": "o/r", "visibility": "PUBLIC"}
        return gql if args[:2] == ["api", "graphql"] else issues
    monkeypatch.setattr(bl, "_gh", gh)
    rc, out = cli(capsys, "plan")
    brief = (bk.sd / "briefs" / "triage.md").read_text()
    assert rc == 0 and "reopened: #7 was shipped in B1" in out
    assert "## #7 Seven (reopened)" in brief and "still broken" in brief


def test_gh_chunk_treats_a_non_dict_answer_as_no_comments(monkeypatch):
    monkeypatch.setattr(bl, "_gh", lambda args: [])
    assert backlog_intake._gh_chunk("o", "r", [1, 2], True) == {1: ([], False), 2: ([], False)}


def test_jira_comment_answer_not_a_dict_gives_no_comments(monkeypatch):
    monkeypatch.setattr(bl, "_acli", lambda args: [])
    item = {"number": "PIX-1", "title": "t", "body": ""}
    assert backlog_intake.with_comments([item], "o/r", False, jira=True) == ([{**item, "comments": []}], [])
