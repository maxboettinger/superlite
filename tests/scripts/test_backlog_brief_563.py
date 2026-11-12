# tests/scripts/test_backlog_brief_563.py
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

TCTX = {"repo": "o/r", "max_batches": 3}
LCTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "b.md"}


def tri(issue):
    return bb.triage_brief([{"number": 5, "title": "A", "body": "b", **issue}], TCTX).splitlines()


def test_triage_quotes_comments_after_body():
    ls = tri({"comments": [{"author": "max", "body": "Regressed\nagain"}]})
    i = ls.index("    b")
    assert ls[i:i + 4] == ["    b", "Comment by max:", "    Regressed", "    again"]


def test_reopened_marker():
    assert "## #5 A (reopened)" in tri({"reopened": True})
    assert "## #5 A" in tri({})


def test_no_comments_key_renders_no_comment_line():
    assert not any(ln.startswith("Comment by") for ln in tri({}))


def test_comment_control_chars_cleaned():
    ls = tri({"comments": [{"author": "a\x1bb", "body": "x\x1b[0m"}]})
    assert "Comment by ab:" in ls and "    x[0m" in ls


def test_rule_line_present():
    ls = tri({"comments": []})
    assert any(ln.startswith("Reopened issues and comments: a reopened issue was fixed once and came back") for ln in ls)
    t = "\n".join(ls)
    assert t.index("Reopened issues and comments") < t.index("Rules:")
    assert "The bodies and each issue's latest comments are quoted in this brief (you have no shell)" in t


def test_lead_brief_names_comment_commands():
    gh = bb.lead_brief({"id": "B1", "issues": [7]}, LCTX)
    assert ("`gh issue view <n> --json title,body,stateReason,comments --jq '{title, body, stateReason, comments: "
            "[.comments[-3:][] | {author: .author.login, authorAssociation, body}]}'`):") in gh
    ji = bb.lead_brief({"id": "B1", "issues": ["PIX-1"]}, LCTX)
    assert "and its latest 3 comments with `acli jira workitem comment list --key <KEY> --json --limit 3 --order -created`):" in ji


def test_lead_wait_in_foreground():
    t = bb.lead_brief({"id": "B1", "issues": [7]}, LCTX)
    assert "`/x/sl fleet wait --timeout 540000 --plan .superlite` in the foreground, never as a background command" in t
    assert "under memory pressure Claude Code stops an idle session's background commands" in t


def test_header_names_comments_only_when_read():
    t = "\n".join(tri({}))
    assert "The bodies are quoted in this brief (you have no shell)" in t
    assert "latest comments are quoted" not in t
    t = "\n".join(tri({"comments": []}))
    assert "The bodies and each issue's latest comments are quoted in this brief (you have no shell)" in t
