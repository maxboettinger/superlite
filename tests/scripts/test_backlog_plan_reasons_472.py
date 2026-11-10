"""sl backlog plan stores the triage worker's left-out reasons and names the empty-proposal way out (#472, #509)."""
import json
import sys

import pytest

from test_backlog_cli import bk, cli, load, BATCH, bl, bs  # noqa: F401  bk is the CLI fixture
from test_backlog_jira_208 import jk, JB  # noqa: F401  jk is the acli fixture
import backlog_brief as bb


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def lo(bk, monkeypatch):
    """bk.left_out goes into the triage report next to the batches."""
    bk.left_out = None
    io = sys.modules["fleet_io"]

    def wait(sd, ids, timeout_ms):
        (sd / "fleet" / "reports").mkdir(parents=True, exist_ok=True)
        block = {"status": bk.status, "files": [], "tests": "", "findings": [], "summary": bk.summary, "batches": bk.batches}
        if bk.left_out is not None:
            block["left_out"] = bk.left_out
        (sd / "fleet" / "reports" / "triage.md").write_text("Status: DONE\n```json\n" + json.dumps(block) + "\n```")
        return [{"id": ids[0], "status": "DONE"}]
    monkeypatch.setattr(io, "wait", wait)
    return bk


def test_triage_reason_stored_and_shown(lo, capsys):
    lo.batches = [{**BATCH, "issues": [1]}]
    lo.left_out = [{"issues": [2], "reason": "needs design"}]
    rc, out = cli(capsys, "plan")
    assert rc == 0
    assert {"number": 2, "title": "Two", "reason": "not planned (triage: needs design)"} in load(lo)["outside"]
    assert "not planned (triage: needs design): #2" in out.splitlines()


def test_cap_without_reason_keeps_cap(lo, capsys, monkeypatch):
    monkeypatch.setattr(bl, "MAX_BATCHES", 1)
    lo.vis = "PRIVATE"
    lo.batches = [{**BATCH, "issues": [1]}]
    lo.left_out = [{"issues": [3], "reason": "dup of 1"}]
    assert cli(capsys, "plan")[0] == 0
    by = {o["number"]: o["reason"] for o in load(lo)["outside"]}
    assert by == {2: "not planned (cap)", 3: "not planned (triage: dup of 1)"}


def test_shipped_issue_never_left_out(lo, capsys):
    p = bs.path(lo.root)
    d = bs.default()
    d["batches"] = [{"id": "B1", "topic": "old", "issues": [2], "state": "shipped"}]
    d["outside"] = [{"number": 2, "title": "Two", "reason": "not planned (cap)"}]
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(d))
    lo.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan", "--issues", "1")[0] == 0
    assert all(o["number"] != 2 for o in load(lo)["outside"])


def test_empty_proposal_names_reasons_and_skip(lo, capsys):
    lo.batches = []
    lo.left_out = [{"issues": [1], "reason": "needs a human"}]
    rc, out = cli(capsys, "plan")
    lines = out.splitlines()
    assert rc == 3
    assert "not planned (triage: needs a human): #1" in lines
    assert "not planned (triage): #2" in lines
    assert "nothing to plan: sl backlog skip <issue> keeps an issue out of every later plan" in lines
    assert "(the proposal holds 0 batches)" in next(x for x in lines if x.startswith("triage worker"))


def test_reject_line_counts_batches(lo, capsys):
    two = [{**BATCH, "id": "B1", "issues": [9]}, {**BATCH, "id": "B2", "issues": [9], "files": ["b.py"]}]
    lo.batches = two
    rc, out = cli(capsys, "plan")
    assert rc == 3 and "(the proposal holds 2 batches)" in out
    (lo.root / ".superlite" / "backlog-proposal.json").unlink()
    lo.batches = two[:1]
    rc, out = cli(capsys, "plan")
    assert rc == 3 and "1 batch)" in out and "1 batches" not in out


def test_jira_left_out_reason(jk, lo, capsys):
    jk.batches = [{**JB, "issues": ["PIX-1"]}]
    jk.left_out = [{"issues": ["pix-2"], "reason": "outside work"}]
    assert cli(capsys, "plan", "--jql", "project = PIX")[0] == 0
    by = {o["number"]: o["reason"] for o in load(jk)["outside"]}
    assert by == {"PIX-2": "not planned (triage: outside work)"}


def test_brief_names_topic_limit_and_left_out():
    b = bb.triage_brief([{"number": 1, "title": "t"}], {"repo": "r", "max_batches": 3})
    assert "at most 40 characters" in b and "left_out" in b and "batch cap of 3" in b
    j = bb.triage_brief([{"number": "PIX-1", "title": "t"}], {"repo": "r", "max_batches": 3})
    assert '"left_out": [{"issues": ["<KEY>"]' in j


def test_brief_cap_cut_issues_get_no_left_out_entry():
    brief = bb.triage_brief([{"number": 1, "title": "t"}], {"repo": "r", "max_batches": 3})
    assert "only because of the batch cap" in brief and "no left_out entry" in brief
