# tests/scripts/test_golden_seal.py
import json
import os
import subprocess
import sys
import types
from pathlib import Path

import pytest
from test_backlog_run import bk, put, run, get, bs  # noqa: F401
from backlog_fixtures import batch as b
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import golden_seal as gs  # noqa: E402

ENV = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}


def git(cwd, *a):
    return subprocess.run(["git", *a], cwd=cwd, env=ENV, capture_output=True, text=True, check=True).stdout.strip()


@pytest.fixture(autouse=True)
def _env(monkeypatch):
    for k in ("SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR", "SUPERLITE_FLEET_WORKER", "SUPERLITE_STATE_DIR"):
        monkeypatch.delenv(k, raising=False)
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        monkeypatch.delenv(k, raising=False)


@pytest.fixture(autouse=True)
def _gh_folder_gone():  # tests that reach _env leave no golden-gh-* folder in the system temp folder
    yield
    gs._drop_gh()


@pytest.fixture
def repo(tmp_path):
    r = tmp_path / "src"
    r.mkdir()
    git(r, "init", "-q", "-b", "trunk")
    git(r, "config", "user.email", "a@b.c")
    git(r, "config", "user.name", "t")
    (r / "a.txt").write_text("1")
    git(r, "add", "-A")
    git(r, "commit", "-q", "-m", "base")
    base = git(r, "rev-parse", "HEAD")
    (r / "a.txt").write_text("2")
    git(r, "commit", "-qam", "later")
    return r, base


def case_for(base):
    return {"id": "small", "topic": "golden-small", "base": base, "issues": [{"number": 866, "title": "t", "body": "b"}]}


def test_seal_no_remote(repo, tmp_path):
    r, base = repo
    c = gs.seal(case_for(base), r, tmp_path / "w")
    assert c == tmp_path / "w" / "small"
    assert git(c, "remote") == ""
    assert git(c, "rev-parse", "HEAD") == base
    assert git(c, "branch", "--show-current") == "main"


def test_seal_existing_dir(repo, tmp_path):
    r, base = repo
    c = gs.seal(case_for(base), r, tmp_path / "w")
    (c / "junk.txt").write_text("x")
    c2 = gs.seal(case_for(base), r, tmp_path / "w")
    assert c2 == c and not (c / "junk.txt").exists()


def test_seal_state(repo, tmp_path):
    r, base = repo
    c = gs.seal(case_for(base), r, tmp_path / "w")
    d = json.loads((c / ".superlite" / "backlog.json").read_text())
    assert d["repo"] == "" and d["approved_ship"] is None
    assert d["sealed"] == {"issue_dir": str(c / ".superlite" / "golden" / "issues")}
    assert d["titles"] == {"866": "t"}
    assert d["batches"] == [{"id": "B1", "topic": "golden-small", "issues": [866], "state": "planned", "files": []}]


def test_seal_issue_files(repo, tmp_path):
    r, base = repo
    c = gs.seal(case_for(base), r, tmp_path / "w")
    t = (c / ".superlite" / "golden" / "issues" / "866.md").read_text()
    assert t.startswith("# t\n") and "b" in t


def test_seal_copies_test_cmd(repo, tmp_path):
    r, base = repo
    (r / ".superlite").mkdir()
    (r / ".superlite" / "test-cmd.json").write_text('{"cmd": "x"}')
    c = gs.seal(case_for(base), r, tmp_path / "w")
    assert (c / ".superlite" / "test-cmd.json").read_text() == '{"cmd": "x"}'


BATCH = {"id": "B1", "topic": "golden-small", "issues": [866], "files": []}
CTX = {"sl": "/p/sl", "backlog_md": "/p/backlog.md", "repo": "", "approved": None, "titles": {"866": "t"}, "summaries": [], "resume": False}


def test_brief_frozen_issues():
    t = bb.lead_brief(BATCH, {**CTX, "issue_dir": "/c/issues"})
    assert "Issues (sealed run without GitHub: read each issue from /c/issues/<n>.md; gh does not work here):" in t
    assert "gh issue view" not in t and "Ship: NOT approved" in t


def test_brief_unchanged_without_issue_dir():
    t = bb.lead_brief(BATCH, CTX)
    assert "gh issue view" in t and "sealed run" not in t
    assert bb.lead_brief(BATCH, {**CTX, "issue_dir": None}) == t


def test_start_unsealed_still_refused(bk, capsys):
    put(bk, b("B1", ["a.py"]), approved=None)
    assert run(capsys, "start") == (2, "BLOCKED: no ship approval yet (sl backlog decide --print)\n")


