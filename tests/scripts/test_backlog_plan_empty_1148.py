"""An empty triage proposal reads as nothing to plan; plan reads new issues by number (#1148)."""
import json
import re

import pytest

from test_backlog_cli import bk, briefed, cli, load, BATCH, bl, bs  # noqa: F401  bk is the CLI fixture
from test_backlog_plan_pin_433 import DIRECT, direct_reads, rest

LAST = "nothing to plan: the proposal holds no batch; sl backlog skip <issue> keeps an issue out of every later plan"
TAIL = "an issue filed in the last minutes may be missing: sl backlog plan --issues <n> --add plans it"
LAG = "listing lag: #{} read by number (not in the open-issue list yet)"


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture
def probe(bk, monkeypatch):
    """bk with a gh whose open list is ISSUES; issues/N answers from probe.reads, a missing number is a 404, probe.fail[N] raises."""
    from test_backlog_cli import ISSUES
    st = type("P", (), {})()
    st.reads, st.fail, st.open = {}, {}, ISSUES
    st.subj = []

    def gh(args):
        bk.gh.append(args)
        if args[:2] == ["repo", "view"]:
            return {"nameWithOwner": "o/r", "visibility": bk.vis}
        m = DIRECT.fullmatch(args[1]) if args[0] == "api" and len(args) > 1 else None
        if m:
            n = int(m.group(1))
            if n in st.fail:
                raise RuntimeError(st.fail[n])
            if n not in st.reads:
                raise RuntimeError(f"gh api repos/{{owner}}/{{repo}}/issues/{n} failed: gh: Not Found (HTTP 404)")
            return st.reads[n]
        return st.open
    monkeypatch.setattr(bl, "_gh", gh)
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: st.subj)
    return st


def test_newest_known_1148():
    data = {"batches": [{"issues": [7]}], "outside": [{"number": 5}, {"number": "PIX-1"}],
            "titles": {"9": "x", "PIX-2": "y"}, "admitted": [2], "skipped": [11]}
    assert bl.newest_known([{"number": 3}], data, ["a\tFix (#8)", "b\tno ref"]) == 11
    assert bl.newest_known([{"number": True}], {"admitted": [True], "titles": {"x9": 1}}, []) == 0
    assert bl.newest_known([], {}, []) == 0
    assert bl.newest_known([], {}, ["a\tno trailing ref (#4) here"]) == 0


def test_empty_done_proposal_reads_nothing_to_plan_1148(bk, capsys):
    bk.batches, bk.summary = [], "all covered"
    rc, out = cli(capsys, "plan")
    lines = out.splitlines()
    assert rc == 0
    assert not [x for x in lines if x.startswith("BLOCKED")]
    assert "not planned (triage): #1 #2" in lines and "triage worker DONE: all covered" in lines
    assert lines[-1] == LAST
    assert not (bk.sd / "backlog-proposal.json").exists()
    assert load(bk)["batches"] == []


def test_empty_proposal_file_reads_nothing_to_plan_1148(bk, capsys):
    f = bk.root / "e.json"
    f.write_text(json.dumps({"batches": []}))
    rc, out = cli(capsys, "plan", "--proposal", str(f))
    lines = out.splitlines()
    assert rc == 0 and lines[-1] == LAST
    assert not [x for x in lines if x.startswith("BLOCKED") or x.startswith("triage worker")]
    assert not [c for c in bk.calls if c[0] == "spawn"]


def test_failed_worker_empty_proposal_stays_blocked_1148(bk, capsys):
    bk.batches, bk.status = [], "NEEDS_CONTEXT"
    rc, out = cli(capsys, "plan")
    assert rc == 3 and "BLOCKED: proposal rejected" in out
    assert not [x for x in out.splitlines() if x.startswith(("nothing to plan", "not planned"))]


def test_plain_plan_reads_new_issue_by_number_1148(bk, probe, capsys):
    probe.reads = {4: rest(4, "Four")}
    bk.batches = [{**BATCH, "issues": [1, 2, 4]}]
    rc, out = cli(capsys, "plan")
    lines = out.splitlines()
    assert rc == 0
    assert LAG.format(4) in lines
    assert 4 in [i["number"] for i in briefed(bk)]
    assert direct_reads(bk) == [4, 5]
    assert not [x for x in lines if x.startswith("listing: ")]


def test_probe_walks_past_prs_and_closed_issues_1148(bk, probe, capsys):
    probe.reads = {4: rest(4, "P", pull=True), 5: rest(5, "C", state="closed"), 6: rest(6, "Six")}
    bk.batches = [{**BATCH, "issues": [1, 2, 6]}]
    rc, out = cli(capsys, "plan")
    assert rc == 0
    assert direct_reads(bk) == [4, 5, 6, 7]
    assert [i["number"] for i in briefed(bk)] == [1, 2, 6]
    assert [x for x in out.splitlines() if x.startswith("listing lag:")] == [LAG.format(6)]


def test_probe_starts_above_newest_known_number_1148(bk, probe, capsys):
    bs.update(bs.path(bk.root), lambda d: d.update(outside=[{"number": 10, "title": "Ten", "reason": "not planned (triage)"}]))
    probe.subj = ["abc\tFix x (#12)"]
    assert cli(capsys, "plan")[0] == 0
    assert direct_reads(bk)[0] == 13


def test_probe_cap_prints_listing_hint_1148(bk, probe, capsys):
    probe.reads = {n: rest(n, "C", state="closed") for n in range(4, 21)}
    rc, out = cli(capsys, "plan")
    assert rc == 0
    assert direct_reads(bk) == list(range(4, 14))
    assert f"listing: read #4 to #13 by number and stopped at the 10-read cap; {TAIL}" in out.splitlines()


def test_probe_gh_failure_prints_listing_hint_1148(bk, probe, capsys):
    probe.fail = {4: "gh api repos/{owner}/{repo}/issues/4 failed: HTTP 502 Bad Gateway"}
    rc, out = cli(capsys, "plan")
    assert rc == 0 and direct_reads(bk) == [4]
    assert f"listing: stopped reading by number at #4 (HTTP 502 Bad Gateway); {TAIL}" in out.splitlines()


def test_pinned_plan_does_not_probe_1148(bk, probe, capsys):
    bk.batches = [{**BATCH, "issues": [1]}]
    assert cli(capsys, "plan", "--issues", "1")[0] == 0
    assert direct_reads(bk) == []


def test_proposal_plan_does_not_probe_1148(bk, probe, capsys):
    f = bk.root / "p.json"
    f.write_text(json.dumps({"batches": [{**BATCH, "issues": [1]}]}))
    assert cli(capsys, "plan", "--proposal", str(f))[0] == 0
    assert direct_reads(bk) == []


def test_no_open_issue_plans_nothing_without_a_worker_1148(bk, probe, capsys):
    probe.open = []
    rc, out = cli(capsys, "plan")
    assert rc == 0 and out.splitlines()[-1] == "nothing to plan: no open issue to triage"
    assert not [c for c in bk.calls if c[0] == "spawn"]
    assert direct_reads(bk) == [1]


def test_probed_outsider_stays_outside_1148(bk, probe, capsys):
    probe.reads = {4: rest(4, "Four", assoc="NONE", login="eve")}
    bk.batches = [BATCH]
    rc, out = cli(capsys, "plan")
    assert rc == 0
    assert 4 not in [i["number"] for i in briefed(bk)]
    assert {"number": 4, "title": "Four", "author": "eve"} in load(bk)["outside"]
