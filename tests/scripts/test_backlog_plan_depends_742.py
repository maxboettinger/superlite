"""backlog plan drops a dependency with no shared file and no why, names it under the stored ids and keeps every reason (#742)."""
import pytest
from test_backlog_cli import bk, cli, load, bs, bl  # noqa: F401
from test_backlog_plan_add_583 import state


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(bl, "_tracked", lambda root: [])


def bt(bid, n, files, depends=()):
    return {"id": bid, "topic": "t", "issues": [n], "files": list(files), "depends": list(depends), "decisions": []}


def test_plan_drops_a_dependency_without_shared_file_or_why(bk, capsys):
    bk.batches = [bt("B7", 1, ["a.py"]), bt("B8", 2, ["b.py"], ["B7"])]
    rc, out = cli(capsys, "plan")
    b2 = bs.batch(load(bk), "B2")
    assert rc == 0 and b2["depends"] == [] and "depends_why" not in b2
    assert "depends: B2 no longer waits for B1: no shared file and no reason" in out.splitlines()


@pytest.mark.parametrize("dep,why", [("B7", "shares a.py"), ({"id": "B7", "why": "issue #2 says after #1"}, "issue #2 says after #1")])
def test_plan_stores_the_reason_under_the_new_ids(bk, capsys, dep, why):
    bk.batches = [bt("B7", 1, ["a.py"]), bt("B8", 2, ["a.py", "c.py"], [dep])]
    rc, out = cli(capsys, "plan")
    b2 = bs.batch(load(bk), "B2")
    assert rc == 0 and b2["depends"] == ["B1"] and b2["depends_why"] == {"B1": why} and "no longer waits" not in out


def test_plan_add_checks_a_dependency_on_an_open_batch(bk, capsys):
    state(bk, "running")
    bk.batches = [bt("B174", 2, ["b.py"], ["B1"])]
    rc, out = cli(capsys, "plan", "--issues", "2", "--add")
    assert rc == 0 and bs.batch(load(bk), "B2")["depends"] == []
    assert "depends: B2 no longer waits for B1: no shared file and no reason" in out.splitlines()


def test_triage_rules_name_the_why(bk, capsys):
    assert cli(capsys, "plan")[0] == 0
    text = (bk.sd / "briefs" / "triage.md").read_text(encoding="utf-8")
    assert ('depends lists a batch that must ship first, only when the two batches share a file or an issue\'s text names the order, as '
            '{"id": "<batch>", "why": "<the shared file, or the issue words that name the order; one line, at most 80 characters, no batch ids>"}; '
            'plan drops a dependency with neither a shared file nor a why, since every dependency keeps a lead idle until the other batch ships') in text
    assert "depends names batches that must ship first" not in text


def test_repair_lines_drop_a_batch_that_was_merged_away_and_keep_backlog_ids():
    lines = ["depends: B3 no longer waits for B1: x", "depends: B4 no longer waits for B2: x", "depends: B2 no longer waits for B9: x"]
    out = bl._dlines(lines, ["B1", "B2", "B4"], [{"id": "B1"}, {"id": "B2"}, {"id": "B3"}], {"B1", "B2", "B3", "B4"})
    assert out == ["depends: B3 no longer waits for B2: x", "depends: B2 no longer waits for B9: x"]
