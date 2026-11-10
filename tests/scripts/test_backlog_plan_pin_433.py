"""sl backlog plan --issues takes GitHub numbers, and issues an earlier cap left out are ranked first (#433)."""
import pytest

import backlog_brief as bb
from test_backlog_cli import bk, cli, load, BATCH, bl, bs  # noqa: F401  bk is the CLI fixture
from test_backlog_jira_208 import jk  # noqa: F401  jk is the acli fixture

CAP = "not planned (cap)"
HEAD = "Carry-over: the batch cap left these issues out of earlier plan rounds: "
TAIL = ". Plan them before the other issues, unless one is an umbrella or tracking issue."


def brief(ns):
    return (ns.sd / "briefs" / "triage.md").read_text()


def nums(ns):
    return [i["number"] for i in ns.issues]


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


def test_issues_number_not_open_is_blocked(bk, capsys, no_acli):
    assert cli(capsys, "plan", "--issues", "9") == (3, "BLOCKED: GitHub issue #9 not found among the open issues\n")
    assert load(bk)["batches"] == []


def test_bad_pin_lists_refused_before_any_call(bk, capsys, no_acli):
    assert cli(capsys, "plan", "--issues", "12,PIX-1") == (2, "BLOCKED: --issues: not a GitHub issue number: PIX-1\n")
    assert cli(capsys, "plan", "--issues", "foo") == (2, "BLOCKED: --issues: not a GitHub issue number or Jira key: foo\n")
    assert cli(capsys, "plan", "--issues", "#0,1") == (2, "BLOCKED: --issues: not a GitHub issue number or Jira key: #0\n")
    assert cli(capsys, "plan", "--issues", "PIX-1,12") == (2, "BLOCKED: --issues: not a Jira key: 12\n")
    assert cli(capsys, "plan", "--issues", " ") == (2, "BLOCKED: --issues is empty\n")
    assert bk.gh == []


def test_pinned_skipped_issue_refused(bk, capsys, no_acli):
    seed(bk, skipped=[2, "PIX-1"])
    assert cli(capsys, "plan", "--issues", "1,2") == (2, "BLOCKED: --issues: #2 is skipped\n")
    assert cli(capsys, "plan", "--issues", "pix-1") == (2, "BLOCKED: --issues: PIX-1 is skipped\n")
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
    bk.issues.clear()
    assert cli(capsys, "plan", "--reset")[0] == 0
    assert nums(bk) == [2, 3, 1] and HEAD + "#2 (1 round), #3 (1 round)" + TAIL in brief(bk)
    assert load(bk)["outside"] == [{"number": 2, "title": "Two", "reason": CAP, "rounds": 2},
                                   {"number": 3, "title": "Three", "reason": CAP, "rounds": 2}]
    bk.issues.clear()
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
