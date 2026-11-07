import copy
import json
import sys

from test_backlog_run import bk, put, get, run, running  # noqa: F401
from backlog_fixtures import Q, batch as b


def qfile(wt, obj):
    p = wt / ".superlite" / "question.json"
    p.write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return p


def texts(bk):
    return [c for c in bk.calls if c[0] == "text"]


def test_wait_cuts_header_and_label_and_names_each_cut(bk, capsys):
    wt = running(bk)
    obj = copy.deepcopy(Q)
    obj["questions"][0]["header"] = "Compatibility"
    obj["questions"][0]["options"][0]["label"] = "k" * 70 + " (Recommended)"
    q = qfile(wt, obj)
    bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, f'B1 needs_decision question={q}\n'
        'B1 shortened: "Keep the v1 API?" header: 13 -> 12 characters\n'
        'B1 shortened: "Keep the v1 API?" option 1 label: 84 -> 60 characters\n')
    assert get(bk, "B1")["state"] == "needs_decision" and json.loads(q.read_text()) == obj
    assert not texts(bk) and not any(c[0] == "stop" for c in bk.calls)


def test_wait_sends_an_over_long_question_back_once(bk, capsys):
    wt = running(bk)
    bad = copy.deepcopy(Q)
    bad["questions"][0]["question"] = "a" * 320
    q = qfile(wt, bad)
    bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    x = get(bk, "B1")
    assert x["state"] == "running" and x["question_reprompted"] is True and x["since"] == 5000
    assert len(texts(bk)) == 1
    t = texts(bk)[0][1]
    assert t[:3] == ["send", "W1", "--text"] and t[4:] == ["--plan", str(bk.sd)]
    assert "q1 question: 1 to 300 characters" in t[3] and "1 to 12" in t[3] and "Status: NEEDS_DECISION" in t[3]
    assert not any(c[0] in ("stop", "release") for c in bk.calls)
    qfile(wt, Q)
    bk.stops["W1"] = {"t": 6000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, f"B1 needs_decision question={q}\n")


def test_wait_parks_on_the_second_invalid_file(bk, capsys):
    wt = running(bk)
    qfile(wt, {"questions": []})
    bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    qfile(wt, {"questions": []})
    bk.stops["W1"] = {"t": 6000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: invalid question.json: questions: 1 to 4 entries\n")
    assert ("stop", ["W1"]) in bk.calls and ("release", "B1") in bk.calls and len(texts(bk)) == 1


def test_wait_parks_when_the_question_fix_cannot_be_sent(bk, capsys):
    wt = running(bk)
    bad = copy.deepcopy(Q)
    bad["questions"][0]["question"] = "a" * 320
    qfile(wt, bad)
    bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    sys.modules["fleet_io"].main = lambda argv: 1
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: invalid question.json: q1 question: 1 to 300 characters\n")


def test_wait_not_json_is_sent_back_then_parks(bk, capsys):
    wt = running(bk)
    qfile(wt, "{")
    bk.stops["W1"] = {"t": 2000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "TIMEOUT\n")
    assert "not JSON" in texts(bk)[0][1][3]
    qfile(wt, "{")
    bk.stops["W1"] = {"t": 6000, "last": "Status: NEEDS_DECISION"}
    assert run(capsys, "wait", "--timeout", "0") == (0, "B1 parked: invalid question.json: not JSON\n")


def test_start_and_answer_reset_the_question_reprompt(bk, capsys, tmp_path):
    wt = running(bk, question_reprompted=True)
    from test_backlog_run import bs
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "needs_decision"}))
    qfile(wt, Q)
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"answers": {"Keep the v1 API?": "Drop"}}))
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 0
    assert get(bk, "B1")["question_reprompted"] is False
    put(bk, b("B2", ["b.py"], question_reprompted=True))
    assert run(capsys, "start", "B2")[0] == 0
    assert get(bk, "B2")["question_reprompted"] is False
