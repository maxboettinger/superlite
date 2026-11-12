import json
import pytest
from backlog_fixtures import Q, batch as b
from test_backlog_run import bk, put, get, run, running, bs  # noqa: F401

TELL = "superlite: main says (sl backlog tell): "


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)


def texts(bk):
    return [c[1] for c in bk.calls if c[0] == "text"]


def test_shipped_line_carries_followups(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8", followups=["file docs", "fix x"], undone=["run migration"])
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    s = bk.sd / "backlog" / "B1.md"
    assert run(capsys, "wait", "--timeout", "0") == (0, f"B1 shipped PR #201 1.5.8 summary={s} followups=2 undone=1\n"
                                                       "B1 follow-up: file docs\nB1 follow-up: fix x\nB1 left undone: run migration\n")


def test_shipped_line_unchanged_without_followups(bk, capsys):
    running(bk, merged=True, pr=201, version="1.5.8")
    bk.stops["W1"] = {"t": 2000, "last": "Status: DONE"}
    assert run(capsys, "wait", "--timeout", "0")[1] == f"B1 shipped PR #201 1.5.8 summary={bk.sd / 'backlog' / 'B1.md'}\n"


def test_tell_sends_to_the_lead(bk, capsys):
    running(bk)
    before = dict(get(bk, "B1"))
    assert run(capsys, "tell", "B1", "--text", "rebase first") == (0, "B1 told lead W1\n")
    assert texts(bk) == [["send", "W1", "--text", TELL + "rebase first", "--plan", str(bk.sd)]]
    x = get(bk, "B1")
    assert (x["state"], x["since"]) == (before["state"], before["since"])


def test_tell_refusals(bk, capsys, monkeypatch):
    put(bk, b("B1", ["a.py"]))
    assert run(capsys, "tell", "B9", "--text", "x") == (2, "BLOCKED: unknown batch B9\n")
    assert run(capsys, "tell", "B1", "--text", "x") == (2, "BLOCKED: B1 is planned; only a running batch has a lead to tell\n")
    put(bk, b("B1", ["a.py"], "needs_decision", lead="W1"))
    assert run(capsys, "tell", "B1", "--text", "x") == (2, "BLOCKED: B1 waits for an answer: sl backlog answer B1 --file F\n")
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W1")
    assert run(capsys, "tell", "B1", "--text", "x") == (2, "BLOCKED: sl backlog tell runs only in the main session\n")
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER")
    assert texts(bk) == []
    running(bk)
    import sys
    monkeypatch.setattr(sys.modules["fleet_io"], "main", lambda argv: 1)
    assert run(capsys, "tell", "B1", "--text", "x") == (3, "BLOCKED: B1 lead W1 not told (fleet send failed)\n")


def test_tell_text_limits(bk, capsys):
    running(bk)
    assert run(capsys, "tell", "B1", "--text", "a" * 2000)[0] == 0
    assert run(capsys, "tell", "B1", "--text", "a\nb")[0] == 0
    n = len(texts(bk))
    bad = "BLOCKED: --text: 1 to 2000 characters, no control characters\n"
    for t in ("a" * 2001, "  ", "x\x1b[2J"):
        assert run(capsys, "tell", "B1", "--text", t) == (2, bad)
    assert len(texts(bk)) == n


def answer_file(tmp_path, **kw):
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"answers": {"Keep the v1 API?": "Drop"}, "by": "user", **kw}))
    return f


def test_answer_records_by(bk, capsys, tmp_path):
    wt = running(bk)
    waiting = lambda: bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "needs_decision"}))
    waiting()
    (wt / ".superlite" / "question.json").write_text(json.dumps(Q))
    assert run(capsys, "answer", "B1", "--file", str(answer_file(tmp_path, by="main")))[0] == 0
    assert json.loads((wt / ".superlite" / "answer-1.json").read_text()) == {
        "answers": {"Keep the v1 API?": "Drop"}, "by": {"Keep the v1 API?": "main"}}
    assert get(bk, "B1")["answered_by"] == {"Keep the v1 API?": "main"}
    assert texts(bk)[-1][3].startswith("Main answered your question as AI orchestrator, not Max: read ")
    waiting()
    assert run(capsys, "answer", "B1", "--file", str(answer_file(tmp_path)))[0] == 0
    assert texts(bk)[-1][3].startswith("Max answered your question: read ")
    assert get(bk, "B1")["answered_by"] == {"Keep the v1 API?": "user"}
    waiting()
    assert run(capsys, "answer", "B1", "--file", str(answer_file(tmp_path, by="bot")))[0] == 2
