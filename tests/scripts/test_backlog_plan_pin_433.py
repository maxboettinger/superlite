"""sl backlog plan --issues takes GitHub numbers, and issues an earlier cap left out are ranked first (#433)."""
import re

import pytest

from test_backlog_cli import ISSUES, bk, briefed, cli, load, BATCH, bl, bs  # noqa: F401  bk is the CLI fixture
import backlog_brief as bb  # noqa: E402
from test_backlog_jira_208 import jk  # noqa: F401  jk is the acli fixture

CAP = "not planned (cap)"
HEAD = "Carry-over: the batch cap left these issues out of earlier plan rounds: "
TAIL = ". Plan them before the other issues, unless one is an umbrella or tracking issue."


def brief(ns):
    return (ns.sd / "briefs" / "triage.md").read_text()


def nums(ns):
    return [i["number"] for i in briefed(ns)]


def seed(ns, **kw):
    bs.update(bs.path(ns.root), lambda d: d.update(kw))


@pytest.fixture
def no_acli(monkeypatch):
    monkeypatch.setattr(bl, "_acli", lambda a: pytest.fail("acli called"))


def test_pin_list_kinds_and_duplicates():
    assert bl.pin_list("1,1 #1, 433") == (False, [1, 433])
    assert bl.pin_list("pix-1, PIX-1 pix-2") == (True, ["PIX-1", "PIX-2"])
    assert bl.pin_list(" , ") == (False, [])


def test_issues_takes_github_numbers(bk, capsys, no_acli):
    rc, out = cli(capsys, "plan", "--issues", "2,#1")
    d = load(bk)
    assert rc == 0 and "B1 | #1 #2 | planned" in out
    assert nums(bk) == [2, 1] and "#3" not in brief(bk)
    assert d["outside"] == [] and d["titles"] == {"1": "One", "2": "Two"}


DIRECT = re.compile(r"repos/\{owner\}/\{repo\}/issues/(\d+)")
GONE = "gh: Not Found (HTTP 404)"


def rest(n, title, assoc="OWNER", state="open", pull=False, login="max"):
    """One issue as ISSUE_JQ shapes the REST answer of issues/N (#776)."""
    return {"number": n, "title": title, "body": f"body {n}", "author": {"login": login}, "authorAssociation": assoc,
            "state": state, "pull": pull}


def lagging(bk, monkeypatch, read):
    """gh whose open-issue list holds only ISSUES (1 to 3); issues/N answers from read, any other number is a 404 (#776)."""
    def gh(args):
        bk.gh.append(args)
        if args[:2] == ["repo", "view"]:
            return {"nameWithOwner": "o/r", "visibility": bk.vis}
        m = DIRECT.fullmatch(args[1]) if args[0] == "api" and len(args) > 1 else None
        if m:
            n = int(m.group(1))
            if n not in read:
                raise RuntimeError(f"gh api repos/{{owner}}/{{repo}}/issues/{n} failed: {GONE}")
            return read[n]
        return ISSUES
    monkeypatch.setattr(bl, "_gh", gh)


def direct_reads(bk):
    return [int(DIRECT.fullmatch(a[1]).group(1)) for a in bk.gh if a[0] == "api" and len(a) > 1 and DIRECT.fullmatch(a[1])]


def test_pinned_issue_missing_from_the_list_is_read_by_number_776(bk, capsys, monkeypatch, no_acli):
    lagging(bk, monkeypatch, {4: rest(4, "Four")})
    bk.batches = [{**BATCH, "issues": [4]}]
    rc, out = cli(capsys, "plan", "--issues", "4")
    assert rc == 0 and "B1 | #4 | planned" in out and "not found" not in out
    assert nums(bk) == [4] and "body 4" in brief(bk)
    assert ["api", "repos/{owner}/{repo}/issues/4", "--jq", bl.ISSUE_JQ] in bk.gh
    assert load(bk)["titles"] == {"4": "Four"}


def test_listed_pins_read_nothing_by_number_776(bk, capsys, monkeypatch, no_acli):
    lagging(bk, monkeypatch, {})
    assert cli(capsys, "plan", "--issues", "2,1")[0] == 0
    assert direct_reads(bk) == []


def test_partial_miss_plans_the_rest_and_prints_not_found_on_stdout_776(bk, capsys, monkeypatch, no_acli):
    lagging(bk, monkeypatch, {})
    bk.batches = [{**BATCH, "issues": [1]}]
    rc, out = cli(capsys, "plan", "--issues", "1,9")
    line = f"not found: #9 (not in the open-issue list; read by number: {GONE}); sl backlog plan --issues 9 --add retries it"
    assert rc == 0 and line in out.splitlines()
    assert out.index("B1 | #1 | planned") < out.index(line)
    assert nums(bk) == [1] and [b["issues"] for b in load(bk)["batches"]] == [[1]]
    assert direct_reads(bk) == [9]


