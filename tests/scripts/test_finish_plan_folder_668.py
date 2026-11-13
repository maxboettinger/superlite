"""#668: finish resolves a run folder, counts an inline run's branch commits and rulings, and takes a green CI run as the full run."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import finish  # noqa: E402
import history  # noqa: E402
import plan_tools  # noqa: E402


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout.strip()


def commit(cwd, name, msg):
    p = Path(cwd) / name
    p.write_text(msg + "\n", encoding="utf-8")
    git(cwd, "add", "-A")
    git(cwd, "commit", "-q", "-m", msg)


def repo(tmp_path, branch="main"):
    top = tmp_path.resolve() / "repo"
    top.mkdir()
    git(top, "init", "-q", "-b", "main")
    git(top, "config", "user.name", "t")
    git(top, "config", "user.email", "t@t")
    commit(top, "a.txt", "init")
    if branch != "main":
        git(top, "checkout", "-q", "-b", branch)
    sd = top / ".superlite"
    sd.mkdir()
    (sd / "prime.md").write_text("prime\n", encoding="utf-8")
    (sd / "progress.md").write_text("", encoding="utf-8")
    (top / ".git" / "info" / "exclude").write_text(".superlite/\n", encoding="utf-8")
    return top, sd


@pytest.fixture(autouse=True)
def quiet(monkeypatch):
    monkeypatch.setattr(finish, "drop_trees", lambda sd: None)
    monkeypatch.setattr(finish, "log_auto", lambda *a, **k: 0)


def run_finish(capsys, monkeypatch, top, *args):
    monkeypatch.chdir(top)
    assert finish.main(list(args)) == 0
    return capsys.readouterr().out


def fake_gh(tmp_path, monkeypatch, runs, rc=0):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    (tmp_path / "gh.json").write_text(json.dumps(runs), encoding="utf-8")
    gh = bindir / "gh"
    gh.write_text(f"#!/bin/sh\ntouch '{tmp_path}/gh-ran'\ncat '{tmp_path}/gh.json'\nexit {rc}\n", encoding="utf-8")
    gh.chmod(0o755)
    monkeypatch.setenv("PATH", f"{bindir}{os.pathsep}{os.environ['PATH']}")
    return tmp_path / "gh-ran"


def gh_run(i, conclusion="success", status="completed"):
    return {"databaseId": i, "workflowName": "ci", "name": "ci", "status": status, "conclusion": conclusion,
            "url": f"https://example.invalid/r/{i}"}


def pushed_repo(tmp_path):
    top, sd = repo(tmp_path)
    remote = tmp_path / "remote.git"
    git(tmp_path, "init", "-q", "--bare", str(remote))
    git(top, "remote", "add", "origin", str(remote))
    git(top, "push", "-q", "-u", "origin", "main")
    return top, sd


def test_folder_plan_reaches_history(tmp_path, monkeypatch, capsys):
    top, sd = repo(tmp_path)
    plan = top / "docs" / "plans" / "p.md"
    plan.parent.mkdir(parents=True)
    plan.write_text("# p\n", encoding="utf-8")
    (sd / "stable.json").write_text(json.dumps({"plan": "docs/plans/p.md"}), encoding="utf-8")
    (sd / "metrics.jsonl").write_text("", encoding="utf-8")
    seen = []
    monkeypatch.setattr(history, "record_run", lambda p, d, *a: seen.append(p) or [])
    out = run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    assert len(seen) == 1 and Path(seen[0]).resolve() == plan.resolve()
    assert "plan not found" not in out and "history: 0 rows appended" in out


def test_inline_run_counts_branch_commits(tmp_path, monkeypatch, capsys):
    top, sd = repo(tmp_path, "feat")
    base = git(top, "rev-parse", "main")
    commit(top, "b.txt", "fix a")
    commit(top, "c.txt", "fix b")
    shas = git(top, "log", "--reverse", "--format=%H", "main..HEAD").split()
    (sd / "spec.md").write_text("# spec\nRuling: one\n- Ruling: two\n", encoding="utf-8")
    out = run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    assert f"commits: 2 (branch commits since {base[:10]}, inline run)" in out
    lines = out.splitlines()
    assert lines.index(f"- {shas[-2][:10]} fix a") < lines.index(f"- {shas[-1][:10]} fix b")
    assert "rulings: 2" in out and "- one" in out and "- two" in out
    assert "history: no plan document (inline run); nothing recorded" in out


def test_inline_commits_and_rulings_helpers(tmp_path):
    top, sd = repo(tmp_path, "feat")
    base = git(top, "rev-parse", "main")
    commit(top, "b.txt", "fix a")
    got = finish.inline_commits(sd)
    assert got[0] == base and [s for _, s in got[1]][-1] == "fix a"
    (sd / "spec.md").write_text("Ruling: x\n- Ruling: y\n", encoding="utf-8")
    assert finish.spec_rulings(sd) == ["x", "y"]
    assert finish.spec_rulings(tmp_path / "none") == []


def test_ledger_commits_win(tmp_path, monkeypatch, capsys):
    top, sd = repo(tmp_path, "feat")
    commit(top, "b.txt", "fix a")
    (sd / "progress.md").write_text("- commit T1 abcdef1234 x\n", encoding="utf-8")
    out = run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    assert "commits: 1" in out and "branch commits since" not in out


def test_ci_green_is_full_run(tmp_path, monkeypatch, capsys):
    top, sd = pushed_repo(tmp_path)
    fake_gh(tmp_path, monkeypatch, [gh_run(7), gh_run(8)])
    sha = git(top, "rev-parse", "HEAD")
    out = run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    head = f"tests (full, CI): ci run 7 and 1 more green on HEAD {sha[:10]} (https://example.invalid/r/7)"
    assert head in out
    (sd / "progress.md").write_text("- tests fast passed=3 failed=0 skipped=0 seconds=1.0\n", encoding="utf-8")
    lines = run_finish(capsys, monkeypatch, top, "--plan", str(sd)).splitlines()
    i = lines.index(head)
    assert lines[i + 1] == "- local fast run (not the run's result): 3 passed, 0 failed, 0 skipped in 1.0s"


def test_ci_single_run_text(tmp_path, monkeypatch, capsys):
    top, sd = pushed_repo(tmp_path)
    fake_gh(tmp_path, monkeypatch, [gh_run(7)])
    sha = git(top, "rev-parse", "HEAD")
    r = finish.ci_full_run(top, sha)
    assert r == {"name": "ci", "id": 7, "url": "https://example.invalid/r/7", "more": 0}


def test_ci_not_green_or_not_asked(tmp_path, monkeypatch, capsys):
    top, sd = pushed_repo(tmp_path)
    marker = fake_gh(tmp_path, monkeypatch, [gh_run(7, "failure")])
    assert "(full, CI)" not in run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    assert marker.exists()
    marker.unlink()
    fake_gh(tmp_path, monkeypatch, [gh_run(7)])
    (top / "a.txt").write_text("dirty\n", encoding="utf-8")  # a tracked change
    assert "(full, CI)" not in run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    assert not marker.exists()
    git(top, "checkout", "--", "a.txt")
    commit(top, "n.txt", "unpushed")
    assert "(full, CI)" not in run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    assert not marker.exists()
    git(top, "push", "-q")
    (sd / "progress.md").write_text("- tests full passed=3 failed=0 skipped=0 seconds=1.0\n", encoding="utf-8")
    out = run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    assert "(full, CI)" not in out and "tests (full): 3 passed" in out
    assert not marker.exists()


def test_ci_gh_failing_prints_no_ci_line(tmp_path, monkeypatch, capsys):
    top, sd = pushed_repo(tmp_path)
    marker = fake_gh(tmp_path, monkeypatch, [gh_run(7)], rc=1)
    assert "(full, CI)" not in run_finish(capsys, monkeypatch, top, "--plan", str(sd))
    assert marker.exists()


def test_history_cli_folder_without_plan_exits_2(tmp_path, capsys):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    assert history.main(["write", "--plan", str(sd)]) == 2
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1 and err[0].startswith("error:")
    assert issubclass(plan_tools.PlanError, Exception)
