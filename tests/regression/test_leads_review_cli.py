import json, sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_state as bs  # noqa: E402
import ship_lock  # noqa: E402
from backlog_fixtures import APPROVED, batch as mk  # noqa: E402
from test_backlog_cli import bk as cli_bk, cli, load  # noqa: E402,F401
from test_backlog_run import bk as run_bk, put, running, run as run_cmd, get  # noqa: E402,F401
from test_backlog_ship import sh, ship, b1, locked  # noqa: E402,F401
import backlog_ship as bsh  # noqa: E402


def test_decide_refuses_inside_a_fleet_worker(cli_bk, capsys, monkeypatch, tmp_path):
    cli(capsys, "plan")
    f = tmp_path / "a.json"; f.write_text(json.dumps({"answers": {bs.SHIP_Q: bs.SHIP_OK}}))
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W1")
    rc, out = cli(capsys, "decide", "--file", str(f))
    assert rc == 2 and out.startswith("refused") and load(cli_bk)["approved_ship"] is None


def test_plan_does_not_overwrite_a_batch_started_during_triage(cli_bk, capsys, monkeypatch):
    import backlog as bl
    real = bl._triage

    def triage(*a, **k):
        r = real(*a, **k)
        bs.update(bs.path(cli_bk.root), lambda d: d["batches"].append(mk("B9", ["z.py"], "running")))
        return r
    monkeypatch.setattr(bl, "_triage", triage)
    rc, out = cli(capsys, "plan")
    assert rc == 3 and "changed while triage ran" in out and [b["id"] for b in load(cli_bk)["batches"]] == ["B9"]


def test_wait_ships_a_merged_batch_whose_pane_is_gone(run_bk, capsys):
    running(run_bk, merged=True, pr=201, version="1.5.8"); run_bk.stops.clear(); run_bk.states.clear()
    out = run_cmd(capsys, "wait", "--timeout", "0")[1]
    assert out.startswith("B1 shipped PR #201 1.5.8") and get(run_bk, "B1")["state"] == "shipped"


def test_merge_reads_notes_before_maxapp_removes_the_worktree(sh, capsys, monkeypatch):
    import backlog_brief
    locked(sh, capsys)
    (sh.wt / ".superlite").mkdir(); (sh.wt / ".superlite" / "notes.md").write_text("Ruling: keep\n")
    seen = {}
    monkeypatch.setitem(sys.modules, "backlog_brief", type("M", (), {"summary": staticmethod(lambda b, n: seen.setdefault("n", n) or "x")}))
    def run(cmd, cwd, timeout=None):
        if cmd[:2] != ["maxapp", "ship"]:
            return 0, "CLOSED"
        (sh.wt / ".superlite" / "notes.md").unlink()
        return 0, "merged #7"
    monkeypatch.setattr(bsh, "_run", run)
    assert ship(capsys, "B1", "merge")[0] == 0 and seen["n"] == "Ruling: keep\n"


def test_bump_twice_does_not_bump_the_version_again(sh, capsys):
    locked(sh, capsys)
    (sh.wt / "scripts" / "bump-version.sh").write_text(""); (sh.wt / "package.json").write_text('{"version": "1.5.8"}')
    (sh.wt / ".version-bump.json").write_text(json.dumps({"files": [{"path": "package.json", "field": "version"}]}))
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"version": "1.5.8"}))
    sh.calls.clear()
    assert ship(capsys, "B1", "bump") == (0, "B1 version 1.5.8 (already bumped)\n")
    assert not any(c[:2] == ["bash", "scripts/bump-version.sh"] for c in sh.calls)
