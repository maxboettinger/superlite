# tests/scripts/test_backlog_run.py
import json, os, sys, types
from pathlib import Path
import pytest
from backlog_fixtures import APPROVED, Q, batch as b
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402

class Herdr(Exception):
    pass

@pytest.fixture
def bk(tmp_path, monkeypatch):
    root = tmp_path / "main"; (root / ".superlite").mkdir(parents=True)
    ns = types.SimpleNamespace(root=root, sd=root / ".superlite", calls=[], stops={}, states={}, down=False, n=[0], fleets={})
    log = lambda *a: ns.calls.append(a)
    def states():
        if ns.down:
            raise Herdr("unreachable")
        return dict(ns.states)
    def spawn_lead(main_sd, wt, model="opus", env=None, rc=None):
        ns.n[0] += 1; wid = f"W{ns.n[0]}"; ns.states[f"sl-m-{wid}"] = "working"; log("spawn", wt.name)
        return {"id": wid, "name": f"sl-m-{wid}", "account": "c3", "pane_id": "p", "agent": "lead", "model": model, "role": "lead", "lead_sd": str(wt / ".superlite"), "rc": rc}
    def ensure(topic, start):
        wt = root / ".claude" / "worktrees" / f"superlite-{topic}"; (wt / ".superlite").mkdir(parents=True, exist_ok=True); return wt, "created"
    fakes = {"fleet": types.SimpleNamespace(hc=types.SimpleNamespace(agent_states=states, HerdrError=Herdr), main=lambda argv: log("fleet", argv) or 0,
                                            stop=lambda sd, ids=None, all_=False: log("stop", ids)),
             "fleet_state": types.SimpleNamespace(is_on=lambda sd: False, load=lambda sd: ns.fleets.get(str(sd), {"workers": {}}), name_of=lambda sd, wid, w: w.get("name") or wid),
             "fleet_io": types.SimpleNamespace(send_brief=lambda sd, wid, brief, label="": log("send", wid, Path(brief).name, label) or label,
                                               latest_stop=lambda sd, wid, after: ns.stops.get(wid) if ns.stops.get(wid, {}).get("t", -1) >= after else None,
                                               main=lambda argv: log("text", argv) or 0),
             "worktree": types.SimpleNamespace(ensure=ensure, PARENT=".claude/worktrees", bare_flag=lambda start: "", BareCheckout=type("BareCheckout", (Exception,), {}), Taken=type("Taken", (Exception,), {}), BadBranch=type("BadBranch", (Exception,), {})), "fleet_lead": types.SimpleNamespace(spawn_lead=spawn_lead),
             "ship_lock": types.SimpleNamespace(lock_path=lambda repo, home=None: tmp_path / "x.lock", release=lambda p, batch: log("release", batch) or True)}
    if os.environ.get("SUPERLITE_REAL") != "1":
        fakes["backlog_brief"] = types.SimpleNamespace(lead_brief=lambda batch, ctx: f"brief {batch['id']} resume={ctx['resume']}",
                                                      pick_summaries=lambda batch, shipped: ([x["path"] for x in shipped], 0))
    for k, v in fakes.items():
        monkeypatch.setitem(sys.modules, k, v)
    monkeypatch.setattr(br, "_root", lambda: root); monkeypatch.setattr(br, "_now_ms", lambda: 5000)
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: log("run", cmd[:3], Path(cwd).name) or (0, "shipped #201"))
    return ns

def put(bk, *batches, approved=APPROVED):
    bs.update(bs.path(bk.root), lambda d: d.update({"repo": "o/r", "approved_ship": approved, "batches": list(batches)}))

def get(bk, bid):
    return bs.batch(bs.load(bs.path(bk.root)), bid)

def run(capsys, *argv):
    rc = br.main(list(argv)); return rc, capsys.readouterr().out

def running(bk, **kw):
    wt = bk.root / ".claude" / "worktrees" / "superlite-b1-t"; (wt / ".superlite").mkdir(parents=True, exist_ok=True)
    put(bk, b("B1", ["a.py"], "running", lead="W1", agent="sl-m-W1", worktree=str(wt), since=1000, **kw)); bk.states["sl-m-W1"] = "done"
    return wt

