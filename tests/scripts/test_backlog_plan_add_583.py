import pytest
import test_backlog_cli as tc
from test_backlog_cli import bk, cli, load, BATCH, bs, bl  # noqa: F401

APPROVED = {"by": "AskUserQuestion", "time": "2026-01-01T00:00:00Z"}
NEW = {"id": "B1", "topic": "urgent", "issues": [2], "files": ["b.py"], "depends": [], "decisions": []}


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(bl, "_tracked", lambda root: [])


def state(bk, st, extra=None):
    bk.batches = [{**BATCH, "issues": [1]}]
    cli_rc = bl.main(["plan"])
    assert cli_rc == 0

    def up(d):
        b = bs.batch(d, "B1")
        b["state"] = st
        d["approved_ship"] = APPROVED
        d.update(extra or {})
    bs.update(bs.path(bk.root), up)
    bk.batches = [NEW]
    bk.gh.clear()


def test_add_keeps_approval_on_drained_backlog(bk, capsys):
    state(bk, "shipped")
    capsys.readouterr()
    rc, out = cli(capsys, "plan", "--issues", "2", "--add")
    d = load(bk)
    assert rc == 0 and d["approved_ship"] == APPROVED and d["round"] == ["B2"]
    assert "B2 | #2 | planned" in out


def test_plain_pinned_plan_still_clears_approval(bk, capsys):
    state(bk, "shipped")
    rc, out = cli(capsys, "plan", "--issues", "2")
    assert rc == 0 and load(bk)["approved_ship"] is None
    assert "backlog o/r:" in out


def test_add_prints_only_the_new_batch(bk, capsys):
    state(bk, "running", {"outside": [{"number": 7, "title": "s", "reason": "not planned (cap)"}]})
    capsys.readouterr()
    rc, out = cli(capsys, "plan", "--issues", "2", "--add")
    assert rc == 0
    assert out.splitlines()[:2] == ["batch | issues | state | lead | PR | next", "B2 | #2 | planned | - | - | start"]
    assert "B1 |" not in out and "not planned" not in out and "backlog o/r:" not in out


def test_added_lines_unit():
    data = {"batches": [{"id": "B1", "state": "shipped", "issues": [1], "topic": "t", "files": [], "depends": [], "decisions": [], "answers": {}},
                        {"id": "B2", "state": "planned", "issues": [2], "topic": "t", "files": [], "depends": [], "decisions": [], "answers": {}}],
            "outside": [{"number": 3, "title": "T", "reason": "not planned (triage)"}, {"number": 9, "title": "T", "reason": "not planned (cap)"}],
            "round": ["B2"], "approved_ship": APPROVED}
    assert bl.added_lines(data, ["B2"], [2]) == ["batch | issues | state | lead | PR | next", "B2 | #2 | planned | - | - | start"]
    got = bl.added_lines(data, ["B2"], [2, 3])
    assert got[-1] == "not planned (triage): #3"


def test_worker_ids_and_open_depends_are_accepted(bk, capsys):
    state(bk, "running")
    bk.batches = [{"id": "B174", "topic": "Urgent Fix", "issues": [2], "files": ["b.py"], "depends": ["B1"], "decisions": []}]
    rc, out = cli(capsys, "plan", "--issues", "2", "--add")
    d = load(bk)
    assert rc == 0
    b2 = bs.batch(d, "B2")
    assert b2["depends"] == ["B1"] and b2["topic"] == "urgent-fix"
    assert 'topic: "B174" "Urgent Fix" -> urgent-fix' in out


def test_fast_path_plans_without_worker(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "_tracked", lambda root: ["s/scripts/backlog.py", "README.md"])
    monkeypatch.setattr(tc, "ISSUES", [tc.ISSUES[0], {**tc.ISSUES[1], "body": "Where: backlog.py"}, tc.ISSUES[2]])
    rc, out = cli(capsys, "plan", "--issues", "2")
    assert rc == 0
    assert not any(c[0] in ("spawn", "send") for c in bk.calls)
    assert bs.batch(load(bk), "B1")["files"] == ["s/scripts/backlog.py"]
    assert "fast path: #2 names s/scripts/backlog.py; no triage worker" in out


def test_fast_path_falls_back_without_named_files(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "_tracked", lambda root: ["s/scripts/backlog.py"])
    bk.batches = [NEW]
    rc, out = cli(capsys, "plan", "--issues", "2")
    assert rc == 0 and any(c[0] == "spawn" for c in bk.calls) and "fast path" not in out


def test_two_pins_use_the_worker(bk, capsys, monkeypatch):
    monkeypatch.setattr(bl, "_tracked", lambda root: ["s/scripts/backlog.py"])
    monkeypatch.setattr(tc, "ISSUES", [{**i, "body": "Where: backlog.py"} for i in tc.ISSUES])
    rc, out = cli(capsys, "plan", "--issues", "1,2")
    assert rc == 0 and any(c[0] == "spawn" for c in bk.calls) and "fast path" not in out


def test_tracked_reads_ls_files_and_fails_soft(tmp_path, monkeypatch):
    import types
    monkeypatch.undo()
    seen = []

    def run(cmd, **kw):
        seen.append(cmd)
        return types.SimpleNamespace(returncode=0, stdout="a/b.py\nc.md\n")
    monkeypatch.setattr(bl.subprocess, "run", run)
    assert bl._tracked(tmp_path) == ["a/b.py", "c.md"] and seen[0][:3] == ["git", "-C", str(tmp_path)]
    monkeypatch.setattr(bl.subprocess, "run", lambda *a, **k: types.SimpleNamespace(returncode=128, stdout=""))
    assert bl._tracked(tmp_path) == []

    def boom(*a, **k):
        raise OSError("no git")
    monkeypatch.setattr(bl.subprocess, "run", boom)
    assert bl._tracked(tmp_path) == []
