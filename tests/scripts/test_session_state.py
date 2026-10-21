"""PIX-837: one .superlite per session. Two sessions launched from one checkout, each building in its own
worktree, never share a gate, a reply log or run markers; `sl orchestrator end` stops the guard after a run."""
from __future__ import annotations

import json
import os
import shutil
import subprocess
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import state  # noqa: E402

ROOT = SCRIPTS.parents[2]
GUARD = ROOT / "hooks" / "block-coordinator-edits"
REPLY = ROOT / "hooks" / "record-human-reply"
ORCH = SCRIPTS / "orchestrator.py"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")
A, B = "aaaa-1111", "bbbb-2222"


@pytest.fixture
def repo(tmp_path):
    """A main checkout with two linked worktrees (`.git` is a file there, as git writes it)."""
    main = tmp_path / "main"
    (main / ".git").mkdir(parents=True)
    trees = {}
    for name in ("wa", "wb"):
        w = main / ".claude" / "worktrees" / name
        (w / "docs" / "superpowers" / "plans").mkdir(parents=True)
        (w / ".git").write_text(f"gitdir: {main}/.git/worktrees/{name}\n")
        trees[name] = w
    return main, trees["wa"], trees["wb"]


def review(w, name="x"):
    f = w / "docs" / "superpowers" / "plans" / f"{name}.review.md"
    f.write_text("# Review\n\nplan\n")
    os.utime(f, (f.stat().st_mtime - 60, f.stat().st_mtime - 60))  # replies come later
    return f


def sl(cwd, sid, *args):
    env = dict(os.environ, PYTHONIOENCODING="utf-8")
    if sid:
        env["CLAUDE_CODE_SESSION_ID"] = sid
    return subprocess.run([sys.executable, str(ORCH), *map(str, args)], capture_output=True, text=True,
                          cwd=cwd, env=env, timeout=60)


def hook(script, launch, sid, payload):
    raw = json.dumps({"session_id": sid, "cwd": str(launch), **payload})
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(launch))
    return subprocess.run([BASH, str(script)], input=raw, capture_output=True, text=True, env=env)


def prompt(launch, sid, text):
    return hook(REPLY, launch, sid, {"prompt": text, "hook_event_name": "UserPromptSubmit"})


def write(launch, sid, path):
    return hook(GUARD, launch, sid, {"tool_name": "Write", "tool_input": {"file_path": str(path)}})


def dispatch(launch, sid, cwd):
    return hook(GUARD, launch, sid, {"tool_name": "Bash", "tool_input": {"command": f"cd {cwd} && sl dispatch --plan p.md"}})


# ------------------------------------------------------------------ state.py

def test_plan_in_worktree_resolves_to_its_toplevel(repo):
    main, wa, _ = repo
    plan = wa / "docs" / "superpowers" / "plans" / "p.md"
    assert state.plan_dir(plan) == wa.resolve() / ".superlite"
    assert state.plan_dir(main / "docs" / "plans" / "p.md") == main.resolve() / ".superlite"


def test_outside_git_keeps_the_old_rule(tmp_path):
    (tmp_path / "docs" / "plans").mkdir(parents=True)
    assert state.plan_dir(tmp_path / "docs" / "plans" / "p.md") == tmp_path.resolve() / ".superlite"
    assert state.plan_dir(tmp_path / "p.md") == tmp_path.resolve() / ".superlite"
    assert state.plan_dir(tmp_path / ".superlite") == tmp_path.resolve() / ".superlite"


def test_resolve_order_env_binding_cwd(repo, monkeypatch):
    main, wa, wb = repo
    monkeypatch.chdir(main)
    assert state.resolve() == Path(".superlite")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", A)
    assert state.bind(wa / ".superlite") == A
    assert state.resolve() == wa.resolve() / ".superlite"
    assert state.owner(wa / ".superlite") == A
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(wb / ".superlite"))
    assert state.resolve() == wb / ".superlite"
    assert state.resolve(main / "p.md") == main.resolve() / ".superlite"  # an explicit plan wins


def test_rebinding_releases_the_old_folder_and_unbind_keeps_others(repo, monkeypatch):
    _, wa, wb = repo
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", A)
    state.bind(wa / ".superlite")
    state.bind(wb / ".superlite")
    assert state.owner(wa / ".superlite") is None and state.owner(wb / ".superlite") == A
    state.unbind(wb / ".superlite", sid=B)  # another session never takes A's folder
    assert state.owner(wb / ".superlite") == A and state.bound(A) == wb.resolve() / ".superlite"
    state.unbind(wb / ".superlite")
    assert state.owner(wb / ".superlite") is None and state.bound(A) is None


