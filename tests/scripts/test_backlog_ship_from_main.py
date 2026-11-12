import json, sys, types
import pytest
from backlog_fixtures import APPROVED  # noqa: F401
from test_backlog_ship import sh, ship, b1, AG, B2  # noqa: F401
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_run  # noqa: E402
import backlog_state as bs  # noqa: E402
import ship_lock  # noqa: E402

SHIPPED = "pr https://github.com/o/r/pull/301\nmerged #301 as abc\n"


@pytest.fixture
def fm(sh, monkeypatch):
    monkeypatch.delenv("SUPERLITE_FLEET_ROLE", raising=False)
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    sh.stops = []
    monkeypatch.setitem(sys.modules, "fleet", types.SimpleNamespace(stop=lambda sd, ids: sh.stops.append(("stop", ids))))
    def run(cmd, cwd, timeout=None):
        sh.calls.append(cmd); return (0, "")
    monkeypatch.setattr(backlog_run, "_run", run)
    setb(sh, state="parked", reason="merge denied", version="1.5.8")
    (sh.wt / "scripts" / "bump-version.sh").write_text("")
    (sh.wt / "package.json").write_text('{"version": "1.5.8"}')
    (sh.wt / ".version-bump.json").write_text(json.dumps({"files": [{"path": "package.json", "field": "version"}]}))
    sh.replies = {"git symbolic-ref": (0, "origin/main\n"), "git show origin/main:package.json": (0, '{"version": "1.5.7"}\n'),
                  "maxapp ship -C": (0, SHIPPED)}
    return sh


def setb(sh, **kw):
    bs.update(bs.path(sh.root), lambda d: bs.batch(d, "B1").update(kw))


def go(capsys, *extra):
    return ship(capsys, "B1", "merge", "--from-main", *extra)


def test_from_main_ships_a_parked_batch(fm, capsys):
    sh = fm
    assert go(capsys) == (0, f"B1 shipped PR #301 1.5.8 summary={sh.sd / 'backlog' / 'B1.md'}\n")
    r = b1(sh)
    assert (r["state"], r["pr"], r["merged"], r["version"], r["open_issues"]) == ("shipped", 301, True, "1.5.8", [])
    assert ship_lock.holder(sh.lock) is None
    assert ("stop", ["W1"]) in sh.stops
    pb = sh.sd / "backlog" / "B1.pr-body.md"
    assert ["git", "fetch", "origin"] in sh.calls and ["git", "rebase", "origin/main"] in sh.calls
    assert ["maxapp", "ship", "-C", str(sh.wt), "--timeout", "8", "--title", "B1: #5", "--body-file", str(pb)] in sh.calls
    assert ["bash", "scripts/bump-version.sh", "1.5.9"] not in sh.calls
    assert pb.read_text() == "Closes #5\n" and (sh.sd / "backlog" / "B1.md").is_file()


def test_from_main_bumps_again_when_main_has_the_version(fm, capsys):
    sh = fm
    sh.replies["git show origin/main:package.json"] = (0, '{"version": "1.5.8"}\n')
    rc, out = go(capsys)
    lines = out.splitlines()
    assert rc == 0 and lines[0] == "B1 version 1.5.9 (origin/main is at 1.5.8)"
    assert lines[1] == f"B1 shipped PR #301 1.5.9 summary={sh.sd / 'backlog' / 'B1.md'}"
    assert ["bash", "scripts/bump-version.sh", "1.5.9"] in sh.calls and ["git", "commit", "-am", "Bump version to 1.5.9"] in sh.calls
    assert b1(sh)["version"] == "1.5.9"
    setb(sh, state="parked", merged=False, version="1.5.8")
    sh.replies["git show origin/main:package.json"] = (0, '{"version": "1.5.10"}\n')
    rc, out = go(capsys)
    assert out.splitlines()[0] == "B1 version 1.5.11 (origin/main is at 1.5.10)"
    setb(sh, state="parked", merged=False, version="1.5.8")
    sh.replies["git show origin/main:package.json"] = (1, "fatal")
    assert go(capsys) == (3, "BLOCKED: cannot read the version on origin/main; lock released, B1 parked: run sl backlog ship B1 merge --from-main again\n")
    assert ship_lock.holder(sh.lock) is None and b1(sh)["state"] == "parked"


