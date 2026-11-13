# tests/scripts/test_backlog_steps_answer_674.py
import copy
import json
import sys
from backlog_fixtures import batch as mk
from test_backlog_run import bk, run, running, put, get  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_answer as ba  # noqa: E402
import backlog_run as br  # noqa: E402
import backlog_state as bs  # noqa: E402
import backlog as bl  # noqa: E402

QT = "Store assets?"
STEP = {"runs": "main", "command": "git lfs install"}
OPTS = [{"label": "Git LFS (Recommended)", "description": "main installs git-lfs", **STEP}, {"label": "Plain git", "description": "no tool"}]
QS = {"B1: " + QT: {"question": "B1: " + QT, "options": OPTS}}


def test_answer_steps_examples():
    k = "B1: " + QT
    assert ba.answer_steps({"answers": {k: "Git LFS"}}, {k: "Git LFS"}, QS) == ({k: STEP}, "")
    s = {"runs": "user", "command": "gh auth login", "why": "sign in"}
    assert ba.answer_steps({"answers": {"Q": "own text"}, "steps": {"Q": s}}, {"Q": "own text"}, {}) == ({"Q": s}, "")
    assert ba.answer_steps({"answers": {"Q": "x"}, "steps": {"Other": {"runs": "main", "command": "c"}}}, {"Q": "x"}, {}) == (
        {}, "steps: Other is not answered in this file")


def test_answer_steps_bad_map():
    assert ba.answer_steps({"steps": "x"}, {"Q": "x"}, {}) == ({}, "steps: an object {question: {runs, command, why}}")
    assert ba.answer_steps({"steps": {"Q": {"runs": "lead", "command": "c"}}}, {"Q": "x"}, {}) == ({}, "steps Q runs: main or user")


def test_option_step_with_note():
    k = "B1: " + QT
    assert ba.answer_steps({}, {k: "Git LFS; note: fine"}, QS) == ({k: STEP}, "")


def test_add_steps():
    b = {"id": "B1"}
    assert ba.add_steps(b, {QT: dict(STEP)}) == 1
    assert b["main_steps"] == [{**STEP, "question": QT}]
    assert ba.add_steps(b, {"Again?": dict(STEP)}) == 0


def test_steps_text():
    assert ba.steps_text({"Q": STEP}) == ("Steps for main or Max (never run one yourself; write each you cannot see done as one "
                                          "`Left undone: main runs this: <command>` line into .superlite/notes.md now): main runs this: git lfs install.")
    assert ba.steps_text({}) == ""


def cli(capsys, *argv):
    rc = bl.main(list(argv))
    return rc, capsys.readouterr().out


def load(bk):
    return bs.load(bs.path(bk.root))