def test_every_pin_missing_blocks_with_the_reason_776(bk, capsys, monkeypatch, no_acli):
    lagging(bk, monkeypatch, {})
    assert cli(capsys, "plan", "--issues", "9,8") == (
        3, f"BLOCKED: GitHub issue #9 not found among the open issues nor read by number ({GONE})\n")
    assert load(bk)["batches"] == []


def test_closed_issue_and_pull_request_are_not_found_776(bk, capsys, monkeypatch, no_acli):
    lagging(bk, monkeypatch, {8: rest(8, "Eight", state="closed"), 7: rest(7, "Seven", pull=True)})
    bk.batches = [{**BATCH, "issues": [1]}]
    rc, out = cli(capsys, "plan", "--issues", "1,8,7")
    lines = out.splitlines()
    assert rc == 0 and nums(bk) == [1]
    assert "not found: #8 (not in the open-issue list; read by number: closed)" in lines
    assert "not found: #7 (not in the open-issue list; read by number: a pull request)" in lines


def test_issue_read_by_number_keeps_the_trust_check_776(bk, capsys, monkeypatch, no_acli):
    lagging(bk, monkeypatch, {5: rest(5, "Five", assoc="NONE", login="eve")})
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan", "--issues", "1,5")[0] == 0
    assert nums(bk) == [1] and load(bk)["outside"] == [{"number": 5, "title": "Five", "author": "eve"}]


def test_add_reads_a_fresh_issue_by_number_776(bk, capsys, monkeypatch, no_acli):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan")[0] == 0
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update(state="running"))
    lagging(bk, monkeypatch, {4: rest(4, "Four")})
    bk.batches = [{**BATCH, "topic": "urgent", "issues": [4], "files": ["b.py"]}]
    rc, out = cli(capsys, "plan", "--issues", "4", "--add")
    assert rc == 0 and "B2 | #4 | planned" in out
    assert [b["issues"] for b in load(bk)["batches"]] == [[1], [4]]


def test_pinned_issues_reads_only_missing_numbers_776(monkeypatch):
    reads = []
    monkeypatch.setattr(bl, "read_issue", lambda n: reads.append(n) or (None, "closed"))
    gone = []
    assert bl.pinned_issues(ISSUES, [2, 9, 1], gone) == [ISSUES[1], ISSUES[0]]
    assert reads == [9] and gone == [(9, "closed")]
    with pytest.raises(RuntimeError, match=r"^GitHub issue #9 not found among the open issues nor read by number \(closed\)$"):
        bl.pinned_issues(ISSUES, [9])


def test_read_issue_answer_shapes_776(monkeypatch):
    seen = []
    answers = {4: rest(4, "Four"), 8: rest(8, "Eight", state="closed"), 7: rest(7, "Seven", pull=True),
               6: [rest(6, "Six")], 5: rest(3, "Three")}
    fails = {9: f"failed:   gh: Not Found\n(HTTP 404)", 10: "failed: " + "x" * 300, 11: "failed: "}

    def gh(args):
        seen.append(args)
        n = int(DIRECT.fullmatch(args[1]).group(1))
        if n in fails:
            raise RuntimeError(f"gh api repos/{{owner}}/{{repo}}/issues/{n} {fails[n]}")
        return answers[n]
    monkeypatch.setattr(bl, "_gh", gh)
    assert bl.read_issue(4) == ({"number": 4, "title": "Four", "body": "body 4", "author": {"login": "max"},
                                 "authorAssociation": "OWNER"}, None)
    assert seen[0] == ["api", "repos/{owner}/{repo}/issues/4", "--jq", bl.ISSUE_JQ]
    assert bl.read_issue(8) == (None, "closed")
    assert bl.read_issue(7) == (None, "a pull request")
    assert bl.read_issue(6) == (None, "no issue in the answer")
    assert bl.read_issue(5) == (None, "no issue in the answer")
    assert bl.read_issue(9) == (None, GONE)
    assert bl.read_issue(10) == (None, "x" * 120)
    assert bl.read_issue(11) == (None, "gh failed")


def test_issue_jq_keeps_the_listing_fields_776():
    for field in ("number", "title", "body", "author: {login: .user.login}", "authorAssociation: .author_association"):
        assert field in bl.ISSUES_JQ and field in bl.ISSUE_JQ
    assert "state" in bl.ISSUE_JQ and 'pull: has("pull_request")' in bl.ISSUE_JQ