def test_start_sealed_passes_gate(bk, capsys, monkeypatch):
    seen = []
    monkeypatch.setitem(sys.modules, "backlog_brief", types.SimpleNamespace(lead_brief=lambda batch, ctx: seen.append(ctx.get("issue_dir")) or "brief", pick_summaries=lambda batch, shipped: ([], 0)))
    put(bk, b("B1", ["a.py"]), approved=None)
    issues = bk.root / ".superlite" / "golden" / "issues"
    bs.update(bs.path(bk.root), lambda d: d.update({"sealed": {"issue_dir": str(issues)}}))
    rc, out = run(capsys, "start")
    assert rc == 0 and "no ship approval" not in out and "B1 running lead=W1" in out
    assert seen == [str(issues)]


def fake(monkeypatch, rc, out, calls=None):
    def _run(cmd, cwd=None, timeout=None):
        if calls is not None:
            calls.append((cmd, cwd, timeout))
        return rc, out
    monkeypatch.setattr(gs, "_run", _run)


def test_start_parses(monkeypatch, tmp_path):
    line = "B1 running lead=W1 worktree=/t/small/.claude/worktrees/superlite-b1-golden-small"
    calls = []
    fake(monkeypatch, 0, line, calls)
    assert gs.start(tmp_path) == {"ok": True, "lead": "W1", "out": line}
    assert calls[0][0][-2:] == ["start", "B1"] and calls[0][1] == tmp_path
    gs.start(tmp_path, "C")
    assert calls[1][0][-2:] == ["--config", "C"]
    fake(monkeypatch, 2, "BLOCKED: B1 lead did not start")
    assert gs.start(tmp_path) == {"ok": False, "lead": None, "out": "BLOCKED: B1 lead did not start"}


def test_wait_parses(monkeypatch, tmp_path):
    calls = []
    fake(monkeypatch, 0, "B1 parked: BLOCKED (ship not approved)", calls)
    assert gs.wait(tmp_path) == {"state": "parked", "reason": "BLOCKED (ship not approved)"}
    assert calls[0][0][-3:] == ["wait", "--timeout", "5400"]
    fake(monkeypatch, 0, "TIMEOUT")
    assert gs.wait(tmp_path, 1) == {"state": "timeout", "reason": ""}
    fake(monkeypatch, 124, "timeout")
    assert gs.wait(tmp_path, 1)["state"] == "timeout"
    fake(monkeypatch, 0, "B1 needs_decision question=Which?")
    assert gs.wait(tmp_path) == {"state": "needs_decision", "reason": "Which?"}


def test_row_last_batch_row(tmp_path):
    assert gs.row(tmp_path) is None
    sd = tmp_path / ".superlite"
    sd.mkdir()
    rows = [{"row": "batch", "batch": "B1", "n": 1}, {"row": "other"}, {"row": "batch", "batch": "B1", "n": 2}]
    (sd / "batch-costs.jsonl").write_text("\n".join(json.dumps(x) for x in rows) + "\nnot json\n")
    assert gs.row(tmp_path)["n"] == 2


def test_worktree_from_state(tmp_path):
    assert gs.worktree(tmp_path) is None
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "backlog.json").write_text(json.dumps({"batches": [{"id": "B1", "worktree": "/t/wt"}]}))
    assert gs.worktree(tmp_path) == Path("/t/wt")


def test_cleanup_missing_dir(monkeypatch, tmp_path):
    calls = []
    fake(monkeypatch, 0, "", calls)
    gs.cleanup(tmp_path / "gone")
    assert calls == []


def test_cleanup_removes(monkeypatch, tmp_path):
    calls = []
    fake(monkeypatch, 0, "", calls)
    (tmp_path / "c").mkdir()
    gs.cleanup(tmp_path / "c")
    assert not (tmp_path / "c").exists() and calls[0][0][-4:-2] == ["stop", "--all"] and calls[0][0][-5].endswith("fleet.py")
    assert calls[0][0][-2:] == ["--plan", str(tmp_path / "c" / ".superlite")]


def test_seal_scrubs_later_history(repo, tmp_path):
    r, base = repo
    later = git(r, "rev-parse", "HEAD")
    git(r, "tag", "v-later")
    c = gs.seal(case_for(base), r, tmp_path / "w")
    assert git(c, "for-each-ref", "--format=%(refname)") == "refs/heads/main"
    assert subprocess.run(["git", "cat-file", "-e", later], cwd=c, env=ENV).returncode != 0


