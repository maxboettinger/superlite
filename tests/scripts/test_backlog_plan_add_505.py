import sys
import pytest
from test_backlog_cli import bk, cli, load, BATCH, bs, bl  # noqa: F401

APPROVED = {"by": "AskUserQuestion", "time": "2026-01-01T00:00:00Z"}
NEW = {"id": "B1", "topic": "urgent", "issues": [2], "files": ["b.py"], "depends": [], "decisions": []}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)


def setup(bk, capsys):
    bk.batches = [{**BATCH, "issues": [1]}]
    cli(capsys, "plan")
    def up(d):
        b = bs.batch(d, "B1")
        b["state"] = "running"
        d["approved_ship"] = APPROVED
    bs.update(bs.path(bk.root), up)
    bk.batches = [NEW]
    bk.gh.clear()


def test_add_plans_next_to_running(bk, capsys):
    setup(bk, capsys)
    rc, out = cli(capsys, "plan", "--issues", "2", "--add")
    d = load(bk)
    assert rc == 0
    assert [(b["id"], b["state"]) for b in d["batches"]] == [("B1", "running"), ("B2", "planned")]
    assert d["approved_ship"] == APPROVED and d["round"] == ["B1", "B2"]
    assert set(d["titles"]) == {"1", "2"}
    assert "B2 | #2 | planned" in out
    assert bk.ctx["open"] == [{"id": "B1", "state": "running", "files": ["a.py"]}]


def test_add_overlap_line(bk, capsys):
    setup(bk, capsys)
    bk.batches = [{**NEW, "files": ["a.py"]}]
    rc, out = cli(capsys, "plan", "--issues", "2", "--add")
    assert rc == 0
    assert "overlap: B2 shares a.py with B1 (running): start holds B2 until B1 ships" in out and "clash B1" in out


def test_add_flag_errors(bk, capsys):
    assert cli(capsys, "plan", "--add") == (2, "BLOCKED: --add needs --issues\n")
    assert cli(capsys, "plan", "--issues", "2", "--add", "--reset") == (2, "BLOCKED: --add and --reset exclude each other\n")


def test_add_refuses_an_open_issue(bk, capsys):
    setup(bk, capsys)
    assert cli(capsys, "plan", "--issues", "1", "--add") == (2, "BLOCKED: --issues: #1 is in B1 (running)\n")
    assert bk.gh == []


def test_pinned_refusal_names_add(bk, capsys):
    setup(bk, capsys)
    assert cli(capsys, "plan", "--issues", "2") == (2, "BLOCKED: backlog has open batches (B1 running); --reset is refused too while a batch is running or needs_decision; --add plans the --issues next to them\n")
    assert cli(capsys, "plan") == (2, "BLOCKED: backlog has open batches (B1 running); --reset is refused too while a batch is running or needs_decision\n")


def test_add_without_open_batch(bk, capsys):
    bk.batches = [{**BATCH, "issues": [1]}]
    rc, _ = cli(capsys, "plan", "--issues", "1", "--add")
    d = load(bk)
    assert rc == 0 and d["approved_ship"] is None and d["round"] == ["B1"] and bk.ctx["open"] == []


def test_add_keeps_source_cap_outside(bk, capsys):
    setup(bk, capsys)
    out0 = [{"number": 7, "title": "s", "reason": "not planned (cap)"}, {"number": 2, "title": "t", "reason": "not planned (cap)"}]
    def up(d):
        d["source"] = {"tracker": "jira", "jql": "project = X"}
        d["max_batches"] = 9
        d["outside"] = out0
    bs.update(bs.path(bk.root), up)
    assert cli(capsys, "plan", "--issues", "2", "--add")[0] == 0
    d = load(bk)
    assert d["source"] == {"tracker": "jira", "jql": "project = X"} and d["max_batches"] == 9
    assert [o["number"] for o in d["outside"]] == [7]


def test_add_race_refused(bk, capsys):
    setup(bk, capsys)
    real = sys.modules["fleet_io"].wait
    def wait(sd, ids, t):
        r = real(sd, ids, t)
        bs.update(bs.path(bk.root), lambda d: d["batches"].append({"id": "B7", "topic": "x", "issues": [2], "files": [], "depends": [], "decisions": [], "state": "planned"}))
        return r
    sys.modules["fleet_io"].wait = wait
    before = [b["id"] for b in load(bk)["batches"]]
    rc, out = cli(capsys, "plan", "--issues", "2", "--add")
    assert (rc, out) == (3, "BLOCKED: backlog changed while triage ran (#2 is in B7 planned)\n")
    assert [b["id"] for b in load(bk)["batches"]] == before + ["B7"]


def test_plan_help_names_add(bk, capsys):
    with pytest.raises(SystemExit) as e:
        bl.main(["plan", "--help"])
    assert e.value.code == 0 and "--add" in capsys.readouterr().out


def test_open_batches_and_overlap_examples():
    data = {"batches": [{"id": "B1", "state": "shipped", "files": ["x.py"]}, {"id": "B10", "state": "running", "files": ["b.py"]}, {"id": "B2", "state": "planned", "files": ["a.py"]}]}
    assert bl.open_batches(data) == [{"id": "B2", "state": "planned", "files": ["a.py"]}, {"id": "B10", "state": "running", "files": ["b.py"]}]
    assert bl.overlap_lines([{"id": "B96", "files": ["a.py", "b.py"]}], [{"id": "B89", "state": "running", "files": ["a.py"]}]) == ["overlap: B96 shares a.py with B89 (running): start holds B96 until B89 ships"]
    assert bl.overlap_lines([{"id": "B96", "files": ["b.py"]}], [{"id": "B90", "state": "planned", "files": ["b.py"]}]) == ["overlap: B96 shares b.py with B90 (planned): whichever starts first holds the files"]
    f = ["a.py", "b.py", "c.py", "d.py", "e.py"]
    assert bl.overlap_lines([{"id": "B9", "files": f}], [{"id": "B1", "state": "planned", "files": f}])[0].startswith("overlap: B9 shares a.py, b.py, c.py (+2 more) with B1")