def test_from_main_refusals(fm, capsys, monkeypatch):
    sh = fm
    assert ship(capsys, "B1", "lock", "--from-main") == (2, "refused: --from-main goes only with merge\n")
    monkeypatch.setenv("SUPERLITE_FLEET_WORKER", "W1")
    assert go(capsys) == (2, "refused: sl backlog ship B1 merge --from-main runs only in the main session\n")
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER")
    bs.update(bs.path(sh.root), lambda d: d.update({"approved_ship": None}))
    assert go(capsys) == (2, "refused: no ship approval recorded (sl backlog decide)\n")
    bs.update(bs.path(sh.root), lambda d: d.update({"approved_ship": APPROVED}))
    setb(sh, state="running")
    assert go(capsys) == (2, "refused: B1 is running, not parked (main ships a parked batch only)\n")
    setb(sh, state="parked", version=None)
    assert go(capsys) == (2, "refused: B1 has no version yet (its lead never ran bump)\n")
    setb(sh, version="1.5.8")
    sh.replies["git status --porcelain"] = (0, " M a.py\n")
    assert go(capsys) == (2, "refused: uncommitted changes in the worktree\n")
    del sh.replies["git status --porcelain"]
    gone = sh.wt / "gone"
    setb(sh, worktree=str(gone))
    assert go(capsys) == (2, f"refused: worktree {gone} is gone\n")
    assert sh.stops == [] and not sh.lock.exists() and b1(sh)["state"] == "parked"
    assert not any(c[:3] == ["maxapp", "ship", "-C"] for c in sh.calls)


def test_from_main_waits_for_another_batch(fm, capsys):
    sh = fm
    ship_lock.acquire(sh.lock, B2, None, 9_000); sh.live = {AG, "sl-x-w5"}
    assert go(capsys, "--wait", "0") == (4, "WAIT: ship lock held by B2 (W5), queue place 1 of 1; run sl backlog ship B1 merge --from-main again\n")
    assert ship_lock.holder(sh.lock)["batch"] == "B2"
    assert ["git", "fetch", "origin"] not in sh.calls


def test_from_main_rerun_keeps_the_lock_as_main(fm, capsys):
    sh = fm
    sh.replies["maxapp ship -C"] = (4, "running")
    assert go(capsys) == (4, "RERUN: sl backlog ship B1 merge --from-main (run 1 of 5)\n")
    assert ship_lock.holder(sh.lock) == {"batch": "B1", "lead": "main", "agent": None, "repo": "o/r", "time": 10_000}
    assert b1(sh)["state"] == "parked" and sh.stops == []
    assert go(capsys) == (4, "RERUN: sl backlog ship B1 merge --from-main (run 2 of 5)\n")


def test_from_main_conflict_aborts_and_releases(fm, capsys):
    sh = fm
    sh.replies["git rebase origin"] = (1, "CONFLICT")
    sh.replies["git diff --name-only --diff-filter=U"] = (0, "a.py\nb.py\n")
    assert go(capsys) == (5, "CONFLICT: a.py b.py; rebase aborted; lock released, B1 parked: sl backlog start B1 resumes its lead to fix it\n")
    assert ["git", "rebase", "--abort"] in sh.calls and ship_lock.holder(sh.lock) is None
    assert b1(sh)["reason"].startswith("CONFLICT: a.py b.py")
    assert not any(c[:3] == ["maxapp", "ship", "-C"] for c in sh.calls)


def test_from_main_red_and_failure_release_and_park(fm, capsys):
    sh = fm
    sh.replies["maxapp ship -C"] = (3, "check unit failed")
    assert go(capsys) == (6, "RED: check unit failed; lock released, B1 parked: sl backlog start B1 resumes its lead to fix it\n")
    r = b1(sh)
    assert r["reason"] == "RED: check unit failed" and not r["merged"] and ship_lock.holder(sh.lock) is None
    sh.replies["maxapp ship -C"] = (1, "gh failed")
    assert go(capsys) == (3, "BLOCKED: maxapp ship failed (gh failed); lock released, B1 parked: run sl backlog ship B1 merge --from-main again\n")
    assert ship_lock.holder(sh.lock) is None