def test_no_session_id_binds_nothing(repo):
    _, wa, _ = repo
    assert state.bind(wa / ".superlite") is None
    assert not (wa / ".superlite" / "session").exists()


def test_bad_session_ids_are_ignored(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", "../../etc")
    assert state.session_id() is None


def test_stale_bindings_are_pruned(repo, monkeypatch):
    _, wa, _ = repo
    old = state.home() / "sessions" / "old-1"
    old.parent.mkdir(parents=True)
    old.write_text(str(wa / ".superlite"))
    os.utime(old, (0, 0))
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", A)
    state.bind(wa / ".superlite")
    assert not old.exists()


# ------------------------------------------------------------------ sl orchestrator

def test_set_binds_the_plans_worktree_and_status_finds_it_from_the_launch_dir(repo):
    main, wa, _ = repo
    plan = wa / "docs" / "superpowers" / "plans" / "p.md"
    r = sl(main, A, "set", "human", "--plan", plan)
    assert r.returncode == 0, r.stderr
    assert json.loads((wa / ".superlite" / "orchestrator.json").read_text())["approved"] is False
    assert not (main / ".superlite").exists()
    assert state.owner(wa / ".superlite") == A
    r = sl(main, A, "status")  # no --plan: the session's binding, not the launch directory
    assert r.returncode == 0 and "awaiting approval" in r.stdout, r.stdout + r.stderr


def test_approve_uses_the_review_plans_worktree(repo):
    main, wa, _ = repo
    assert sl(main, A, "set", "human", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    f = review(wa)
    assert prompt(main, A, "approve").returncode == 0
    r = sl(main, A, "approve", "--review", f)
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads((wa / ".superlite" / "orchestrator.json").read_text())["approved"] is True


def test_bind_command(repo):
    main, wa, _ = repo
    r = sl(main, A, "bind", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md")
    assert r.returncode == 0 and str(wa.resolve() / ".superlite") in r.stdout, r.stdout + r.stderr
    assert state.bound(A) == wa.resolve() / ".superlite"
    r = sl(main, None, "bind")
    assert r.returncode == 2 and "CLAUDE_CODE_SESSION_ID" in r.stderr


def test_end_archives_the_run_and_releases_the_session(repo):
    main, wa, _ = repo
    sd = wa / ".superlite"
    assert sl(main, A, "set", "human", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    for f in ("stable.json", "prime.md", "prime-haiku.md", "pool.json", "human-replies.jsonl"):
        (sd / f).write_text("{}\n")
    (sd / "progress.md").write_text("ledger\n")
    r = sl(main, A, "end")
    assert r.returncode == 0, r.stderr
    assert "ended" in r.stdout
    runs = list((sd / "runs").iterdir())
    assert len(runs) == 1
    assert sorted(p.name for p in runs[0].iterdir()) == sorted(
        ["stable.json", "prime.md", "prime-haiku.md", "pool.json", "human-replies.jsonl", "orchestrator.json"])
    assert (sd / "progress.md").exists()  # the ledger stays
    assert state.owner(sd) is None and state.bound(A) is None
    assert write(wa, A, wa / "src" / "a.py").returncode == 0  # the guard is off
    r = sl(main, A, "end", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md")
    assert r.returncode == 0 and "nothing to end" in r.stdout


# ------------------------------------------------------------------ hooks

def test_two_sessions_from_one_launch_dir_never_share_a_gate(repo):
    """The 2026-10-21 incident: A and B are launched from main; A's human gate never stops B's build."""
    main, wa, wb = repo
    assert sl(main, A, "set", "human", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    assert sl(main, B, "set", "ai", "--plan", wb / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    (wb / ".superlite" / "pool.json").write_text("{}")  # B's run is active
    assert dispatch(main, B, wb).returncode == 0  # B builds while A waits for approval
    r = dispatch(main, A, wa)
    assert r.returncode == 2 and "Human orchestrator" in r.stderr  # A is gated
    assert write(main, B, wb / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    assert write(main, B, wb / "src" / "a.py").returncode == 2  # B's own run guard still holds
    assert write(main, A, wb / "src" / "a.py").returncode == 0  # but not for A
    assert write(main, A, wa / "src" / "a.py").returncode == 2


def test_replies_land_in_the_sessions_own_pending_plan(repo):
    main, wa, wb = repo
    assert sl(main, A, "set", "human", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    assert sl(main, B, "set", "human", "--plan", wb / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    assert prompt(main, A, "approve").returncode == 0
    assert (wa / ".superlite" / "human-replies.jsonl").exists()
    assert not (wb / ".superlite" / "human-replies.jsonl").exists()
    assert not (main / ".superlite").exists()


def test_legacy_folder_owned_by_another_session_is_ignored(repo):
    main, _, _ = repo
    assert sl(main, A, "set", "human", "--plan", main / "plan.md").returncode == 0  # A works in main itself
    assert write(main, A, main / "src" / "a.py").returncode == 2
    assert write(main, B, main / "src" / "a.py").returncode == 0  # B, unbound, launched in main: not A's gate
    assert prompt(main, B, "approve").returncode == 0
    assert not (main / ".superlite" / "human-replies.jsonl").exists()


def test_without_session_ids_the_launch_dir_still_works(tmp_path):
    sd = tmp_path / ".superlite"
    sd.mkdir()
    (sd / "orchestrator.json").write_text('{"mode": "human", "approved": false}')
    raw = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(tmp_path / "a.py")}})
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(tmp_path))
    assert subprocess.run([BASH, str(GUARD)], input=raw, capture_output=True, text=True, env=env).returncode == 2


def test_state_dir_override(repo, monkeypatch):
    main, wa, _ = repo
    (wa / ".superlite").mkdir()
    (wa / ".superlite" / "orchestrator.json").write_text('{"mode": "human", "approved": false}')
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(wa / ".superlite"))
    assert write(main, A, wa / "src" / "a.py").returncode == 2
    assert write(main, A, main / "src" / "a.py").returncode == 0


# ------------------------------------------------------------------ tools

def test_lint_stable_writes_at_the_worktree_root_and_binds(repo):
    from test_routing import mech_plan
    main, wa, _ = repo
    p = mech_plan(wa / "docs" / "superpowers" / "plans", 2)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=A)
    r = subprocess.run([sys.executable, str(SCRIPTS / "plan_tools.py"), "lint", "--stable", "--plan", str(p)],
                       capture_output=True, text=True, cwd=main, env=env, timeout=120)
    assert (wa / ".superlite" / "stable.json").is_file(), r.stdout + r.stderr
    assert not (wa / "docs" / "superpowers" / "plans" / ".superlite").exists()
    assert state.bound(A) == wa.resolve() / ".superlite"


def test_hotspots_takes_several_files(tmp_path):
    log = tmp_path / "i.jsonl"
    for f in ("a.swift", "b.swift", "c.swift"):
        assert run(SCRIPTS / "incident.py", "add", "--file", f, "--line", 1, "--context", "x", "--kind", "flaky",
                   "--log", log, cwd=tmp_path).returncode == 0
    r = run(SCRIPTS / "incident.py", "hotspots", "--files", "a.swift", "b.swift", "--log", log, cwd=tmp_path)
    assert r.returncode == 0, r.err
    assert "a.swift" in r.out and "b.swift" in r.out and "c.swift" not in r.out
    r = run(SCRIPTS / "incident.py", "hotspots", "--files", "a.swift,c.swift", "--log", log, cwd=tmp_path)
    assert "a.swift" in r.out and "c.swift" in r.out and "b.swift" not in r.out


def test_build_prime_numbers_unnumbered_sections_in_order(tmp_path):
    spec = tmp_path / "x.review.md"
    spec.write_text("# Review\n\n## Goal\n\ngoal text\n\n## What changes\n\nchanges text\n\n### Detail\n\nd\n\n## Risks\n\nrisk text\n")
    plan = tmp_path / "plan.md"
    plan.write_text("# Plan\n")
    out = tmp_path / "prime.md"
    r = run(SCRIPTS / "build_prime.py", "--plan", plan, "--spec", spec, "--sections", "1,3", "--out", out, cwd=tmp_path)
    assert r.returncode == 0, r.err
    text = out.read_text()
    assert "goal text" in text and "risk text" in text and "changes text" not in text
    r = run(SCRIPTS / "build_prime.py", "--plan", plan, "--spec", spec, "--sections", "7", "--out", out, cwd=tmp_path)
    assert r.returncode != 0 and "Goal" in r.err and "Risks" in r.err  # the error lists what exists
