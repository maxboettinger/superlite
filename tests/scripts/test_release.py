# tests/scripts/test_release.py
import json, os, subprocess, sys, time
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import release  # noqa: E402

REAL_BOARD, REAL_READ = release.scoreboard.board, release.batch_cost.read_rows

GIT_ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, env=GIT_ENV, check=True, capture_output=True, text=True).stdout


@pytest.fixture
def repo(tmp_path):
    bare, work = tmp_path / "origin.git", tmp_path / "work"
    subprocess.run(["git", "init", "-q", "--bare", "-b", "main", str(bare)], env=GIT_ENV, check=True)
    work.mkdir()
    git(work, "init", "-q", "-b", "main")
    git(work, "config", "user.email", "t@t"); git(work, "config", "user.name", "t")
    (work / "package.json").write_text(json.dumps({"version": "1.5.244"}))
    (work / ".version-bump.json").write_text(json.dumps({"files": [{"path": "package.json", "field": "version"}]}))
    git(work, "add", "."); git(work, "commit", "-qm", "init")
    git(work, "remote", "add", "origin", str(bare)); git(work, "push", "-q", "origin", "main")
    return work


@pytest.fixture
def fx(repo, tmp_path, monkeypatch):
    """Everything faked: preflight clear, no flags, golden green; _run records and answers."""
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)
    s = {"cmds": [], "tags": "", "fail": None, "tagcalls": [], "golden": [], "flags": [], "pass": True, "claude": 0, "count": "0\t0\n", "subjects": {}}

    def fake_run(cmd, cwd=None, timeout=None):
        s["cmds"].append(cmd)
        j = " ".join(cmd)
        if s["fail"] and s["fail"] in j:
            return 1, "boom"
        if cmd[:3] == ["git", "tag", "-l"]:
            return 0, s["tags"]
        if cmd[:3] == ["git", "log", "-1"]:
            return 0, s["subjects"].get(cmd[-1], "")
        if cmd[:2] == ["git", "rev-parse"]:
            return 0, "abc1234\n"
        if cmd[:2] == ["git", "rev-list"]:
            return 0, s["count"]
        if cmd[:3] == ["gh", "repo", "view"]:
            return 0, "o/r\n"
        if cmd[:2] == ["claude", "plugin"]:
            return s["claude"], "claude: not found" if s["claude"] else ""
        return 0, ""

    def fake_cases(root):
        return [{"id": i} for i in ("small", "typical", "large")]

    def fake_gold(cases, src, out, rerun=True, timeout_s=5400, seal=None):
        s["golden"].append([c["id"] for c in cases])
        return [{"case": c["id"], "passed": s["pass"], "why": [] if s["pass"] else ["hidden tests red"]} for c in cases]

    monkeypatch.setattr(release, "_run", fake_run)
    monkeypatch.setattr(release, "preflight", lambda root, env: [])
    monkeypatch.setattr(release.batch_cost, "read_rows", lambda *a, **k: [])
    monkeypatch.setattr(release.scoreboard, "board", lambda rows, window=15: {"flags": s["flags"]})
    monkeypatch.setattr(release.golden_case, "cases", fake_cases)
    monkeypatch.setattr(release.golden, "run", fake_gold)
    monkeypatch.setattr(release.release_tag, "level", lambda cur, new: "minor" if new.endswith(".0") and not new.endswith(".0.0") else "major")
    monkeypatch.setattr(release.release_tag, "tag", lambda root, v, sha, push=True: s["tagcalls"].append((v, sha, push)) or "tag v1.6.0 created")
    import backlog_state as bs
    bs.update(bs.path(repo), lambda d: d.update({"repo": "o/r"}))  # the repo name `sl backlog` records and ships lock with
    s["root"] = str(repo)
    return s


def go(fx, *a):
    return release.main([*a, "--root", fx["root"]])


def kinds(fx, *prefix):
    return [c for c in fx["cmds"] if c[:len(prefix)] == list(prefix)]


def test_next_version_examples():
    assert release.next_version("1.5.244", "minor") == "1.6.0"
    assert release.next_version("1.5.244", "major") == "2.0.0"


