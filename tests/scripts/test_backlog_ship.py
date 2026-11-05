import json, os, sys, types
import pytest
from backlog_fixtures import APPROVED, batch
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_ship as bsh  # noqa: E402
import backlog_state as bs  # noqa: E402
import ship_lock  # noqa: E402

AG = "sl-m-w1"
B2 = {"batch": "B2", "lead": "W5", "agent": "sl-x-w5", "repo": "o/r"}

@pytest.fixture
def sh(tmp_path, monkeypatch):
    root, wt = tmp_path / "main", tmp_path / "wt"; (root / ".superlite").mkdir(parents=True); (wt / "scripts").mkdir(parents=True)
    (wt / "scripts" / "test_layers.py").write_text("")
    for k, v in (("SUPERLITE_HOME", str(tmp_path / "h")), ("SUPERLITE_FLEET_ROLE", "lead"), ("SUPERLITE_FLEET_WORKER", "W1")):
        monkeypatch.setenv(k, v)
    ns = types.SimpleNamespace(root=root, sd=root / ".superlite", wt=wt, lock=ship_lock.lock_path("o/r", tmp_path / "h"), calls=[], live={AG}, replies={})
    bs.update(bs.path(root), lambda d: d.update({"repo": "o/r", "approved_ship": APPROVED,
                                                 "batches": [batch("B1", ["a.py"], "running", issues=[5], lead="W1", agent=AG, worktree=str(wt))]}))
    def run(cmd, cwd, timeout=None):
        ns.calls.append(cmd); return next((r for p, r in ns.replies.items() if " ".join(cmd).startswith(p)), (0, ""))
    for name, value in (("_root", lambda: root), ("_run", run), ("_live", lambda: ns.live), ("_now_ms", lambda: 10_000), ("_sleep", lambda s: None)):
        monkeypatch.setattr(bsh, name, value)
    if os.environ.get("SUPERLITE_REAL") != "1":
        monkeypatch.setitem(sys.modules, "backlog_brief", types.SimpleNamespace(summary=lambda b, notes: f"{b['id']} shipped: #5\nPR: #{b['pr']}\n"))
    return ns

def ship(capsys, *argv):
    rc = bsh.main(list(argv)); return rc, capsys.readouterr().out

def b1(sh):
    return bs.batch(bs.load(bs.path(sh.root)), "B1")

def locked(sh, capsys):
    assert ship(capsys, "B1", "lock")[0] == 0; sh.calls.clear()

