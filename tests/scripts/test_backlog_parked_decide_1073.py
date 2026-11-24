import json
from test_backlog_cli import bk, cli  # noqa: F401
from backlog_fixtures import batch, Q
import backlog_state as bs

QT = "B2: Keep the v1 API?"


def _set(bk, *batches):
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": list(batches), "approved_ship": {"by": "AskUserQuestion", "time": "t"}}))


def _parked(**kw):
    return batch("B2", ["a.py"], "parked", questions=1, decisions=[Q], **kw)


def test_open_questions_list_a_parked_batch():
    d = {"batches": [_parked()], "approved_ship": {"by": "AskUserQuestion", "time": "t"}}
    assert [q["question"] for q in bs.open_questions(d)] == [QT]


def test_open_questions_skip_running_and_shipped():
    bs_ = [batch("B3", ["a.py"], s, questions=1, decisions=[Q]) for s in ("running", "shipped")]
    assert bs.open_questions({"batches": bs_, "approved_ship": {"by": "x", "time": "t"}}) == []


def test_decide_file_answers_a_parked_batch(bk, capsys, tmp_path):
    _set(bk, _parked())
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"answers": {QT: "Drop"}, "by": "user"}))
    rc, out = cli(capsys, "decide", "--file", str(f))
    b = bs.batch(bs.load(bs.path(bk.root)), "B2")
    assert rc == 0, out
    assert b["answers"]["Keep the v1 API?"] == "Drop" and bs._unanswered(b) == [] and b["state"] == "parked"


def test_decide_print_lists_a_parked_batch(bk, capsys):
    _set(bk, _parked())
    rc, out = cli(capsys, "decide", "--print")
    assert rc == 0 and QT in [q["question"] for q in json.loads(out)["questions"]]


def test_decide_print_batch_falls_back_to_plan_questions(bk, capsys):
    _set(bk, _parked())
    rc, out = cli(capsys, "decide", "--print", "--batch", "B2")
    assert rc == 0 and json.loads(out)["questions"][0]["question"] == QT


def test_decide_print_batch_prefers_question_json(bk, capsys, tmp_path):
    wt = tmp_path / "wt"
    (wt / ".superlite").mkdir(parents=True)
    q = {"questions": [{**Q["questions"][0], "question": "Own lead question?"}]}
    (wt / ".superlite" / "question.json").write_text(json.dumps(q))
    _set(bk, _parked(worktree=str(wt)))
    rc, out = cli(capsys, "decide", "--print", "--batch", "B2")
    assert rc == 0 and [x["question"] for x in json.loads(out)["questions"]] == ["Own lead question?"]


def test_decide_print_batch_without_questions(bk, capsys):
    _set(bk, batch("B2", ["a.py"], "parked"))
    assert cli(capsys, "decide", "--print", "--batch", "B2") == (0, "B2 has no open question\n")


def test_decide_print_batch_prefix_does_not_match_b10(bk, capsys):
    _set(bk, batch("B1", ["a.py"], "parked"), batch("B10", ["b.py"], "parked", questions=1, decisions=[Q]))
    assert cli(capsys, "decide", "--print", "--batch", "B1") == (0, "B1 has no open question\n")