def test_bad_pin_lists_refused_before_any_call(bk, capsys, no_acli):
    assert cli(capsys, "plan", "--issues", "12,PIX-1") == (2, "BLOCKED: --issues: not a GitHub issue number: PIX-1\n")
    assert cli(capsys, "plan", "--issues", "foo") == (2, "BLOCKED: --issues: not a GitHub issue number or Jira key: foo\n")
    assert cli(capsys, "plan", "--issues", "#0,1") == (2, "BLOCKED: --issues: not a GitHub issue number or Jira key: #0\n")
    assert cli(capsys, "plan", "--issues", "PIX-1,12") == (2, "BLOCKED: --issues: not a Jira key: 12\n")
    assert cli(capsys, "plan", "--issues", " ") == (2, "BLOCKED: --issues is empty\n")
    assert bk.gh == []


def test_pinned_skipped_issue_refused(bk, capsys, no_acli):
    seed(bk, skipped=[2, "PIX-1"])
    assert cli(capsys, "plan", "--issues", "1,2") == (2, "BLOCKED: --issues: #2 is skipped; sl backlog unskip 2 takes it back\n")
    assert cli(capsys, "plan", "--issues", "pix-1") == (2, "BLOCKED: --issues: PIX-1 is skipped; sl backlog unskip PIX-1 takes it back\n")
    assert bk.gh == []


def test_untrusted_pinned_issue_stays_an_admit_entry(bk, capsys, no_acli):
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan", "--issues", "3,1")[0] == 0
    assert nums(bk) == [1] and load(bk)["outside"] == [{"number": 3, "title": "Three", "author": "eve"}]


def test_pinned_plan_keeps_left_out_entries_of_other_issues(bk, capsys, no_acli):
    eve = {"number": 3, "title": "Three", "author": "eve"}
    two = {"number": 2, "title": "Two", "reason": CAP}
    seed(bk, outside=[eve, two, {"number": "PIX-9", "title": "J", "reason": CAP}])
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan", "--issues", "1")[0] == 0
    assert load(bk)["outside"] == [eve, two]
    assert "Carry-over" not in brief(bk)


def test_cap_carry_over_ranked_first_and_counted(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "MAX_BATCHES", 1)
    bk.vis = "PRIVATE"
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan")[0] == 0
    assert nums(bk) == [1, 2, 3] and "Carry-over" not in brief(bk)
    assert load(bk)["outside"] == [{"number": 2, "title": "Two", "reason": CAP}, {"number": 3, "title": "Three", "reason": CAP}]
    assert cli(capsys, "plan", "--reset")[0] == 0
    assert nums(bk) == [2, 3, 1] and HEAD + "#2 (1 round), #3 (1 round)" + TAIL in brief(bk)
    assert load(bk)["outside"] == [{"number": 2, "title": "Two", "reason": CAP, "rounds": 2},
                                   {"number": 3, "title": "Three", "reason": CAP, "rounds": 2}]
    bk.batches = [{**BATCH, "issues": [2]}]
    assert cli(capsys, "plan", "--reset")[0] == 0
    assert nums(bk) == [2, 3, 1] and HEAD + "#2 (2 rounds), #3 (2 rounds)" + TAIL in brief(bk)
    assert load(bk)["outside"] == [{"number": 3, "title": "Three", "reason": CAP, "rounds": 3},
                                   {"number": 1, "title": "One", "reason": CAP}]


def test_most_rounds_first_and_triage_resets_the_count(bk, capsys):
    bk.vis = "PRIVATE"
    seed(bk, outside=[{"number": 3, "title": "Three", "reason": CAP}, {"number": 2, "title": "Two", "reason": CAP, "rounds": 3}])
    assert cli(capsys, "plan")[0] == 0
    assert nums(bk) == [2, 3, 1] and HEAD + "#2 (3 rounds), #3 (1 round)" + TAIL in brief(bk)
    assert load(bk)["outside"] == [{"number": 3, "title": "Three", "reason": "not planned (triage)"}]


def test_issue_past_the_fetch_limit_carried_into_the_brief(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "ISSUE_LIMIT", 2)
    bk.vis = "PRIVATE"
    seed(bk, outside=[{"number": 3, "title": "Three", "reason": "not triaged (2 cap)"}])
    bk.batches = [{**BATCH, "issues": [3, 1]}]
    assert cli(capsys, "plan")[0] == 0
    assert nums(bk) == [3, 1] and HEAD + "#3 (1 round)" + TAIL in brief(bk) and "#2" not in brief(bk)
    assert load(bk)["outside"] == [{"number": 2, "title": "Two", "reason": "not triaged (2 cap)"}]