def test_start_picks_disjoint_batches_up_to_the_cap(bk, capsys):
    put(bk, b("B1", ["a.py"]), b("B2", ["a.py"]), b("B3", ["c.py"]))
    w1, w3 = bk.root / ".claude" / "worktrees" / "superlite-b1-t", bk.root / ".claude" / "worktrees" / "superlite-b3-t"
    assert run(capsys, "start", "--cap", "2") == (0, f"B1 running lead=W1 worktree={w1}\nB3 running lead=W2 worktree={w3}\n")
    x = get(bk, "B1")
    assert (x["state"], x["agent"], x["branch"], x["since"]) == ("running", "sl-m-W1", "superlite/b1-t", 5000) and get(bk, "B2")["state"] == "planned"
    assert "B1" in (w1 / ".superlite" / "briefs" / "lead.md").read_text() and ("send", "W1", "lead.md", "B1") in bk.calls
    assert ("fleet", ["on", "--plan", str(bk.sd)]) in bk.calls

def test_start_refusals(bk, capsys):
    put(bk, b("B1", ["a.py"]), approved=None)
    assert run(capsys, "start") == (2, "BLOCKED: no ship approval yet (sl backlog decide --print)\n")
    put(bk, b("B1", ["a.py"], "running"), b("B2", ["a.py"]), b("B3", ["c.py"], decisions=[Q]))
    assert run(capsys, "start", "B2", "--cap", "2") == (2, "BLOCKED: B2 shares files with running B1\n")
    assert run(capsys, "start", "B3", "--cap", "2") == (2, "BLOCKED: B3 has open decisions (sl backlog decide --print)\n")
    bk.down = True
    assert run(capsys, "start")[0] == 3 and not any(c[0] == "spawn" for c in bk.calls)

def test_start_resumes_a_parked_batch_and_survives_a_blocked_spawn(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"], "parked", reason="tui red", worktree=str(bk.root / ".claude" / "worktrees" / "superlite-b1-t")), b("B2", ["b.py"]))
    assert run(capsys, "start", "B1")[0] == 0 and get(bk, "B1")["state"] == "running"
    brief = (bk.root / ".claude" / "worktrees" / "superlite-b1-t" / ".superlite" / "briefs" / "lead.md").read_text()
    assert "resume=True" in brief or "Resume: this batch was parked (tui red)" in brief
    def boom(*a, **k):
        print("BLOCKED: no account with headroom"); raise SystemExit(3)
    monkeypatch.setattr(sys.modules["fleet_lead"], "spawn_lead", boom)
    assert run(capsys, "start", "B2")[0] == 2 and get(bk, "B2")["state"] == "planned"

def test_wait_needs_decision_or_invalid_question(bk, capsys):
    wt = running(bk); q = wt / ".superlite" / "question.json"; q.write_text(json.dumps(Q)); bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, f"B1 needs_decision question={q}\n")
    assert get(bk, "B1")["state"] == "needs_decision" and not any(c[0] == "stop" for c in bk.calls)
    running(bk, question_reprompted=True); q.write_text('{"questions": []}')
    assert run(capsys, "wait", "--timeout", "0")[1] == "B1 parked: invalid question.json: questions: 1 to 4 entries\n"

