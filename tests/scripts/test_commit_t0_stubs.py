"""commit_task: T0 commits the stub files recorded in wave0.json while their owner has not committed (#198)."""
from __future__ import annotations

import json
import subprocess

from test_plan_tools import run
from test_wave0 import COMMIT, TS, plan

W0 = {"id": "T0", "synthetic": True, "title": "Wave 0 skeleton", "owns": ["package.json"], "stubs": ["src/slug.ts"], "wait": ["T1"]}


def setup(tmp_path, w0=W0, ledger="", pool=None):
    def git(*a):
        subprocess.run(["git", *a], cwd=tmp_path, check=True, capture_output=True)
    git("init", "-q")
    git("config", "user.email", "t@t")
    git("config", "user.name", "t")
    p = plan(tmp_path, "**Tech stack:** TypeScript", "x", TS)
    sl = tmp_path / ".superlite"
    (sl / "briefs").mkdir(parents=True, exist_ok=True)
    (sl / "briefs" / "wave0.json").write_text(json.dumps(w0), encoding="utf-8")
    if ledger:
        (sl / "progress.md").write_text(ledger, encoding="utf-8")
    if pool is not None:
        (sl / "pool.json").write_text(json.dumps(pool), encoding="utf-8")
    (tmp_path / "package.json").write_text("{}", encoding="utf-8")
    (tmp_path / "src").mkdir()
    (tmp_path / "src" / "slug.ts").write_text("export {}\n", encoding="utf-8")
    (tmp_path / "src" / "feed.ts").write_text("// T2\n", encoding="utf-8")
    return p


def committed(tmp_path, p, tid="T0"):
    cp = run(COMMIT, tid, "--plan", p, cwd=tmp_path)
    assert cp.returncode == 0, cp.both
    return sorted(subprocess.run(["git", "show", "--name-only", "--format=", "HEAD"], cwd=tmp_path, capture_output=True, text=True).stdout.split())


def test_t0_commits_stub_of_uncommitted_owner(tmp_path):
    assert committed(tmp_path, setup(tmp_path)) == ["package.json", "src/slug.ts"]


def test_t0_commits_stub_while_owner_busy(tmp_path):
    p = setup(tmp_path, pool={"agents": [{"id": "a1", "busy": True, "current": "T1", "tasks": []}]})
    assert committed(tmp_path, p) == ["package.json", "src/slug.ts"]


def test_t0_leaves_stub_of_committed_owner(tmp_path):
    p = setup(tmp_path, ledger="- commit T1 abcdef1234 slug\n")
    assert committed(tmp_path, p) == ["package.json"]


def test_wave0_json_without_stubs_keeps_old_rule(tmp_path):
    p = setup(tmp_path, w0={k: v for k, v in W0.items() if k != "stubs"})
    assert committed(tmp_path, p) == ["package.json"]


def test_other_task_ignores_stub_record(tmp_path):
    p = setup(tmp_path)
    assert committed(tmp_path, p, "T2") == ["src/feed.ts"]


def test_t0_recommit_leaves_stub_of_building_owner(tmp_path):
    p = setup(tmp_path, ledger="- commit T0 abcdef1234 skeleton\n")
    assert committed(tmp_path, p) == ["package.json"]