def test_run_env_drops_caller_state(monkeypatch, tmp_path):
    monkeypatch.setenv("SUPERLITE_STATE_DIR", "/main/.superlite")
    monkeypatch.setenv("GH_TOKEN", "x")
    monkeypatch.setenv("KEEP_ME", "1")
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw["env"])
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(gs.subprocess, "run", fake_run)
    gs._run(["true"], cwd=tmp_path)
    assert "SUPERLITE_STATE_DIR" not in seen and "GH_TOKEN" not in seen and seen["KEEP_ME"] == "1"


def test_run_env_has_no_gh_login(monkeypatch, tmp_path):
    for k in ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST"):
        monkeypatch.setenv(k, "x")
    monkeypatch.setenv("GH_CONFIG_DIR", "/home/me/.config/gh")
    seen = {}

    def fake_run(cmd, **kw):
        seen.update(kw["env"])
        seen["_existed_empty"] = Path(kw["env"]["GH_CONFIG_DIR"]).is_dir() and not any(Path(kw["env"]["GH_CONFIG_DIR"]).iterdir())
        return types.SimpleNamespace(returncode=0, stdout="", stderr="")
    monkeypatch.setattr(gs.subprocess, "run", fake_run)
    gs._run(["true"], cwd=tmp_path)
    gone = ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN", "GH_HOST")
    assert not any(k in seen for k in gone)
    assert seen["GH_CONFIG_DIR"] != "/home/me/.config/gh" and seen["_existed_empty"]
    gs.cleanup(tmp_path / "none")
    assert not Path(seen["GH_CONFIG_DIR"]).exists()


def test_lead_cost_live(monkeypatch, tmp_path):
    assert gs.lead_cost(tmp_path) == 0.0
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "backlog.json").write_text(json.dumps({"batches": [{"id": "B1", "lead": "W1"}]}))
    bc = types.SimpleNamespace(build_row=lambda root, batch, end: {"lead": {"cost_usd": 2.5}} if batch["id"] == "B1" else {})
    monkeypatch.setitem(sys.modules, "batch_cost", bc)
    assert gs.lead_cost(tmp_path) == 2.5


def test_run_output_not_utf8_does_not_raise():
    code, out = gs._run([sys.executable, "-c", "import sys; sys.stdout.buffer.write(b'a\\xff\\xfeb')"])
    assert code == 0 and out.startswith("a") and out.endswith("b")


def test_gh_config_folder_goes_with_cleanup_and_exit(tmp_path, monkeypatch):
    monkeypatch.setenv("TMPDIR", str(tmp_path))
    monkeypatch.setattr(gs.tempfile, "tempdir", None)
    monkeypatch.setattr(gs, "_GH_DIR", [])
    monkeypatch.setattr(gs, "_EXIT", [])
    registered = []
    monkeypatch.setattr(gs.atexit, "register", lambda fn, *a: registered.append(fn))
    d = Path(gs._env()["GH_CONFIG_DIR"])
    assert d.is_dir() and d.parent == tmp_path
    assert registered == [gs._drop_gh]  # removed at exit as well, once per process
    gs._env()
    assert registered == [gs._drop_gh]
    gs.cleanup(tmp_path / "gone")  # a clone that never existed still drops the folder
    assert not d.exists() and list(tmp_path.glob("golden-gh-*")) == []
    d2 = Path(gs._env()["GH_CONFIG_DIR"])
    assert d2.is_dir()
    registered[0]()  # the exit hook
    assert not d2.exists()


def test_patch_names_changed_and_new_files(repo, tmp_path):
    r, base = repo
    c = gs.seal(case_for(base), r, tmp_path / "w")
    (c / "a.txt").write_text("changed")
    (c / "new.txt").write_text("fresh")
    (c / ".superlite" / "state.json").write_text("{}")
    git(c, "config", "user.email", "a@b.c")
    out = gs.patch(c, base)
    assert "a/a.txt" in out and "changed" in out and "new.txt" in out and "fresh" in out
    assert ".superlite" not in out
    assert git(c, "status", "--porcelain", "--", "new.txt").startswith("??")  # the clone's own index stays untouched


def test_patch_of_a_linked_worktree(repo, tmp_path):
    r, base = repo
    c = gs.seal(case_for(base), r, tmp_path / "w")
    git(c, "config", "user.email", "a@b.c")
    git(c, "config", "user.name", "t")
    wt = tmp_path / "linked"
    git(c, "worktree", "add", "--detach", str(wt), base)
    (wt / "a.txt").write_text("changed")
    (wt / "new.txt").write_text("fresh")
    (wt / ".superlite").mkdir()
    (wt / ".superlite" / "state.json").write_text("{}")
    out = gs.patch(wt, base)
    assert "a/a.txt" in out and "changed" in out and "new.txt" in out and "fresh" in out
    assert ".superlite" not in out


