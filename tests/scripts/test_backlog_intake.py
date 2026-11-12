import sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_intake as bi  # noqa: E402


def test_merged_refs_examples():
    assert bi.merged_refs(["48888dd\tFinal reviewer; 1.5.125 (#564) (#608)", "a1b2c3d\tFix (#564) (#600)"], False) == {564: "PR #608"}
    assert bi.merged_refs(["b2c3d4e\tMerge pull request #12 from x/y"], False) == {}
    assert bi.merged_refs(["a1b2c3d\tPIX-3: Fix y (#9)", "b2c3d4e\tPIX-4 and PIX-5 cleanup"], True) == {
        "PIX-3": "PR #9", "PIX-4": "commit b2c3d4e", "PIX-5": "commit b2c3d4e"}


def test_trailing_pr_is_not_an_issue():
    got = bi.merged_refs(["a1b2c3d\tFix #3 (#9)"], False)
    assert got == {3: "PR #9"} and 9 not in got


def test_first_subject_wins():
    assert bi.merged_refs(["aaaaaaa\tFix #3 (#9)", "bbbbbbb\tAgain #3 (#8)"], False) == {3: "PR #9"}


def test_no_tab_line_skipped():
    assert bi.merged_refs(["no tab #3"], False) == {}


def test_jira_keys_match_whole_keys():
    got = bi.merged_refs(["aaaaaaa\tPIX-120 done"], True)
    assert got == {"PIX-120": "commit aaaaaaa"}


def test_shipped_batch_beats_merged_subject():
    t = [{"number": 5, "title": "A", "body": ""}]
    kept, dropped, lines = bi.split_shipped(t, [{"id": "B7", "state": "shipped", "issues": [5], "pr": 608}], {5: "PR #1"}, [])
    assert kept == [] and dropped == []
    assert lines == ["already shipped: #5 in B7 (PR #608): not planned again"]


def test_split_shipped_examples():
    t = [{"number": 5, "title": "A", "body": ""}, {"number": 6, "title": "B", "body": ""}]
    b = [{"id": "B7", "state": "shipped", "issues": [5], "pr": 608}]
    assert bi.split_shipped(t, b, {6: "PR #20"}, []) == ([], [{"number": 6, "title": "B", "reason": "not planned (shipped: PR #20)"}], [
        "already shipped: #5 in B7 (PR #608): not planned again",
        "already shipped: #6 named by merged PR #20: not planned; close it, or sl backlog skip 6 keeps it out"])
    t6 = [t[1]]
    assert bi.split_shipped(t6, [], {6: "PR #20"}, [6]) == (t6, [], [
        "already shipped?: #6 named by merged PR #20: planned anyway (pinned); sl backlog skip 6 drops it"])


def test_shipped_batch_without_pr():
    _, _, lines = bi.split_shipped([{"number": 5, "title": "A", "body": ""}], [{"id": "B7", "state": "shipped", "issues": [5]}], {}, [])
    assert lines == ["already shipped: #5 in B7: not planned again"]


def test_lines_drop_control_characters():
    t = [{"number": 6, "title": "B\x1b[31m", "body": ""}]
    _, dropped, lines = bi.split_shipped(t, [], {6: "PR #20"}, [])
    assert "\x1b" not in dropped[0]["title"] and not any("\x1b" in x for x in lines)
    got = bi.blocked_lines({"left_out": [{"issues": [1], "reason": "needs\x1b x first"}]}, [1], None)
    assert got and "\x1b" not in got[0]


def test_jira_key_plain_ref():
    t = [{"number": "PIX-6", "title": "B", "body": ""}]
    kept, dropped, lines = bi.split_shipped(t, [], {"PIX-6": "PR #3"}, [])
    assert lines == ["already shipped: PIX-6 named by merged PR #3: not planned; close it, or sl backlog skip PIX-6 keeps it out"]


TR = ["s/scripts/backlog.py", "s/scripts/backlog_checks.py", "s/backlog.md", "commands/backlog.md"]


def test_named_files_example():
    assert bi.named_files("Where: backlog_checks.py, backlog.py plan, backlog.md, 1.5.123.", TR) == ["s/scripts/backlog.py", "s/scripts/backlog_checks.py"]


def test_ambiguous_basename_is_skipped():
    assert bi.named_files("see backlog.md", TR) == []


def test_dot_slash_and_trailing_punctuation():
    assert bi.named_files("edit `./s/scripts/backlog.py`, now", TR) == ["s/scripts/backlog.py"]
    assert bi.named_files("edit s/scripts/backlog.py.", TR) == ["s/scripts/backlog.py"]


def bl(reason, version="1.5.125", pin=(12,)):
    return bi.blocked_lines({"left_out": [{"issues": [12], "reason": reason}]}, list(pin), version)


def test_blocked_lines_example():
    prop = {"left_out": [{"issues": [12], "reason": "needs the fleet rework first"}, {"issues": [13], "reason": "needs 1.5.100 first"},
                         {"issues": [14], "reason": "umbrella issue"}]}
    assert bi.blocked_lines(prop, [12, 13, 14], "1.5.125") == [
        'check: #12 left out as "needs the fleet rework first" without naming the missing commit or version; sl backlog plan --issues 12 --add plans it again',
        'check: #13 left out as "needs 1.5.100 first" but the repository is at 1.5.125; sl backlog plan --issues 13 --add plans it again']


def test_reason_naming_commit_issue_or_batch_gives_no_line():
    for r in ("needs a1b2c3d first", "after #12", "waits for B7", "needs PIX-9"):
        assert bl(r) == [], r


def test_unpinned_left_out_gives_no_line():
    assert bl("needs the fleet rework first", pin=(99,)) == []


def test_version_compare_pads():
    assert bl("needs 1.6 first") == []
    assert len(bl("needs 1.5 first")) == 1


def test_no_version_known():
    assert bl("needs 1.6.0 first", None) == []


def test_pinned_rule():
    r = bi.pinned_rule("48888dd", "1.5.125")
    assert r.startswith("Pinned: main chose these issues with --issues; plan each one.")
    assert r.endswith('(e.g. "needs 1.6.0 first"); work already on the default branch (at 48888dd, version 1.5.125) is not missing.')
    assert bi.pinned_rule(None, None).endswith("work already on the default branch is not missing.")


def test_insert_before_rules():
    assert bi.insert_before_rules("# T\nx\nRules: a\nEnd\n", ["P"]) == "# T\nx\nP\nRules: a\nEnd\n"
    assert bi.insert_before_rules("# T\nx\n", ["P", "Q"]) == "# T\nx\nP\nQ\n"
    assert bi.insert_before_rules("# T", ["P"]) == "# T\nP"


def test_version_with_suffix_or_control_chars():
    prop = {"left_out": [{"issues": [1], "reason": "needs 1.5.1 first"}]}
    assert len(bi.blocked_lines(prop, [1], "1.5.125-rc1")) == 1
    assert len(bi.blocked_lines(prop, [1], "v1.5.125")) == 1
    assert bi.blocked_lines(prop, [1], "dev") == []
    got = bi.blocked_lines(prop, [1], "1.5.125\x1b[31m")
    assert got and "\x1b" not in got[0]
    assert "\x1b" not in bi.pinned_rule("ab\x1bcd", "1.5\x1b")
