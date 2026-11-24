"""#1095: a Jira-source plan's main_steps name the batch's Jira keys; a bare number is matched to its key or named."""
import sys

from test_backlog_cli import bk, cli, load  # noqa: F401  bk is the CLI fixture jk builds on
from test_backlog_jira_208 import JB, jk  # noqa: F401
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_checks as bc  # noqa: E402

KEYS = {1: "PIX-123", 2: "PIX-7"}
GEN = "w issues: a non-empty list of this batch's issues"


def step(issues):
    return {"issues": issues, "runs": "main", "command": "git lfs install"}


def test_key_kept_and_upper_cased():
    assert bc.check_step(step(["PIX-7"]), "w", [1, 2], KEYS) == (step(["PIX-7"]), [])
    assert bc.check_step(step(["pix-123"]), "w", [1, 2], KEYS) == (step(["PIX-123"]), [])


def test_bare_number_matches_its_key_not_the_index():
    assert bc.check_step(step([123, 7]), "w", [1, 2], KEYS) == (step(["PIX-123", "PIX-7"]), [])
    assert bc.check_step(step([1]), "w", [1, 2], KEYS) == (None, ["w issues: 1 matches no Jira key of this batch (PIX-123, PIX-7)"])


def test_same_issue_twice_kept_once():
    assert bc.check_step(step([123, "PIX-123"]), "w", [1, 2], KEYS) == (step(["PIX-123"]), [])


def test_key_of_another_batch_named():
    assert bc.check_step(step(["PIX-7"]), "w", [1], KEYS) == (None, ["w issues: PIX-7 is not one of this batch's issues (PIX-123)"])


def test_number_two_keys_share_is_named():
    keys = {1: "PIX-5", 2: "ABC-5"}
    assert bc.check_step(step([5]), "w", [1, 2], keys) == (None, ["w issues: 5 matches PIX-5 and ABC-5; write the key"])


def test_empty_or_odd_items_keep_the_old_message():
    for bad in ([], "PIX-7", [True], [None], [1.5]):
        assert bc.check_step(step(bad), "w", [1, 2], KEYS) == (None, [GEN])


def test_without_keys_numbers_only_as_before():
    assert bc.check_step(step(["PIX-7"]), "w", [12]) == (None, [GEN])
    assert bc.check_step(step([12]), "w", [12]) == (step([12]), [])


def test_proposal_stores_keys():
    p = {"batches": [{"id": "B1", "topic": "t", "issues": [1, 2], "files": ["a.py"], "depends": [], "main_steps": [step([7])]}]}
    out, errs = bc.check_proposal(p, {1, 2}, keys=KEYS)
    assert errs == [] and out[0]["main_steps"] == [step(["PIX-7"])] and out[0]["issues"] == [1, 2]


def test_plan_stores_step_keys(jk, capsys):
    jk.batches = [{**JB, "main_steps": [step(["PIX-2"]), {"issues": [1], "runs": "user", "command": "acli jira auth login"}]}]
    rc, out = cli(capsys, "plan", "--jql", "x")
    assert rc == 0, out
    assert load(jk)["batches"][0]["main_steps"] == [step(["PIX-2"]), {"issues": ["PIX-1"], "runs": "user", "command": "acli jira auth login"}]
    assert "step B1: main runs this: git lfs install (PIX-2)" in out and "step B1: Max runs this: acli jira auth login (PIX-1)" in out


def test_plan_names_an_unmatched_number(jk, capsys):
    jk.batches = [{**JB, "main_steps": [step([9])]}]
    rc, out = cli(capsys, "plan", "--jql", "x")
    assert rc == 3 and "B1 main_steps 1 issues: 9 matches no Jira key of this batch (PIX-1, PIX-2)" in out
