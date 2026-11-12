import json
import pytest
import test_backlog_cli as tc
from test_backlog_cli import bk, cli, load, BATCH, bs, bl  # noqa: F401
import backlog_tracker

TWO = {**BATCH, "issues": [2]}
REAL_SUBJECTS = bl._subjects  # saved before the autouse fake patches it; no importlib.reload mid-suite


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(bl, "_tracked", lambda root: [])
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: [])


def brief(bk):
    return (bk.sd / "briefs" / "triage.md").read_text()


def test_issue_of_shipped_batch_is_not_triaged(bk, capsys):
    bs.update(bs.path(bk.root), lambda d: d["batches"].append({**BATCH, "id": "B7", "issues": [1], "state": "shipped"}))
    bk.batches = [TWO]
    rc, out = cli(capsys, "plan")
    assert rc == 0 and "#1 One" not in brief(bk) and "#2 Two" in brief(bk)
    assert "already shipped: #1 in B7" in out


def test_merged_subject_leaves_issue_out(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: ["abc1234\tFix two (#2) (#40)"])
    bk.batches = [{**BATCH, "issues": [1]}]
    rc, out = cli(capsys, "plan")
    assert rc == 0 and "#2 Two" not in brief(bk)
    assert {"number": 2, "title": "Two", "reason": "not planned (shipped: PR #40)"} in [
        {k: o[k] for k in ("number", "title", "reason")} for o in load(bk)["outside"] if "reason" in o]
    assert "not planned (shipped: PR #40): #2" in out


def test_pinned_shipped_issue_is_planned_anyway(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: ["abc1234\tFix two (#2) (#40)"])
    bk.batches = [TWO]
    rc, out = cli(capsys, "plan", "--issues", "2")
    assert rc == 0 and load(bk)["batches"][0]["issues"] == [2]
    assert "already shipped?: #2 named by merged PR #40: planned anyway (pinned)" in out


def test_everything_shipped_plans_nothing(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "_subjects", lambda root, ref: ["abc1234\tFix (#1) (#40)", "def5678\tFix (#2) (#41)"])
    before = bs.path(bk.root).exists()
    rc, out = cli(capsys, "plan")
    assert rc == 0 and "nothing to plan: every issue is already shipped" in out
    assert bs.path(bk.root).exists() == before
    assert not any(c[0] in ("spawn", "send") for c in bk.calls)


def test_pinned_brief_has_the_rule(bk, capsys):
    bk.batches = [TWO]
    assert cli(capsys, "plan", "--issues", "2")[0] == 0
    assert "Pinned: main chose these issues" in brief(bk)
    cli(capsys, "plan", "--reset")
    assert "Pinned:" not in brief(bk)


def test_blocked_pin_gets_check_line(bk, capsys):
    prop = {"status": "DONE", "summary": "x", "batches": [{**BATCH, "issues": [1]}],
            "left_out": [{"issues": [2], "reason": "needs the fleet rework first"}]}
    f = bk.root / "p.json"
    f.write_text(json.dumps(prop))
    rc, out = cli(capsys, "plan", "--issues", "1,2", "--proposal", str(f))
    assert rc == 0
    assert 'check: #2 left out as "needs the fleet rework first" without naming the missing commit or version; sl backlog plan --issues 2 --add plans it again' in out


def test_subjects_failure_gives_empty(tmp_path):
    main = bl.main
    assert REAL_SUBJECTS(tmp_path / "nope", "main") == []
    assert bl.main is main  # no reload: test_backlog_cli and the others keep the module's own objects


class Jira:
    def __init__(self, bk, monkeypatch, view):
        self.bk = bk
        bk.batches = [{**BATCH, "issues": ["PIX-1", "PIX-2"]}]
        monkeypatch.setattr(bl, "_acli", lambda args: [tc_acli()[0]])
        self.seen = []

        def by_key(keys):
            self.seen.append(list(keys))
            return view(keys)
        monkeypatch.setattr(backlog_tracker, "jira_by_key", by_key)


def tc_acli():
    return [{"key": "PIX-1", "fields": {"summary": "One", "description": None}}]


def test_missing_jira_key_read_by_key(bk, capsys, monkeypatch):
    j = Jira(bk, monkeypatch, lambda keys: ([{"number": "PIX-2", "title": "Two", "body": ""}], []))
    rc, out = cli(capsys, "plan", "--issues", "PIX-1,PIX-2")
    assert rc == 0 and j.seen == [["PIX-2"]]
    assert load(bk)["batches"][0]["issues"] == ["PIX-1", "PIX-2"]


def test_missing_jira_key_others_plan(bk, capsys, monkeypatch):
    Jira(bk, monkeypatch, lambda keys: ([], list(keys)))
    bk.batches = [{**BATCH, "issues": ["PIX-1"]}]
    rc, out = cli(capsys, "plan", "--issues", "PIX-1,PIX-2")
    assert rc == 0 and load(bk)["batches"][0]["issues"] == ["PIX-1"]
    assert "not found: PIX-2 (Jira search and read by key); sl backlog plan --issues PIX-2 --add retries it" in out


def test_all_pinned_jira_keys_missing_blocks(bk, capsys, monkeypatch):
    Jira(bk, monkeypatch, lambda keys: ([], list(keys)))
    monkeypatch.setattr(bl, "_acli", lambda args: [])
    rc, out = cli(capsys, "plan", "--issues", "PIX-2")
    assert (rc, out) == (3, "BLOCKED: Jira issue PIX-2 not found\n")


def test_status_reads_markers_in_one_call(bk, capsys, monkeypatch):
    def seed(d):
        d["repo"] = "o/r"
        d["batches"] = [{**BATCH, "id": "B1", "issues": [5], "state": "shipped", "open_issues": [5]},
                        {**BATCH, "id": "B2", "issues": [6], "state": "shipped", "open_issues": [6, "PIX-1"]}]
    bs.update(bs.path(bk.root), seed)
    calls = []

    def fake(repo, issues, root):
        calls.append((repo, list(issues)))
        return [6]
    monkeypatch.setattr(backlog_tracker, "open_now", fake)
    rc, out = cli(capsys, "status")
    assert rc == 0 and calls == [("o/r", [5, 6, "PIX-1"])]
    assert [b["open_issues"] for b in load(bk)["batches"]] == [[], [6]]
