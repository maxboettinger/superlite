import copy, json
from pathlib import Path
from test_backlog_cli import bk, cli, BATCH  # noqa: F401
from backlog_fixtures import Q, batch
import backlog as bl
import backlog_state as bs

REC = " (Recommended)"
ROOT = Path(__file__).resolve().parents[2]


def _put(bk, tmp_path, q):
    wt = tmp_path / "wt"
    (wt / ".superlite").mkdir(parents=True, exist_ok=True)
    f = wt / ".superlite" / "question.json"
    f.write_text(json.dumps(q))
    bs.update(bs.path(bk.root), lambda d: d.update({"batches": [batch("B1", ["a.py"], "needs_decision", worktree=str(wt))]}))
    return f


def _q():
    q = copy.deepcopy(Q)
    q["questions"][0]["header"] = "Compatibility"
    q["questions"][0]["options"][0]["label"] = "k" * 70 + REC
    q["questions"][0]["options"][1]["description"] = "y" * 250
    return q


def test_decide_batch_cuts_and_names_cuts_on_stderr(bk, tmp_path, capsys):
    f = _put(bk, tmp_path, _q())
    before = f.read_text()
    rc = bl.main(["decide", "--print", "--batch", "B1"])
    cap = capsys.readouterr()
    want = copy.deepcopy(Q)
    want["questions"][0]["header"] = "Compatibilit"
    want["questions"][0]["options"][0]["label"] = "k" * 46 + REC
    want["questions"][0]["options"][1]["description"] = "y" * 200
    assert rc == 0 and json.loads(cap.out) == want
    assert cap.err == ('shortened: "Keep the v1 API?" header: 13 -> 12 characters\n'
                       'shortened: "Keep the v1 API?" option 1 label: 84 -> 60 characters\n'
                       'shortened: "Keep the v1 API?" option 2 description: 250 -> 200 characters\n')
    assert f.read_text() == before


def test_decide_batch_valid_file_prints_no_cut_lines(bk, tmp_path, capsys):
    _put(bk, tmp_path, Q)
    assert bl.main(["decide", "--print", "--batch", "B1"]) == 0
    cap = capsys.readouterr()
    assert json.loads(cap.out) == Q and cap.err == ""


def test_decide_batch_still_refuses_an_over_long_question(bk, tmp_path, capsys):
    q = copy.deepcopy(Q)
    q["questions"][0]["question"] = "a" * 301
    _put(bk, tmp_path, q)
    rc = bl.main(["decide", "--print", "--batch", "B1"])
    assert rc == 3 and capsys.readouterr().out == "BLOCKED: B1 question.json invalid: q1 question: 1 to 300 characters\n"


def test_decide_batch_caps_cut_lines_at_five(bk, tmp_path, capsys):
    qs = []
    for n in range(1, 5):
        qs.append({"question": f"Q{n}?", "header": "Compatibility", "multiSelect": False,
                   "options": [{"label": "k" * 70, "description": "a"}, {"label": "Drop", "description": "b"}]})
    _put(bk, tmp_path, {"questions": qs})
    assert bl.main(["decide", "--print", "--batch", "B1"]) == 0
    lines = capsys.readouterr().err.splitlines()
    assert len(lines) == 6 and lines[-1] == "shortened: 3 more"


def test_plan_cut_lines_unchanged(bk, capsys):
    dec = {"questions": [{"question": "Which store?", "header": "Dependencies!",
                          "options": [{"label": "Keep", "description": "a"}, {"label": "Drop", "description": "b"}]}]}
    bk.batches = [{**BATCH, "decisions": [dec]}]
    rc, out = cli(capsys, "plan")
    assert rc == 0 and 'shortened: "Which store?" header: 13 -> 12 characters' in out


def test_command_step5_names_decide_batch_and_the_send_back():
    t = (ROOT / "commands" / "backlog.md").read_text()
    for s in ('"$SL" backlog decide --print --batch B', "shortened:", "invalid question.json", "rewrite"):
        assert s in t
    assert t.index("decide --print --batch B") < t.index('"$SL" backlog answer B --file F')


def test_decide_batch_deeply_nested_file_blocks_without_raising(bk, tmp_path, capsys):
    f = _put(bk, tmp_path, Q)
    f.write_text("[" * 100000 + "]" * 100000)
    assert bl.main(["decide", "--print", "--batch", "B1"]) == 3
    assert capsys.readouterr().out.startswith("BLOCKED: B1 question.json unreadable")