def test_wait_ships_stops_the_lead_and_cleans_up(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8"); bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    assert run(capsys, "wait", "--timeout", "0")[1] == f"B1 shipped PR #201 1.5.8 summary={bk.sd / 'backlog' / 'B1.md'}\n"
    assert ("stop", ["W1"]) in bk.calls and ("run", ["maxapp", "ship", "-C"], "main") in bk.calls and get(bk, "B1")["state"] == "shipped"

def test_wait_parks_a_blocked_or_gone_lead_and_releases_the_lock(bk, capsys):
    running(bk); bk.stops["W1"] = {"t": 2000, "last": "Status: BLOCKED - tui red"}
    assert run(capsys, "wait", "--timeout", "0")[1] == "B1 parked: Status: BLOCKED - tui red\n"
    assert ("release", "B1") in bk.calls and ("stop", ["W1"]) in bk.calls and get(bk, "B1")["reason"] == "Status: BLOCKED - tui red"
    running(bk); bk.stops.clear(); bk.states.clear()
    assert run(capsys, "wait", "--timeout", "0")[1] == "B1 parked: lead pane gone\n"

def test_wait_ignores_old_stops_and_herdr_outages(bk, capsys):
    running(bk); bk.stops["W1"] = {"t": 500, "last": "Status: DONE"}; bk.states["sl-m-W1"] = "working"
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    bk.down = True; bk.states.clear()
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n") and get(bk, "B1")["state"] == "running"
    put(bk, b("B1", ["a.py"]))
    assert run(capsys, "wait", "--timeout", "0") == (0, "no running batch\n")

def test_answer_sends_the_file_and_resumes_the_lead(bk, capsys, tmp_path):
    wt = running(bk); waiting = lambda: bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "needs_decision"}))
    waiting(); (wt / ".superlite" / "question.json").write_text(json.dumps(Q))
    f = tmp_path / "a.json"; f.write_text(json.dumps({"answers": {"Keep the v1 API?": "Drop"}, "by": "user"})); ans = wt / ".superlite" / "answer-1.json"
    assert run(capsys, "answer", "B1", "--file", str(f)) == (0, "B1 answered: answer-1.json sent to W1\n")
    assert json.loads(ans.read_text()) == {"answers": {"Keep the v1 API?": "Drop"}, "by": {"Keep the v1 API?": "user"}} and (wt / ".superlite" / "question-1.json").exists()
    text = next(c[1] for c in bk.calls if c[0] == "text")
    assert text[:3] == ["send", "W1", "--text"] and str(ans) in text[3] and text[4:] == ["--plan", str(bk.sd)]
    x = get(bk, "B1")
    assert (x["state"], x["since"], x["questions"], x["answers"]) == ("running", 5000, 1, {"Keep the v1 API?": "Drop"})
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 2
    waiting(); f.write_text(json.dumps({"answers": {"K?": "x\x1b[2J"}, "by": "user"}))
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 2

def test_start_passes_summary_paths_not_contents(bk, capsys, monkeypatch):
    seen = []
    monkeypatch.setitem(sys.modules, "backlog_brief", types.SimpleNamespace(lead_brief=lambda batch, ctx: seen.append(ctx["summaries"]) or "brief", pick_summaries=lambda batch, shipped: ([x["path"] for x in shipped], 0)))
    f = bk.sd / "backlog" / "B1.md"; f.parent.mkdir(parents=True); f.write_text("# ruling text\nbody")
    put(bk, b("B1", ["a.py"], "shipped"), b("B2", ["c.py"]))
    assert run(capsys, "start")[0] == 0 and seen == [[str(f)]]

def test_wait_parks_on_a_deeply_nested_question_json(bk, capsys):
    wt = running(bk, question_reprompted=True); bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    (wt / ".superlite" / "question.json").write_text("[" * 200000 + "]" * 200000)
    rc, out = run(capsys, "wait", "--timeout", "0")
    assert rc == 0 and out.startswith("B1 parked: invalid question.json") and get(bk, "B1")["state"] == "parked"

def test_wait_reports_a_batch_its_lead_parked_once_and_stops_the_lead(bk, capsys):
    running(bk); bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "parked", "reason": "release --park: tui red"}))
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: release --park: tui red\n")
    assert ("stop", ["W1"]) in bk.calls and ("release", "B1") in bk.calls
    bk.states.clear()
    assert run(capsys, "wait", "--timeout", "0") == (0, "no running batch\n")

def test_start_never_spawns_a_second_lead_while_the_first_pane_lives(bk, capsys):
    running(bk); bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "parked", "reason": "x"}))
    rc, out = run(capsys, "start", "B1")
    assert rc == 2 and "still running" in out and not any(c[0] == "spawn" for c in bk.calls)
    bk.states.clear()
    assert run(capsys, "start", "B1")[0] == 0 and any(c[0] == "spawn" for c in bk.calls)

def test_a_batch_main_parked_starts_only_by_name_and_fresh(bk, capsys):
    put(bk, b("B1", ["a.py"], "parked", reason="hold", parked_by="main"))
    assert run(capsys, "start", "--cap", "2") == (0, "no startable batch\n")
    assert run(capsys, "start", "B1")[0] == 0 and get(bk, "B1")["state"] == "running"
    brief = (bk.root / ".claude" / "worktrees" / "superlite-b1-t" / ".superlite" / "briefs" / "lead.md").read_text()
    assert ("resume=False" in brief) if brief.startswith("brief ") else ("Resume" not in brief)

