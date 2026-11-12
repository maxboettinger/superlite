# tests/scripts/test_backlog_brief_jira_208.py
import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

CTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md",
       "titles": {"PIX-1272": "Fix login", "PIX-725": "Cache"}, "summaries": [],
       "approved": {"by": "AskUserQuestion", "time": "t"}}
JB = {"id": "B2", "topic": "jira-fix", "issues": ["PIX-1272", "PIX-725"], "files": ["a.py"], "answers": {}}

GH_LEAD = ('# Lead brief: B1 (t)\nYou are the lead of batch B1 in o/r. Read /x/backlog.md first: it holds the lead rules.\n'
           + bb.DATA_RULE + '\n'
           + "Issues (you have a shell: read each body and its latest 3 comments yourself with `gh issue view <n> --json title,body,stateReason,comments --jq '{title, body, stateReason, comments: [.comments[-3:][] | {author: .author.login, authorAssociation, body}]}'`):\n- #7 Seven\n"
           + 'Files this batch may touch: a.py. Another lead may own any other file.\n'
           + bb.ROOT_DOC_RULE + "\n"
           "Max's decisions: none\n" + bb.ATTRIBUTION + "\nRulings from shipped batches: none\n"
           'Your run: the worktree you start in, state in .superlite/; pass --plan .superlite to every sl call.\n'
           'First: `/x/sl orchestrator set ai --plan .superlite`, then `/x/sl fleet on --plan .superlite`.\n'
           'Build: superlite:brainstorming (AI orchestrator, no questions), superlite:writing-plans, superlite:subagent-driven-development with fleet on, the final review (UI screenshots go in .superlite/render/, its packet lists them), the test layers. Build inside your worktree: never pass -derivedDataPath outside it (your session scratchpad included); sl run_tests builds each task tree in <tree>/.build/DerivedData and backlog cleanup removes scratchpad build folders when the worktree goes.\n'
           'Never end your turn while your workers run: wait with `/x/sl fleet wait --timeout 540000 --plan .superlite` in the foreground, never as a background command: under memory pressure Claude Code stops an idle session\'s background commands, and a restarted wait still reports every worker that finished meanwhile.\n'
           'Escalate a new major decision: let running workers finish, write .superlite/question.json in the AskUserQuestion shape, end your turn with Status: NEEDS_DECISION.\n'
           'Ship: allowed (approved by Max in AskUserQuestion at t). Ship only with `/x/sl backlog ship B1 lock`, then bump, then merge (backlog.md). Run each ship step as one bare command that starts with `/x/sl backlog ship` or `maxapp ship`: no `cd` (you start in your worktree), no pipe, no `echo`, no `&&` chain; the allow rules match nothing else. ' + bb.NOTES_RULE + 'one `Closes #N` line per issue ("Fixes #1, #2" closes only #1); merge adds a missing one and prints `OPEN #N` for an issue still open after the merge.\n'
           'End: Status: DONE once merge printed shipped; otherwise Status: BLOCKED with the reason. Then the JSON block.\n')


def test_lead_brief_lists_keys_and_acli():
    t = bb.lead_brief(JB, CTX)
    for s in ["- PIX-1272 Fix login", "- PIX-725 Cache", "acli jira workitem view <KEY> --fields summary,description --json",
              "getJiraIssue", "**Ticket:** PIX-1272", "merge --title", "naming each Jira key", "OPEN #<KEY>"]:
        assert s in t
    for s in ["#PIX", "gh issue view", "one `Closes #N` line per issue"]:
        assert s not in t


def test_lead_brief_jira_not_approved():
    t = bb.lead_brief(JB, {**CTX, "approved": None})
    assert "Ship: NOT approved. Do not rebase, bump or ship;" in t
    assert "**Ticket:** PIX-1272" in t


def test_github_lead_brief_unchanged():
    b = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"]}
    t = bb.lead_brief(b, {**CTX, "titles": {"7": "Seven"}})
    assert t == GH_LEAD
    assert "Jira" not in t


def test_triage_brief_jira_headings():
    t = bb.triage_brief([{"number": "PIX-1272", "title": "Fix\x07 login", "body": "line\n\x1bnext"}],
                        {"repo": "o/r", "max_batches": 3})
    for s in ["## PIX-1272 Fix login", "    line", "    next", "open Jira issues", '"issues": ["PIX-1272"]', '"issues": ["<KEY>"]']:
        assert s in t
    assert "#PIX" not in t


def test_triage_brief_github_unchanged():
    t = bb.triage_brief([{"number": 3, "title": "T", "body": "b"}], {"repo": "o/r", "max_batches": 3})
    assert "## #3 T" in t and '"issues": [<n>]' in t
    assert "Jira" not in t


def test_ref_and_summary():
    assert bb.ref("PIX-1272") == "PIX-1272"
    assert bb.ref(208) == "#208"
    assert bb.ref("PIX-1\x07") == "PIX-1"
    assert bb.summary({"id": "B38", "issues": ["PIX-1272", "PIX-725"], "pr": 9, "version": "1.5.47"}, "") == \
        "B38 shipped: PIX-1272 PIX-725\nPR: #9\nVersion: 1.5.47\n"
    assert bb.summary({"id": "B1", "issues": [1, 2]}, "").splitlines()[0] == "B1 shipped: #1 #2"


def test_ticket_line_names_first_key_when_mixed():
    out = bb.lead_brief({**JB, "issues": [7, "PIX-9"]}, CTX)
    assert "**Ticket:** PIX-9" in out
