"""status and start name the reason a planned batch waits for another (#742)."""
import sys
from backlog_fixtures import batch as b
from test_backlog_run import bk, put, run  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402


def data(*batches):
    return {**bs.default(), "repo": "o/r", "batches": list(batches)}


def test_waits_for_names_the_first_unshipped_dependency_and_its_reason():
    d = data(b("B1", ["a.py"], "shipped"), b("B2", ["b.py"]),
             b("B3", ["a.py", "b.py"], depends=["B1", "B2"], depends_why={"B1": "shares a.py", "B2": "shares b.py"}))
    b3 = d["batches"][2]
    assert bs.waits_for(d, b3) == "B2: shares b.py" and bs.waits_for(d, d["batches"][1]) == ""
    b3["depends_why"] = {}
    assert bs.waits_for(d, b3) == "B2"
    b3["depends_why"] = {"B2": "issue #3\x1b[2J says\nafter #2"}
    assert bs.waits_for(d, b3) == "B2: issue #3 [2J says after #2"
    b3["depends_why"] = "broken"
    assert bs.waits_for(d, b3) == "B2"


def test_status_keeps_the_cell_and_adds_one_reason_line():
    d = data(b("B1", ["a.py"], "running"), b("B2", ["a.py"], depends=["B1"], depends_why={"B1": "shares a.py"}), b("B3", ["c.py"], depends=["B1"]))
    lines = bs.status_lines(d)
    assert "B2 | #2 | planned | - | - | waits B1" in lines and "B3 | #3 | planned | - | - | waits B1" in lines
    assert [x for x in lines if " waits for " in x] == ["B2 waits for B1: shares a.py"]
    assert lines.index("B2 waits for B1: shares a.py") > lines.index("B3 | #3 | planned | - | - | waits B1")


def test_skip_drops_the_reason_with_the_dependency():
    d = data(b("B1", ["a.py"]), b("B2", ["a.py"], depends=["B1"], depends_why={"B1": "shares a.py"}))
    bs.skip_issue(d, 1)
    assert [x["id"] for x in d["batches"]] == ["B2"] and d["batches"][0]["depends"] == [] and "depends_why" not in d["batches"][0]


def test_start_refusal_names_the_reason(bk, capsys):
    put(bk, b("B1", ["a.py"]), b("B2", ["a.py"], depends=["B1"], depends_why={"B1": "shares a.py"}))
    rc, out = run(capsys, "start", "B2")
    assert rc == 2 and "BLOCKED: B2 waits for B1: shares a.py" in out.splitlines()
