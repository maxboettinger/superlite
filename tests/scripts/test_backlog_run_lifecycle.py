# tests/scripts/test_backlog_run_lifecycle.py
import json, sys
from backlog_fixtures import batch as b, Q
from test_backlog_run import bk, put, get, run, running  # noqa: F401


def test_start_takes_several_ids_and_reports_each_refusal(bk, capsys):
    put(bk, b("B1", ["a.py"]), b("B2", ["a.py"]), b("B3", ["c.py"]), b("B4", ["d.py"], depends=["B1"]))
    r = bk.root / "wts"
    assert run(capsys, "start", "B1", "B2", "B4", "B3", "--cap", "3") == (2, "BLOCKED: B2 shares files with running B1\nBLOCKED: B4 waits for B1\n"
        f"B1 running lead=W1 worktree={r}/superlite-b1-t\nB3 running lead=W2 worktree={r}/superlite-b3-t\n")
    assert get(bk, "B1")["state"] == get(bk, "B3")["state"] == "running"
    assert get(bk, "B2")["state"] == get(bk, "B4")["state"] == "planned"


def test_start_counts_batches_of_the_same_call_against_the_cap(bk, capsys):
    put(bk, b("B1", ["a.py"]), b("B2", ["b.py"]), b("B3", ["c.py"]))
    rc, out = run(capsys, "start", "B1", "B2", "B3")
    assert rc == 2 and out.splitlines()[0] == "BLOCKED: no free slot for B3 (cap 2)"
    assert get(bk, "B1")["state"] == get(bk, "B2")["state"] == "running" and get(bk, "B3")["state"] == "planned"
    put(bk, b("B5", ["e.py"]))
    n = sum(1 for c in bk.calls if c[0] == "spawn")
    rc, out = run(capsys, "start", "B5", "B5")
    assert rc == 0 and out.count("B5 running") == 1 and sum(1 for c in bk.calls if c[0] == "spawn") == n + 1


def test_a_live_lead_refuses_only_its_own_batch(bk, capsys):
    put(bk, b("B1", ["a.py"], "parked", reason="x", lead="W9", agent="sl-m-W9", worktree=str(bk.root / "wts" / "superlite-b1-t")), b("B2", ["b.py"]))
    bk.states["sl-m-W9"] = "working"
    rc, out = run(capsys, "start", "B1", "B2")
    lines = out.splitlines()
    assert rc == 2 and lines[0] == "BLOCKED: B1 lead W9 is still running (sl backlog wait)" and lines[1].startswith("B2 running lead=")
    assert get(bk, "B1")["state"] == "parked"


def test_start_keeps_a_started_batch_when_a_later_spawn_blocks(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"]), b("B2", ["b.py"]))
    real = sys.modules["fleet_lead"].spawn_lead
    n = [0]

    def spawn(*a, **k):
        n[0] += 1
        if n[0] == 1:
            return real(*a, **k)
        print("BLOCKED: no account with headroom")
        raise SystemExit(3)
    monkeypatch.setattr(sys.modules["fleet_lead"], "spawn_lead", spawn)
    assert run(capsys, "start", "B1", "B2")[0] == 3
    assert get(bk, "B1")["state"] == "running" and get(bk, "B2")["state"] == "planned"


def test_wait_reprompts_a_lead_whose_stop_holds_no_status_once(bk, capsys):
    running(bk); bk.stops["W1"] = {"t": 2000, "last": "PONG"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    x = get(bk, "B1")
    assert x["state"] == "running" and x["reprompted"] is True and x["since"] == 5000
    texts = [c[1] for c in bk.calls if c[0] == "text"]
    assert len(texts) == 1 and texts[0][:3] == ["send", "W1", "--text"] and "Status:" in texts[0][3] and texts[0][4:] == ["--plan", str(bk.sd)]
    assert not any(c[0] in ("stop", "release") for c in bk.calls)
    bk.stops["W1"] = {"t": 6000, "last": "PONG again"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: no status in stop text: PONG again\n")
    assert get(bk, "B1")["reason"] == "no status in stop text: PONG again"
    assert ("release", "B1") in bk.calls and ("stop", ["W1"]) in bk.calls


def test_wait_reads_the_status_from_the_transcript(bk, capsys, monkeypatch):
    running(bk)
    bk.stops["W1"] = {"t": 2000, "last": "Outcome: BLOCKED, tui layer red", "transcript": "/x/t.jsonl"}
    monkeypatch.setattr(sys.modules["fleet_io"], "report_text", lambda t: "Outcome: BLOCKED, tui layer red\n\nStatus: BLOCKED", raising=False)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: Outcome: BLOCKED, tui layer red\n")
    assert not any(c[0] == "text" for c in bk.calls)


def test_needs_decision_without_a_question_parks_at_once(bk, capsys):
    running(bk); bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: Status: NEEDS_DECISION\n")


def test_a_failed_reprompt_send_parks_with_a_readable_reason(bk, capsys, monkeypatch):
    running(bk); bk.stops["W1"] = {"t": 2000, "last": ""}
    monkeypatch.setattr(sys.modules["fleet_io"], "main", lambda argv: 1)
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: no status in stop text: -\n")


def test_answer_and_start_reset_the_reprompt(bk, capsys, tmp_path):
    wt = running(bk, reprompted=True)
    bs_update = sys.modules["backlog_state"].update
    bs_update(sys.modules["backlog_state"].path(bk.root), lambda d: sys.modules["backlog_state"].batch(d, "B1").update({"state": "needs_decision"}))
    (wt / ".superlite" / "question.json").write_text(json.dumps(Q))
    f = tmp_path / "a.json"; f.write_text(json.dumps({"answers": {"Keep the v1 API?": "Drop"}}))
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 0 and get(bk, "B1")["reprompted"] is False
    put(bk, b("B2", ["b.py"], reprompted=True))
    assert run(capsys, "start", "B2")[0] == 0 and get(bk, "B2")["reprompted"] is False