@pytest.mark.parametrize("ignored", [True, False])
def test_patch_keeps_superlite_out_ignored_or_not(repo, tmp_path, ignored):
    r, base = repo
    c = gs.seal(case_for(base), r, tmp_path / "w")
    git(c, "config", "user.email", "a@b.c")
    git(c, "config", "user.name", "t")
    wt = tmp_path / "linked"
    git(c, "worktree", "add", "--detach", str(wt), base)
    if ignored:  # commit_task lists .superlite in the common dir's info/exclude
        common = Path(git(wt, "rev-parse", "--git-common-dir"))
        common = common if common.is_absolute() else wt / common
        (common / "info").mkdir(exist_ok=True)
        with (common / "info" / "exclude").open("a") as f:
            f.write(".superlite\n")
    (wt / "a.txt").write_text("changed")
    (wt / "new.txt").write_text("fresh")
    (wt / ".superlite").mkdir()
    (wt / ".superlite" / "x.json").write_text("{}")
    out = gs.patch(wt, base)
    assert "a/a.txt" in out and "changed" in out and "new.txt" in out and "fresh" in out
    assert ".superlite" not in out


def test_patch_error_names_the_failed_git_step(tmp_path):
    assert gs.patch(tmp_path / "missing", "deadbeef") == ""
    assert gs.patch_error(tmp_path / "missing")
    (tmp_path / "plain").mkdir()
    assert gs.patch(tmp_path / "plain", "deadbeef") == ""
    assert gs.patch_error(tmp_path / "plain").strip()


def test_patch_git_failure_gives_empty_string(tmp_path):
    assert gs.patch(tmp_path / "missing", "deadbeef") == ""
    (tmp_path / "plain").mkdir()
    assert gs.patch(tmp_path / "plain", "deadbeef") == ""


def test_patch_capped_at_two_mb(repo, tmp_path):
    r, base = repo
    c = gs.seal(case_for(base), r, tmp_path / "w")
    (c / "big.txt").write_text("y" * 3_000_000)
    out = gs.patch(c, base)
    assert len(out.encode()) <= 2 * 1024 * 1024 + 10 and out.rstrip().endswith("... cut")


def _lead_wt(tmp_path, summaries):
    wt = tmp_path / "wt"
    (wt / ".superlite").mkdir(parents=True)
    clone = tmp_path / "clone"
    (clone / ".superlite").mkdir(parents=True)
    (clone / ".superlite" / "backlog.json").write_text(json.dumps({"batches": [{"id": "B1", "worktree": str(wt)}]}))
    for i, (name, data) in enumerate(summaries):
        f = wt / ".superlite" / name
        f.write_text(json.dumps(data) if isinstance(data, dict) else data)
        os.utime(f, (1000 + i, 1000 + i))
    return clone


def test_suite_reads_newest_full_summary(tmp_path):
    clone = _lead_wt(tmp_path, [
        ("test-summary-a.json", {"mode": "full", "passed": 5, "failed": 1}),
        ("test-summary-b.json", {"mode": "full", "passed": 9, "failed": 0, "seconds": 3}),
        ("test-summary.json", {"mode": "fast", "passed": 1, "failed": 0}),
        ("test-summary-c.json", "{torn"),
    ])
    assert gs.suite(clone) == {"passed": 9, "failed": 0}


def test_suite_none_without_full_summary(tmp_path):
    assert gs.suite(tmp_path / "nowhere") is None
    clone = _lead_wt(tmp_path, [("test-summary.json", {"mode": "fast", "passed": 1, "failed": 0}),
                                ("test-summary-x.json", {"mode": "recorded", "passed": 1, "failed": 0})])
    assert gs.suite(clone) is None


def test_suite_finds_archived_run_summary(tmp_path):
    clone = _lead_wt(tmp_path, [("test-summary.json", {"mode": "fast", "passed": 1, "failed": 0})])
    arch = clone / ".superlite" / "runs" / "x"
    arch.mkdir(parents=True)
    f = arch / "test-summary-old.json"
    f.write_text(json.dumps({"mode": "full", "passed": 7, "failed": 0}))
    os.utime(f, (500, 500))  # older than the newer fast summary in the worktree
    assert gs.suite(clone) == {"passed": 7, "failed": 0}
    newer = clone / ".superlite" / "runs" / "y"
    newer.mkdir()
    g = newer / "test-summary-new.json"
    g.write_text(json.dumps({"mode": "full", "passed": 8, "failed": 2}))
    os.utime(g, (2000, 2000))
    assert gs.suite(clone) == {"passed": 8, "failed": 2}