def test_refuses_patch_level(fx, capsys):
    assert go(fx, "patch") == 2
    assert "patch versions are released by leads at ship" in capsys.readouterr().err
    assert not kinds(fx, "git")


def test_worker_refused(repo):
    assert release.preflight(repo, {"SUPERLITE_FLEET_WORKER": "W3"}) == [release.WORKER_MSG]


def test_preflight_clean(repo):
    assert release.preflight(repo, {}) == []


def test_preflight_behind(repo, tmp_path):
    other = tmp_path / "other"
    subprocess.run(["git", "clone", "-q", str(tmp_path / "origin.git"), str(other)], env=GIT_ENV, check=True)
    git(other, "config", "user.email", "t@t"); git(other, "config", "user.name", "t")
    (other / "f").write_text("x"); git(other, "add", "."); git(other, "commit", "-qm", "x"); git(other, "push", "-q", "origin", "main")
    assert "main is behind origin/main" in release.preflight(repo, {})


def test_dirty_tree_refused(repo, tmp_path, monkeypatch, capsys):
    monkeypatch.delenv("SUPERLITE_FLEET_WORKER", raising=False)
    (repo / "package.json").write_text("{}")
    assert any("package.json" in p for p in release.preflight(repo, {}))
    assert release.main(["minor", "--root", str(repo)]) == 2
    assert "package.json" in capsys.readouterr().err


def test_flags_need_accept(fx, capsys):
    fx["flags"] = ["lead_usd +50% (4.00 -> 6.00)"]
    assert go(fx, "minor") == 4
    assert "scoreboard flags: lead_usd +50% (4.00 -> 6.00); rerun with --accept-flags" in capsys.readouterr().err
    assert not kinds(fx, "git", "commit")
    assert go(fx, "minor", "--accept-flags") == 0


def test_level_sets(fx):
    assert go(fx, "minor") == 0
    assert go(fx, "major") == 0
    assert fx["golden"][0] == ["small", "typical"]
    assert fx["golden"][1] == ["small", "typical", "large"]


def test_golden_red_stops_before_bump(fx):
    fx["pass"] = False
    assert go(fx, "minor") == 1
    assert not kinds(fx, "bash") and not kinds(fx, "git", "commit") and not fx["tagcalls"] and not kinds(fx, "git", "push")


def test_step_order(fx):
    assert go(fx, "minor") == 0
    steps = [c for c in fx["cmds"] if c[0] in ("bash", "claude", "gh") or c[:2] in (["git", "commit"], ["git", "push"])]
    assert steps[0][0] == "bash" and steps[0][-2:] == [steps[0][1], "1.6.0"] and steps[0][1].endswith("scripts/bump-version.sh")
    assert steps[1:] == [
        ["claude", "plugin", "validate", "--strict", "."],
        ["git", "commit", "-am", "Release v1.6.0"],
        ["git", "push", "--atomic", "origin", "HEAD:main", "refs/tags/v1.6.0"],
        ["gh", "release", "create", "v1.6.0", "--generate-notes", "--title", "superlite 1.6.0"],
        ["git", "push", "origin", "v1.6.0^{commit}:refs/heads/stable"],
    ]
    assert fx["tagcalls"] == [("1.6.0", "abc1234", False)]
    i = fx["cmds"].index(["git", "commit", "-am", "Release v1.6.0"])
    assert ["git", "rev-parse", "HEAD"] in fx["cmds"][i:]