def test_only_the_batch_lead_with_an_approval_ships(sh, capsys, monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W2")
    assert ship(capsys, "B1", "lock") == (2, "refused: sl backlog ship B1 runs only in its lead W1\n")
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W1"); monkeypatch.delenv("SUPERLITE_FLEET_ROLE")
    assert ship(capsys, "B1", "lock")[0] == 2
    monkeypatch.setenv("SUPERLITE_FLEET_ROLE", "lead"); bs.update(bs.path(sh.root), lambda d: d.update({"approved_ship": None}))
    assert ship(capsys, "B1", "lock") == (2, "refused: no ship approval recorded (sl backlog decide)\n") and sh.calls == [] and not sh.lock.exists()

def test_lock_rebases_and_names_stale_layers(sh, capsys):
    sh.replies = {"git symbolic-ref": (0, "origin/main\n"), "python3 scripts/test_layers.py check": (2, "headless stale: x\ntui stale: y\n")}
    assert ship(capsys, "B1", "lock") == (0, "LAYERS: headless tui\nB1 lock held\n")
    assert ["git", "fetch", "origin"] in sh.calls and ["git", "rebase", "origin/main"] in sh.calls
    assert ship_lock.holder(sh.lock) == {"batch": "B1", "lead": "W1", "agent": AG, "repo": "o/r", "time": 10_000}

def test_lock_waits_for_a_live_holder_and_takes_over_a_dead_one(sh, capsys):
    ship_lock.acquire(sh.lock, B2, None, 9_000); sh.live = {AG, "sl-x-w5"}
    assert ship(capsys, "B1", "lock", "--wait", "0") == (4, "WAIT: ship lock held by B2 (W5); run sl backlog ship B1 lock again\n") and sh.calls == []
    sh.live = {AG}
    rc, out = ship(capsys, "B1", "lock")
    assert rc == 0 and out.startswith("took over the stale ship lock of B2 (W5)\n")
    inc = json.loads((sh.sd / "incidents.jsonl").read_text().splitlines()[-1])
    assert inc["kind"] == "workaround" and "B2" in inc["context"]

def test_rebase_conflict_keeps_the_lock(sh, capsys):
    sh.replies = {"git rebase": (1, "CONFLICT"), "git diff --name-only --diff-filter=U": (0, "a.py\nb.py\n")}
    assert ship(capsys, "B1", "lock") == (5, "CONFLICT: a.py b.py; lock held: resolve with fixers, git rebase --continue, then run lock again\n")
    assert ship_lock.holder(sh.lock)["batch"] == "B1"

def test_bump(sh, capsys):
    assert ship(capsys, "B1", "bump") == (2, "refused: B1 does not hold the ship lock (run lock first)\n")
    locked(sh, capsys)
    assert ship(capsys, "B1", "bump") == (0, "B1 bump: skipped (no scripts/bump-version.sh)\n")
    (sh.wt / "scripts" / "bump-version.sh").write_text(""); (sh.wt / "package.json").write_text('{"version": "1.5.7"}')
    (sh.wt / ".version-bump.json").write_text(json.dumps({"files": [{"path": "a.yaml", "field": "version"}, {"path": "package.json", "field": "version"}]}))
    sh.replies = {"python3 scripts/test_layers.py check": (2, "tui stale: y\n")}
    assert ship(capsys, "B1", "bump") == (2, "refused: stale layers tui (run them first)\n")
    sh.replies = {"git status --porcelain": (0, " M a.py\n")}
    assert ship(capsys, "B1", "bump") == (2, "refused: uncommitted changes in the worktree\n")
    sh.replies = {}
    assert ship(capsys, "B1", "bump") == (0, "B1 version 1.5.8\n") and b1(sh)["version"] == "1.5.8"
    assert ["bash", "scripts/bump-version.sh", "1.5.8"] in sh.calls and ["git", "commit", "-am", "Bump version to 1.5.8"] in sh.calls
    assert ship(capsys, "B1", "bump", "--version", "1.6.0")[0] == 0 and b1(sh)["version"] == "1.6.0"

def test_merge_records_the_pr_writes_the_summary_and_releases(sh, capsys):
    locked(sh, capsys); bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"version": "1.5.8"}))
    (sh.wt / ".superlite").mkdir(); (sh.wt / ".superlite" / "notes.md").write_text("Ruling: x\n")
    sh.replies = {"maxapp ship": (0, "pr https://github.com/o/r/pull/201\nmerged #201 as abc\nnext: maxapp ship -C /wt (from outside the worktree)\n")}
    s = sh.sd / "backlog" / "B1.md"
    assert ship(capsys, "B1", "merge", "--title", "B1: leads", "--body-file", "/b.md") == (0, f"B1 shipped PR #201 1.5.8 summary={s}\n")
    assert ["maxapp", "ship", "-C", str(sh.wt), "--timeout", "8", "--title", "B1: leads", "--body-file", "/b.md"] in sh.calls
    assert s.read_text().startswith("B1 shipped: #5") and (b1(sh)["pr"], b1(sh)["merged"], b1(sh)["state"]) == (201, True, "running")
    assert ship_lock.holder(sh.lock) is None

def test_merge_timeouts_red_checks_and_release(sh, capsys):
    locked(sh, capsys); sh.replies = {"maxapp ship": (3, "check tests failed\nsee https://x\n")}
    assert ship(capsys, "B1", "merge") == (6, "RED: check tests failed / see https://x; lock held: fix with fixers, commit, run merge again\n")
    sh.replies = {"maxapp ship": (4, "still running")}
    for k in range(1, 5):
        assert ship(capsys, "B1", "merge") == (4, f"RERUN: sl backlog ship B1 merge (run {k} of 5)\n")
    assert ship(capsys, "B1", "merge") == (3, "BLOCKED: maxapp ship timed out 5 times; lock released\n")
    assert ship_lock.holder(sh.lock) is None and b1(sh)["state"] == "parked"
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update({"state": "running"})); locked(sh, capsys)
    assert ship(capsys, "B1", "release", "--park", "conflict in a.py") == (0, "B1 lock released, parked\n")
    assert ship_lock.holder(sh.lock) is None and (b1(sh)["state"], b1(sh)["reason"]) == ("parked", "conflict in a.py")
