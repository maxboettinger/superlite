import json, os, sys, types
import pytest
from backlog_fixtures import Q
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog as bl  # noqa: E402
import backlog_state as bs  # noqa: E402

ISSUES = [{"number": n, "title": t, "author": {"login": a}, "authorAssociation": r}
          for n, t, a, r in ((1, "One", "max", "OWNER"), (2, "Two", "co", "COLLABORATOR"), (3, "Three", "eve", "NONE"))]
BATCH = {"id": "B1", "topic": "first", "issues": [1, 2], "files": ["a.py"], "depends": [], "decisions": []}

@pytest.fixture
def bk(tmp_path, monkeypatch):
    root = tmp_path / "main"; (root / ".superlite").mkdir(parents=True)
    ns = types.SimpleNamespace(root=root, sd=root / ".superlite", calls=[], vis="PUBLIC", batches=[BATCH])
    monkeypatch.setattr(bl, "_root", lambda: root)
    monkeypatch.setattr(bl, "_gh", lambda args: {"nameWithOwner": "o/r", "visibility": ns.vis} if args[:2] == ["repo", "view"] else ISSUES)
    def wait(sd, ids, timeout_ms):
        (sd / "fleet" / "reports").mkdir(parents=True, exist_ok=True)
        block = {"status": "DONE", "files": [], "tests": "", "findings": [], "summary": "x", "batches": ns.batches}
        (sd / "fleet" / "reports" / "triage.md").write_text("Status: DONE\n```json\n" + json.dumps(block) + "\n```")
        return [{"id": ids[0], "status": "DONE"}]
    log = lambda *a: ns.calls.append(a)
    fakes = {"fleet": types.SimpleNamespace(main=lambda argv: log("fleet", argv) or 0,
                                            spawn=lambda sd, plan, tier, project, role="implementer": log("spawn", tier, role) or {"id": "W1"}),
             "fleet_state": types.SimpleNamespace(is_on=lambda sd: False),
             "fleet_io": types.SimpleNamespace(send_brief=lambda sd, wid, brief, label="": log("send", wid, brief, label) or label, wait=wait)}
    if os.environ.get("SUPERLITE_REAL") != "1":
        fakes["backlog_brief"] = types.SimpleNamespace(triage_brief=lambda issues, ctx: "\n".join(f"- #{i['number']} {i['title']}" for i in issues))
    for k, v in fakes.items():
        monkeypatch.setitem(sys.modules, k, v)
    return ns

def cli(capsys, *argv):
    rc = bl.main(list(argv)); return rc, capsys.readouterr().out

def load(bk):
    return bs.load(bs.path(bk.root))

def test_plan_records_trusted_batches_and_lists_outside_issues(bk, capsys):
    rc, out = cli(capsys, "plan")
    d, brief = load(bk), (bk.sd / "briefs" / "triage.md").read_text()
    assert rc == 0 and "B1 | #1 #2 | planned" in out and "questions: 2 open (sl backlog decide --print)" in out
    assert (d["repo"], d["titles"], d["outside"]) == ("o/r", {"1": "One", "2": "Two"}, [{"number": 3, "title": "Three", "author": "eve"}])
    assert "- #1 One" in brief and "#3" not in brief
    assert all(c in bk.calls for c in (("fleet", ["on", "--plan", str(bk.sd)]), ("spawn", "sonnet", "research"),
                                       ("send", "W1", str(bk.sd / "briefs" / "triage.md"), "triage")))

def test_outside_issues_cannot_be_smuggled_and_private_repos_trust_all(bk, capsys):
    bk.batches = [{**BATCH, "issues": [3]}]
    rc, out = cli(capsys, "plan")
    assert rc == 3 and "BLOCKED: proposal rejected" in out and "B1: unknown issue #3" in out and load(bk)["batches"] == []
    bk.vis = "PRIVATE"
    assert cli(capsys, "plan")[0] == 0 and load(bk)["outside"] == [] and "- #3 Three" in (bk.sd / "briefs" / "triage.md").read_text()

def test_plan_refuses_while_batches_are_open(bk, capsys):
    cli(capsys, "plan")
    assert cli(capsys, "plan") == (2, "BLOCKED: backlog has open batches (B1 planned)\n")
    assert cli(capsys, "plan", "--reset")[0] == 0
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "shipped"})); bk.batches = [{**BATCH, "issues": [2]}]
    assert cli(capsys, "plan")[0] == 0 and [(x["id"], x["state"]) for x in load(bk)["batches"]] == [("B1", "shipped"), ("B2", "planned")]

def test_decide_print_and_file(bk, capsys, tmp_path):
    cli(capsys, "plan")
    qs = json.loads(cli(capsys, "decide", "--print")[1])["questions"]
    assert qs[0]["question"] == bs.SHIP_Q and qs[1]["question"].startswith("Admit outside issue #3")
    f = tmp_path / "a.json"; f.write_text(json.dumps({"answers": {bs.SHIP_Q: "Approve shipping", qs[1]["question"]: "Skip"}}))
    assert cli(capsys, "decide", "--file", str(f)) == (0, "recorded 2 answers, 0 open\n")
    assert load(bk)["approved_ship"]["by"] == "AskUserQuestion" and load(bk)["skipped"] == [3]
    wt = tmp_path / "wt"; (wt / ".superlite").mkdir(parents=True); q = wt / ".superlite" / "question.json"
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "needs_decision", "worktree": str(wt)}))
    q.write_text(json.dumps(Q)); assert json.loads(cli(capsys, "decide", "--print", "--batch", "B1")[1]) == Q
    q.write_text('{"questions": []}')
    assert cli(capsys, "decide", "--print", "--batch", "B1") == (3, "BLOCKED: B1 question.json invalid: questions: 1 to 4 entries\n")

def test_status_and_router(bk, capsys, monkeypatch):
    assert cli(capsys, "status") == (0, "backlog: 0 batches, 0 running, 0 shipped, ship not approved\n")
    seen = []
    monkeypatch.setitem(sys.modules, "backlog_run", types.SimpleNamespace(main=lambda argv: seen.append(argv) or 0))
    monkeypatch.setitem(sys.modules, "backlog_ship", types.SimpleNamespace(main=lambda argv: seen.append(argv) or 4))
    assert [bl.main(a) for a in (["start", "B2"], ["wait"], ["answer", "B2", "--file", "a.json"], ["ship", "B2", "merge"])] == [0, 0, 0, 4]
    assert seen == [["start", "B2"], ["wait"], ["answer", "B2", "--file", "a.json"], ["B2", "merge"]]