def test_wait_names_issues_the_merge_left_open(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8", open_issues=[1, 9]); bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    assert run(capsys, "wait", "--timeout", "0")[1] == f"B1 shipped PR #201 1.5.8 summary={bk.sd / 'backlog' / 'B1.md'}\nB1 OPEN #1 #9\n"

def git(replies):
    return lambda cmd, cwd: next((r for p, r in replies.items() if " ".join(cmd).startswith(p)), (0, ""))

GIT = {"git symbolic-ref": (0, "origin/main"), "git log": (0, "abc1234 T1 ship guard\ndef5678 T0 stubs"), "git status": (0, "M skills/x.py\n?? tests/y.py")}

def parked(bk, **kw):
    wt = bk.root / ".claude" / "worktrees" / "superlite-b1-t"; (wt / ".superlite").mkdir(parents=True, exist_ok=True)
    put(bk, b("B1", ["a.py"], "parked", reason="lead pane gone", lead="W7", agent="sl-m-W7", worktree=str(wt), **kw))
    return wt

def brief_of(wt):
    return (wt / ".superlite" / "briefs" / "lead.md").read_text()

def test_start_after_a_crash_briefs_the_worktree_state_and_the_answers(bk, capsys, monkeypatch):
    wt = parked(bk, questions=1, answers={"Keep the v1 API?": "Drop"}); (wt / ".superlite" / "answer-1.json").write_text("{}")
    calls = []
    monkeypatch.setattr(br, "_run", lambda cmd, cwd: calls.append((cmd[0], Path(cwd))) or git(GIT)(cmd, cwd))
    assert run(capsys, "start", "B1")[0] == 0
    text = brief_of(wt)
    assert ("Previous lead W7: parked (lead pane gone); its work stays in this worktree. Read it before you plan; "
            "keep, finish or drop each part on purpose:\n") in text
    assert "- Commits on superlite/b1-t not on origin/main: 2: abc1234 T1 ship guard; def5678 T0 stubs\n" in text
    assert "- Uncommitted files: 2: M skills/x.py, ?? tests/y.py\n" in text
    assert "- Answers given mid-run: answer-1.json in .superlite/ (also under Max's decisions or main's rulings above; each file's by names who answered; never ask them again)\n" in text
    assert calls and all(cwd == wt for c, cwd in calls if c == "git")

def test_start_after_a_crash_caps_the_lists_and_names_git_failures(bk, capsys, monkeypatch):
    wt = parked(bk)
    log = "\n".join(f"c{i:06d} subject {i}" for i in range(7)); st = "\n".join(f"?? f{i}.py" for i in range(12))
    monkeypatch.setattr(br, "_run", git({"git symbolic-ref": (128, "fatal: no ref"), "git log": (0, log), "git status": (0, st)}))
    assert run(capsys, "start", "B1")[0] == 0
    text = brief_of(wt)
    assert ("- Commits on superlite/b1-t not on origin/main: 7: c000000 subject 0; c000001 subject 1; c000002 subject 2; "
            "c000003 subject 3; c000004 subject 4 (+2 more)\n") in text
    assert "- Uncommitted files: 12: " + ", ".join(f"?? f{i}.py" for i in range(10)) + " (+2 more)\n" in text
    assert "Answers Max gave" not in text
    parked(bk); monkeypatch.setattr(br, "_run", git({"git log": (128, "fatal: bad revision"), "git status": (0, "")}))
    assert run(capsys, "start", "B1")[0] == 0
    text = brief_of(wt)
    assert "- Commits on superlite/b1-t not on origin/main: unknown (git log failed)\n" in text and "- Uncommitted files: 0\n" in text

def test_start_after_a_crash_strips_control_characters(bk, capsys, monkeypatch):
    wt = parked(bk)
    monkeypatch.setattr(br, "_run", git({"git log": (0, "abc1234 evil\x1b[2J subject"), "git status": (0, "?? a\x07.py")}))
    assert run(capsys, "start", "B1")[0] == 0
    text = brief_of(wt)
    assert "\x1b" not in text and "\x07" not in text and "abc1234 evil?[2J subject" in text and "?? a?.py" in text

def test_a_fresh_start_gets_no_worktree_state(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"])); monkeypatch.setattr(br, "_run", git(GIT))
    assert run(capsys, "start", "B1")[0] == 0
    assert "Previous lead" not in brief_of(bk.root / ".claude" / "worktrees" / "superlite-b1-t")

def fleet_of(bk, wt, **workers):
    bk.fleets[str(wt / ".superlite")] = {"workers": workers}

def test_wait_flags_vanished_worker_panes_of_a_live_lead_once(bk, capsys, monkeypatch):
    wt = running(bk); bk.states.update({"sl-m-W1": "working", "sl-l-w3": "working"})
    fleet_of(bk, wt, W2={"name": "sl-l-w2", "state": "busy"}, W3={"name": "sl-l-w3", "state": "busy"},
             W4={"name": "sl-l-w4", "state": "stopped"}, W5={"name": "sl-l-w5", "state": "busy", "role": "layer"},
             W6={"name": "sl-l-w6", "state": "starting"}, W7={"name": "sl-l-w7", "state": "ready"})
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert get(bk, "B1")["gone_seen"] == {"W2": 5000, "W7": 5000} and not any(c[0] == "text" for c in bk.calls)
    monkeypatch.setattr(br, "_now_ms", lambda: 5000 + br.GONE_MS)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 worker panes gone: W2 W7; lead W1 told\n")
    text = next(c[1] for c in bk.calls if c[0] == "text")
    assert text[:3] == ["send", "W1", "--text"] and "fleet stop W2 W7 --plan .superlite" in text[3] and text[4:] == ["--plan", str(bk.sd)]
    x = get(bk, "B1")
    assert (x["gone_workers"], x["gone_seen"], x["state"]) == (["W2", "W7"], {}, "running")
    bk.calls.clear()
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n") and not any(c[0] == "text" for c in bk.calls)

def test_wait_forgets_a_worker_pane_that_comes_back_and_skips_herdr_outages(bk, capsys, monkeypatch):
    wt = running(bk); bk.states["sl-m-W1"] = "working"
    fleet_of(bk, wt, W2={"name": "sl-l-w2", "state": "busy"})
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n") and get(bk, "B1")["gone_seen"] == {"W2": 5000}
    bk.states["sl-l-w2"] = "working"; monkeypatch.setattr(br, "_now_ms", lambda: 5000 + br.GONE_MS)
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n") and get(bk, "B1")["gone_seen"] == {}
    del bk.states["sl-l-w2"]; bk.down = True
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n") and get(bk, "B1")["gone_seen"] == {}

def test_wait_names_a_lead_it_could_not_tell(bk, capsys, monkeypatch):
    wt = running(bk, gone_seen={"W2": 0}); bk.states["sl-m-W1"] = "working"
    fleet_of(bk, wt, W2={"name": "sl-l-w2", "state": "busy"})
    monkeypatch.setattr(br, "_now_ms", lambda: br.GONE_MS); monkeypatch.setattr(sys.modules["fleet_io"], "main", lambda argv: 1)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 worker panes gone: W2; lead W1 not told (send failed)\n")
    assert get(bk, "B1")["gone_workers"] == ["W2"]

def test_start_clears_the_gone_worker_marks(bk, capsys):
    parked(bk, gone_seen={"W2": 1}, gone_workers=["W3"])
    assert run(capsys, "start", "B1")[0] == 0
    x = get(bk, "B1"); assert (x["gone_seen"], x["gone_workers"]) == ({}, [])


def test_start_after_a_crash_cleans_the_park_reason_in_the_header(bk, capsys, monkeypatch):
    wt = parked(bk); put(bk, b("B1", ["a.py"], "parked", reason="lead\x1b[2J pane\ngone", lead="W7", agent="sl-m-W7", worktree=str(wt)))
    monkeypatch.setattr(br, "_run", git(GIT))
    assert run(capsys, "start", "B1")[0] == 0
    text = brief_of(wt)
    assert "\x1b" not in text and "Previous lead W7: parked (lead?[2J pane gone);" in text

def test_wait_open_line_jira_key(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8", open_issues=["PIX-9"]); bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    assert run(capsys, "wait", "--timeout", "0")[1].endswith("B1 OPEN PIX-9\n")