def test_from_main_names_open_issues(fm, capsys):
    sh = fm
    sh.replies["gh issue view"] = (0, "OPEN\n")
    rc, out = go(capsys)
    assert rc == 0 and "B1 OPEN #5" in out.splitlines() and b1(sh)["open_issues"] == [5]


def test_from_main_compares_versions_as_integers(fm, capsys):
    sh = fm
    setb(sh, version="1.5.10")
    (sh.wt / "package.json").write_text('{"version": "1.5.10"}')
    sh.replies["git show origin/main:package.json"] = (0, '{"version": "1.5.9"}\n')
    rc, out = go(capsys)
    assert rc == 0 and out.startswith("B1 shipped PR #301 1.5.10 ")
    assert ["bash", "scripts/bump-version.sh", "1.5.10"] not in sh.calls and not any(c[:2] == ["bash", "scripts/bump-version.sh"] for c in sh.calls)


def test_from_main_failed_bump_resets_the_worktree(fm, capsys):
    sh = fm
    sh.replies["git show origin/main:package.json"] = (0, '{"version": "1.5.8"}\n')
    sh.replies["bash scripts/bump-version.sh"] = (1, "boom")
    assert go(capsys) == (3, "BLOCKED: bash scripts/bump-version.sh failed: boom; lock released, B1 parked: run sl backlog ship B1 merge --from-main again\n")
    reset = ["git", "reset", "--hard", "HEAD"]
    assert reset in sh.calls and sh.calls.index(reset) > sh.calls.index(["bash", "scripts/bump-version.sh", "1.5.9"])
    assert ship_lock.holder(sh.lock) is None and not any(c[:2] == ["maxapp", "ship"] for c in sh.calls)
    del sh.replies["bash scripts/bump-version.sh"]
    sh.calls.clear()
    setb(sh, state="parked", merged=False, version="1.5.8")
    sh.replies["git commit -am"] = (1, "nothing")
    assert go(capsys) == (3, "BLOCKED: git commit failed: nothing; lock released, B1 parked: run sl backlog ship B1 merge --from-main again\n")
    assert reset in sh.calls and ship_lock.holder(sh.lock) is None


def test_from_main_rerun_skips_sync_and_bump(fm, capsys):
    sh = fm
    sh.replies["git show origin/main:package.json"] = (0, '{"version": "1.5.8"}\n')
    sh.replies["maxapp ship -C"] = (4, "running")
    rc, out = go(capsys)
    assert rc == 4 and out.splitlines() == ["B1 version 1.5.9 (origin/main is at 1.5.8)", "RERUN: sl backlog ship B1 merge --from-main (run 1 of 5)"]
    sh.calls.clear()
    sh.replies["maxapp ship -C"] = (0, SHIPPED)
    assert go(capsys) == (0, f"B1 shipped PR #301 1.5.9 summary={sh.sd / 'backlog' / 'B1.md'}\n")
    assert not any(c[:2] in (["git", "fetch"], ["git", "rebase"], ["git", "show"], ["bash", "scripts/bump-version.sh"]) for c in sh.calls)
    assert any(c[:3] == ["maxapp", "ship", "-C"] for c in sh.calls)
    assert b1(sh)["version"] == "1.5.9"


def test_from_main_takes_over_its_lead_lock(fm, capsys):
    sh = fm
    ship_lock.acquire(sh.lock, {"batch": "B1", "lead": "W1", "agent": AG, "repo": "o/r"}, None, 9_000)
    sh.live = {AG}
    sh.replies["maxapp ship -C"] = (4, "running")
    assert go(capsys) == (4, "RERUN: sl backlog ship B1 merge --from-main (run 1 of 5)\n")
    assert ["git", "fetch", "origin"] in sh.calls and ["git", "rebase", "origin/main"] in sh.calls
    assert ship_lock.holder(sh.lock) == {"batch": "B1", "lead": "main", "agent": None, "repo": "o/r", "time": 10_000}
    sh.replies["maxapp ship -C"] = (0, SHIPPED)
    assert go(capsys)[0] == 0 and ship_lock.holder(sh.lock) is None