def planned(bk, capsys, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    monkeypatch.setattr(bl, "_root", lambda: bk.root)
    d = [{"questions": [{"question": QT, "header": "Assets", "options": copy.deepcopy(OPTS)}]}]
    put(bk, mk("B1", ["a.py"], decisions=d), approved=None)


def answer_file(tmp_path, answers, **kw):
    f = tmp_path / "a.json"
    f.write_text(json.dumps({"answers": answers, "by": "user", **kw}))
    return str(f)


def test_decide_records_option_step(bk, capsys, tmp_path, monkeypatch):
    planned(bk, capsys, monkeypatch)
    rc, out = cli(capsys, "decide", "--file", answer_file(tmp_path, {"B1: " + QT: "Git LFS"}))
    assert rc == 0 and out.rstrip().endswith(", 1 main steps (sl backlog status lists them)")
    assert get(bk, "B1")["main_steps"] == [{**STEP, "question": QT}]


def test_decide_plain_option_no_step(bk, capsys, tmp_path, monkeypatch):
    planned(bk, capsys, monkeypatch)
    assert cli(capsys, "decide", "--file", answer_file(tmp_path, {"B1: " + QT: "Plain git"}))[0] == 0
    assert "main_steps" not in get(bk, "B1")


def test_decide_explicit_step_wins(bk, capsys, tmp_path, monkeypatch):
    planned(bk, capsys, monkeypatch)
    f = answer_file(tmp_path, {"B1: " + QT: "Git LFS"}, steps={"B1: " + QT: {"runs": "user", "command": "gh auth login"}})
    assert cli(capsys, "decide", "--file", f)[0] == 0
    assert get(bk, "B1")["main_steps"] == [{"runs": "user", "command": "gh auth login", "question": QT}]


def test_decide_step_on_ship_refused(bk, capsys, tmp_path, monkeypatch):
    planned(bk, capsys, monkeypatch)
    before = bs.path(bk.root).read_text()
    f = answer_file(tmp_path, {bs.SHIP_Q: "Approve shipping"}, steps={bs.SHIP_Q: STEP})
    assert cli(capsys, "decide", "--file", f) == (2, f"BLOCKED: steps: {bs.SHIP_Q[:60]} takes no step\n")
    assert bs.path(bk.root).read_text() == before


def test_decide_print_strips_step_keys(bk, capsys, tmp_path, monkeypatch):
    planned(bk, capsys, monkeypatch)
    rc = bl.main(["decide", "--print"])
    cap = capsys.readouterr()
    assert rc == 0 and '"runs"' not in cap.out and '"command"' not in cap.out
    assert 'step: "B1: Store assets?" / "Git LFS (Recommended)": main runs this: git lfs install' in cap.err


def test_decide_print_batch_strips_step_keys(bk, capsys, tmp_path, monkeypatch):
    planned(bk, capsys, monkeypatch)
    wt = tmp_path / "wt"
    (wt / ".superlite").mkdir(parents=True)
    (wt / ".superlite" / "question.json").write_text(json.dumps({"questions": [{"question": QT, "header": "Assets", "options": OPTS}]}))
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"worktree": str(wt)}))
    rc = bl.main(["decide", "--print", "--batch", "B1"])
    cap = capsys.readouterr()
    assert rc == 0 and '"runs"' not in cap.out and '"command"' not in cap.out
    assert 'step: "Store assets?" / "Git LFS (Recommended)": main runs this: git lfs install' in cap.err


def test_answer_writes_steps(bk, capsys):
    wt = running(bk)
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "needs_decision"}))
    (wt / ".superlite" / "question.json").write_text(json.dumps({"questions": [{"question": QT, "header": "Assets", "options": OPTS}]}))
    f = bk.root / "a.json"
    f.write_text(json.dumps({"answers": {QT: "Git LFS"}, "by": "user"}))
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 0
    assert json.loads((wt / ".superlite" / "answer-1.json").read_text())["steps"] == {QT: STEP}
    sent = [c for c in bk.calls if c[0] == "text"]
    assert any("main runs this: git lfs install" in " ".join(map(str, c[1])) for c in sent)
    assert get(bk, "B1")["main_steps"] == [{**STEP, "question": QT}]


def test_answer_without_step_writes_none(bk, capsys):
    wt = running(bk)
    bs.update(bs.path(bk.root), lambda d: bs.batch(d, "B1").update({"state": "needs_decision"}))
    (wt / ".superlite" / "question.json").write_text(json.dumps({"questions": [{"question": QT, "header": "Assets", "options": OPTS}]}))
    f = bk.root / "a.json"
    f.write_text(json.dumps({"answers": {QT: "Plain git"}, "by": "user"}))
    assert run(capsys, "answer", "B1", "--file", str(f))[0] == 0
    assert "steps" not in json.loads((wt / ".superlite" / "answer-1.json").read_text())


def test_added_lines_keep_step_lines(monkeypatch):
    import backlog_state
    rows = ["batch | issues | state | lead | PR | next", "B3 | #9 | planned | - | - | start",
            "step B3: main runs this: c (#9)", "step B1: main runs this: d (#1)"]
    monkeypatch.setattr(backlog_state, "status_lines", lambda *a, **k: rows)
    got = bl.added_lines({}, ["B3"], None)
    assert rows[2] in got and rows[1] in got and rows[3] not in got