def test_notes_start_tag(fx, capsys):
    """#1042: notes start at the newest tag `sl release` made (commit `Release vX.Y.0`), else at the newest v* tag."""
    fx["tags"] = "v1.5.0\nv1.5.3\n"
    fx["subjects"] = {"refs/tags/v1.5.0": "Release v1.5.0\n"}
    assert go(fx, "minor") == 0
    assert kinds(fx, "gh")[0][-2:] == ["--notes-start-tag", "v1.5.0"]
    fx["tags"] = "v1.1.0\nv1.5.248\nv1.5.309\n"
    fx["subjects"] = {"refs/tags/v1.1.0": "Bump version to 1.1.0\n"}
    fx["cmds"].clear()
    assert go(fx, "minor") == 0
    assert kinds(fx, "gh")[0][-2:] == ["--notes-start-tag", "v1.5.309"]
    capsys.readouterr()
    assert go(fx, "minor", "--dry-run") == 0
    assert "release notes start at v1.5.309" in capsys.readouterr().out
    fx["tags"] = "v1.4.0\nv1.5.0\nv1.5.7\n"
    fx["subjects"] = {"refs/tags/v1.4.0": "Release v1.4.0", "refs/tags/v1.5.0": "Release v1.5.0"}
    fx["cmds"].clear()
    assert go(fx, "minor") == 0
    assert kinds(fx, "gh")[0][-2:] == ["--notes-start-tag", "v1.5.0"]
    fx["tags"] = "v1.5.3\nv1.6.0-rc1\nv2.0.0\n"
    fx["subjects"] = {}
    fx["cmds"].clear()
    assert go(fx, "minor") == 0
    assert kinds(fx, "gh")[0][-2:] == ["--notes-start-tag", "v1.5.3"]
    fx["tags"] = ""
    fx["cmds"].clear()
    assert go(fx, "minor") == 0
    assert "--notes-start-tag" not in kinds(fx, "gh")[0]


def test_notes_start_real_git(repo):
    """#1042: the commit subject is read through the annotated tag, as release_tag makes it."""
    git(repo, "tag", "-a", "v1.1.0", "-m", "superlite 1.1.0")
    git(repo, "commit", "-q", "--allow-empty", "-m", "Release v1.5.0")
    git(repo, "tag", "-a", "v1.5.0", "-m", "Version 1.5.0")
    git(repo, "commit", "-q", "--allow-empty", "-m", "fix: a patch; 1.5.3 (B1) (#7)")
    git(repo, "tag", "-a", "v1.5.3", "-m", "Version 1.5.3")
    assert release._notes_start(repo, ["v1.1.0", "v1.5.0", "v1.5.3"], "1.6.0") == "v1.5.0"
    assert release._notes_start(repo, ["v1.1.0", "v1.5.3"], "1.6.0") == "v1.5.3"
    assert release._notes_start(repo, [], "1.6.0") is None


def test_dry_run(fx, capsys):
    assert go(fx, "minor", "--dry-run") == 0
    assert "would release v1.6.0 (tag v1.6.0, stable -> v1.6.0)" in capsys.readouterr().out
    assert not kinds(fx, "bash") and not kinds(fx, "git", "commit") and not kinds(fx, "git", "push") and not fx["tagcalls"]
    assert fx["golden"] == [["small", "typical"]]


def test_dry_run_no_golden(fx, capsys):
    assert go(fx, "minor", "--dry-run", "--no-golden") == 0
    assert fx["golden"] == []
    assert go(fx, "minor", "--no-golden") == 2


def test_validate_missing_claude(fx, capsys):
    fx["claude"] = 127
    assert go(fx, "minor") == 0
    assert "validate: skipped (claude not found)" in capsys.readouterr().err
    assert kinds(fx, "git", "commit")


def test_push_failure_exit_3(fx, capsys):
    fx["fail"] = "git push --atomic origin HEAD:main"
    assert go(fx, "minor") == 3
    err = capsys.readouterr().err
    assert "undo: git reset --hard origin/main && git tag -d v1.6.0" in err and "is pushed" not in err
    assert not kinds(fx, "gh")


def test_main_moved_during_golden_refused(fx, capsys, monkeypatch):
    real = release._golden
    def moved(root, level):
        rc = real(root, level); fx["count"] = "0\t2\n"; return rc
    monkeypatch.setattr(release, "_golden", moved)
    assert go(fx, "minor") == 2
    assert "main moved during the golden run" in capsys.readouterr().err
    assert not kinds(fx, "bash") and not kinds(fx, "git", "commit") and not kinds(fx, "git", "push") and not fx["tagcalls"]
    fx["count"] = "0\t0\n"; monkeypatch.setattr(release, "_golden", real)
    assert go(fx, "minor") == 0  # lock was released