def test_bad_rounds_count_as_one_and_bad_entries_are_ignored(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "MAX_BATCHES", 1)
    bk.vis = "PRIVATE"
    seed(bk, outside=[{"number": 2, "title": "Two", "reason": CAP, "rounds": True},
                      {"number": 3, "title": "Three", "reason": CAP, "rounds": "x"}, {"number": [1], "reason": CAP}, "junk"])
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan")[0] == 0
    assert load(bk)["outside"] == [{"number": 2, "title": "Two", "reason": CAP, "rounds": 2},
                                   {"number": 3, "title": "Three", "reason": CAP, "rounds": 2}]


def test_jira_key_carried_first(jk, capsys):
    seed(jk, outside=[{"number": "PIX-2", "title": "Two", "reason": CAP}])
    assert cli(capsys, "plan", "--jql", "x")[0] == 0
    assert nums(jk) == ["PIX-2", "PIX-1"] and HEAD + "PIX-2 (1 round)" + TAIL in brief(jk)
    d = load(jk)
    assert sorted(d["batches"][0]["issues"]) == ["PIX-1", "PIX-2"] and d["outside"] == []


def test_no_carry_no_line(bk, capsys):
    assert cli(capsys, "plan")[0] == 0
    assert "Carry-over" not in brief(bk)


def test_carry_helpers():
    out = [{"number": 2, "reason": CAP, "rounds": 4}, {"number": 5, "reason": "not triaged (200 cap)"},
           {"number": 6, "reason": "not planned (triage)"}, {"number": 7, "author": "eve"}, {"number": True, "reason": CAP}]
    assert bl.carry_rounds(out) == {2: 4, 5: 1}
    assert bl.carry_rounds(None) == {}
    trusted = [{"number": 5}, {"number": 2}, {"number": 9}]
    assert bb.carry_line(trusted, {2: 4, 5: 1}) == HEAD + "#5 (1 round), #2 (4 rounds)" + TAIL
    assert bb.carry_line(trusted, {}) is None


def test_help_names_github_numbers(capsys):
    with pytest.raises(SystemExit):
        bl.main(["plan", "--help"])
    assert "GitHub numbers (362,#433) or Jira keys" in " ".join(capsys.readouterr().out.split())


PIN_HEAD = "Pinned: main chose these issues with --issues; plan each one."
PIN_AT = "work already on the default branch (at 48888dd, version 1.5.125) is not missing."


def test_pinned_line_text_622():
    r = bb.pinned_line("48888dd", "1.5.125")
    assert r.startswith(PIN_HEAD) and r.endswith('(e.g. "needs 1.6.0 first"); ' + PIN_AT)
    assert bb.pinned_line(None, None).endswith("work already on the default branch is not missing.")
    assert bb.pinned_line(None, "1.5.125").endswith("work already on the default branch (version 1.5.125) is not missing.")
    assert "\x1b" not in bb.pinned_line("ab\x1bcd", "1.5\x1b")


def test_triage_brief_puts_the_pinned_line_before_rules_622():
    issues = [{"number": 1, "title": "t", "body": "b"}]
    lines = bb.triage_brief(issues, {"repo": "r", "max_batches": 3, "pinned": {"head": "48888dd", "version": "1.5.125"}}).splitlines()
    i = next(k for k, x in enumerate(lines) if x.startswith("Pinned: "))
    assert lines[i] == bb.pinned_line("48888dd", "1.5.125") and lines[i + 1].startswith("Rules: ")
    assert "Pinned:" not in bb.triage_brief(issues, {"repo": "r", "max_batches": 3})


def test_pinned_plan_writes_one_line_built_by_the_brief_622(bk, capsys, no_acli, monkeypatch):
    import inspect
    import backlog_intake as bi
    import backlog_ship
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: ["48888dd\tsubject"])
    monkeypatch.setattr(backlog_ship, "_current_version", lambda root: "1.5.125")
    assert cli(capsys, "plan", "--issues", "2,#1")[0] == 0
    lines = brief(bk).splitlines()
    pins = [k for k, x in enumerate(lines) if x.startswith("Pinned: ")]
    assert len(pins) == 1 and lines[pins[0]] == bb.pinned_line("48888dd", "1.5.125") and lines[pins[0] + 1].startswith("Rules: ")
    assert not hasattr(bi, "pinned_rule") and not hasattr(bi, "insert_before_rules")
    assert "extra" not in inspect.signature(bl._triage).parameters