def test_stable_push_failure_is_warning(fx, capsys):
    fx["fail"] = "refs/heads/stable"
    assert go(fx, "minor") == 0
    assert "warning" in capsys.readouterr().err


def test_gh_failure_after_push_gives_no_reset_hint(fx, capsys):
    fx["fail"] = "gh release"
    assert go(fx, "minor") == 3
    err = capsys.readouterr().err
    assert "undo:" not in err and "v1.6.0 is pushed" in err
    assert not kinds(fx, "git", "push", "origin", "v1.6.0^{commit}:refs/heads/stable")


def test_existing_tag_refused(fx):
    fx["tags"] = "v1.6.0\n"
    assert go(fx, "minor") == 2 and not kinds(fx, "bash")


def _row(i, usd):
    return {"row": "batch", "batch": f"B{i}", "end": "shipped", "lead": {"cost_usd": usd, "turns": 10}}


def test_real_scoreboard_rows_flag(fx, monkeypatch, capsys):
    monkeypatch.setattr(release.scoreboard, "board", REAL_BOARD)
    monkeypatch.setattr(release.batch_cost, "read_rows", REAL_READ)
    d = os.path.join(fx["root"], ".superlite"); os.makedirs(d, exist_ok=True)
    rows = [_row(i, 4.0 if i < 15 else 6.0) for i in range(30)]
    open(os.path.join(d, "batch-costs.jsonl"), "w").write("\n".join(json.dumps(r) for r in rows) + "\n")
    assert go(fx, "minor") == 4
    assert "scoreboard flags: lead_usd +50%" in capsys.readouterr().err


def test_golden_rerun_pass_is_green(fx, monkeypatch):
    def gold(cases, src, out, rerun=True, timeout_s=5400, seal=None):
        rows = []
        for c in cases:
            if c["id"] == "small":
                rows.append({"row": "golden", "case": "small", "attempt": 1, "passed": False, "why": ["timeout"]})
                rows.append({"row": "golden", "case": "small", "attempt": 2, "passed": True, "why": []})
            else:
                rows.append({"row": "golden", "case": c["id"], "attempt": 1, "passed": True, "why": []})
        return rows
    monkeypatch.setattr(release.golden, "run", gold)
    assert go(fx, "minor") == 0


def test_tag_status_failure_exit_3(fx, monkeypatch, capsys):
    monkeypatch.setattr(release.release_tag, "tag", lambda root, v, sha, push=True: "tag v1.6.0 failed: boom")
    assert go(fx, "minor") == 3
    assert not kinds(fx, "git", "push")
    assert "undo: git reset --hard origin/main && git tag -d v1.6.0" in capsys.readouterr().err


def _held(fx, tmp_path, state_repo="o/r"):
    """The ship lock held by a lead's batch under the key backlog_ship uses: lock_path(backlog.json repo)."""
    import backlog_state as bs, ship_lock
    root = Path(fx["root"])
    bs.update(bs.path(root), lambda d: d.update({"repo": state_repo}))
    lock = ship_lock.lock_path(bs.load(bs.path(root))["repo"], tmp_path / "home")
    assert ship_lock.acquire(lock, {"batch": "B7", "lead": "W7", "agent": None}, None, int(time.time() * 1000))["acquired"]
    return lock


def test_release_refuses_under_the_lock_a_lead_ship_holds(fx, tmp_path, capsys):
    lock = _held(fx, tmp_path)
    assert go(fx, "minor") == 2
    assert "ship lock held by B7" in capsys.readouterr().err
    assert not fx["golden"] and not kinds(fx, "bash") and not kinds(fx, "git", "commit") and not kinds(fx, "git", "push") and not fx["tagcalls"]
    import ship_lock
    assert ship_lock.holder(lock)["batch"] == "B7"
    ship_lock.release(lock, "B7")
    assert go(fx, "minor") == 0  # same key: free again, and the refused run left no queue entry behind
