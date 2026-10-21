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
        ["stable.json", "prime.md", "prime-haiku.md", "pool.json", "human-replies.jsonl", "orchestrator.json", "progress.md"])
    assert not (sd / "progress.md").exists()  # the next run starts with a fresh ledger
    assert state.owner(sd) is None and state.bound(A) is None
    assert write(wa, A, wa / "src" / "a.py").returncode == 0  # the guard is off
    plan = wa / "docs" / "superpowers" / "plans" / "p.md"
    plan.write_text("# p\n")
    r = sl(main, A, "end", "--plan", plan)
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


# ------------------------------------------------------------------ review findings (fix wave)

def guard_bash(launch, sid, cmd):
    return hook(GUARD, launch, sid, {"tool_name": "Bash", "tool_input": {"command": cmd}})


def test_set_without_plan_never_takes_another_sessions_folder(repo):
    """C1: the skills run `sl orchestrator set` before any plan exists, both sessions from the launch directory."""
    main, _, _ = repo
    assert sl(main, A, "set", "human").returncode == 0
    r = sl(main, B, "set", "ai")
    assert r.returncode == 0, r.stderr
    assert "awaiting approval" in sl(main, A, "status").stdout  # A keeps its own gate
    assert "AI" in sl(main, B, "status").stdout
    assert state.owner(main / ".superlite") == A
    assert state.bound(B) == state.private_dir(B)
    assert guard_bash(main, A, "sl dispatch --plan p.md").returncode == 2
    assert guard_bash(main, B, "sl dispatch --plan p.md").returncode == 0


def test_pending_gate_follows_the_session_to_its_worktree(repo):
    """C2: set human before the plan, then lint --stable on the worktree's plan: still gated, and approvable there."""
    from test_routing import mech_plan
    main, wa, _ = repo
    assert sl(main, A, "set", "human").returncode == 0
    p = mech_plan(wa / "docs" / "superpowers" / "plans", 2)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=A)
    r = subprocess.run([sys.executable, str(SCRIPTS / "plan_tools.py"), "lint", "--stable", "--plan", str(p)],
                       capture_output=True, text=True, cwd=main, env=env, timeout=120)
    assert r.returncode == 4, r.stdout + r.stderr
    assert not (wa / ".superlite" / "stable.json").exists()
    assert json.loads((wa / ".superlite" / "orchestrator.json").read_text())["mode"] == "human"
    assert not (main / ".superlite" / "orchestrator.json").exists()
    assert guard_bash(main, A, f"cd {wa} && sl dispatch --plan p.md").returncode == 2
    f = review(wa)
    assert prompt(main, A, "approve").returncode == 0
    assert sl(main, A, "approve", "--review", f).returncode == 0


def test_end_refuses_another_sessions_folder_and_a_missing_plan(repo):
    """C3: A ends after removing its worktree; the path walks up to main, which B's run owns."""
    main, wa, _ = repo
    assert sl(main, B, "set", "human").returncode == 0
    (main / ".superlite" / "stable.json").write_text("{}")
    r = sl(main, A, "end", "--plan", main / "docs" / "plans" / "gone.md")
    assert r.returncode == 2 and "end before removing the worktree" in r.stderr
    (main / "docs" / "plans").mkdir(parents=True)
    (main / "docs" / "plans" / "p.md").write_text("# p\n")
    r = sl(main, A, "end", "--plan", main / "docs" / "plans" / "p.md")
    assert r.returncode == 2 and "belongs to session" in r.stderr
    assert (main / ".superlite" / "orchestrator.json").exists() and (main / ".superlite" / "stable.json").exists()


def test_bind_force_takes_over(repo):
    main, _, _ = repo
    assert sl(main, A, "set", "human").returncode == 0
    r = sl(main, B, "bind", "--plan", main / "plan.md")
    assert r.returncode == 2 and "belongs to session" in r.stderr
    assert sl(main, B, "bind", "--force", "--plan", main / "plan.md").returncode == 0
    assert state.owner(main / ".superlite") == B
    assert state.bound(A) is None  # A no longer resolves to it


def test_symlinked_project_path_is_still_guarded(repo, tmp_path):
    """M1: Claude passes the logical path; the binding keeps it, not the resolved one."""
    main, wa, _ = repo
    link = tmp_path / "link"
    link.symlink_to(main)
    lwa = link / ".claude" / "worktrees" / "wa"
    assert sl(link, A, "set", "ai", "--plan", lwa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    (wa / ".superlite" / "pool.json").write_text("{}")
    assert state.bound(A) == lwa / ".superlite"
    assert write(link, A, lwa / "src" / "a.py").returncode == 2


def test_stale_owner_does_not_lock_out_a_new_session(repo):
    """M2: after /clear the old id's binding is gone; the new session uses the folder (and its gate)."""
    main, _, _ = repo
    assert sl(main, A, "set", "human").returncode == 0
    (state.home() / "sessions" / A).unlink()
    assert write(main, B, main / "src" / "a.py").returncode == 2
    assert prompt(main, B, "approve").returncode == 0
    assert (main / ".superlite" / "human-replies.jsonl").exists()


def test_session_start_exports_the_hook_session_id(tmp_path):
    env_file = tmp_path / "env.sh"
    env = dict(os.environ, CLAUDE_ENV_FILE=str(env_file), CLAUDE_PLUGIN_ROOT=str(ROOT))
    r = subprocess.run([BASH, str(ROOT / "hooks" / "session-start")], input=json.dumps({"session_id": A, "source": "clear"}),
                       capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    assert env_file.read_text() == f"export SUPERLITE_SESSION_ID={A}\n"


def test_superlite_session_id_wins(monkeypatch):
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", A)
    monkeypatch.setenv("SUPERLITE_SESSION_ID", B)
    assert state.session_id() == B


def test_next_tasks_reads_stable_json_at_the_worktree_root(repo):
    """M3: dispatch must see the stable set lint wrote at the toplevel."""
    sys.path.insert(0, str(SCRIPTS))
    import next_tasks
    _, wa, _ = repo
    (wa / ".superlite").mkdir()
    (wa / ".superlite" / "stable.json").write_text(json.dumps({"stable": ["T1"], "fix": []}))
    got = next_tasks.stable_filter(str(wa / "docs" / "superpowers" / "plans" / "p.md"))
    assert got is not None and "T1" in got


def test_monorepo_plan_resolves_next_to_its_docs(repo):
    main, _, _ = repo
    assert state.plan_dir(main / "app" / "docs" / "plans" / "p.md") == main / "app" / ".superlite"


@pytest.mark.parametrize("cmd", [
    "python3 - <<'EOF'\nfrom pathlib import Path\nPath('.superlite/notes.md').write_text('n')\nfor f in Path('src').glob('*'):\n    f.write_text('x')\nEOF",
    "python3 -c \"t='a'; open(f'src/{t}.py','w').write('x'); print('.superlite/stable.json')\"",
    "python3 -c \"import os; open(os.path.join('src','main'),'w'); open('docs/plans/x.md','w')\"",
    "python3 -c \"import sys; open(sys.argv[1],'w').write('x')\" src/a.py && cat 'docs/plans/x.md'",
    "python3 -c \"from pathlib import Path; Path('src/a.py').with_suffix('.md').write_text('x'); open('docs/plans/x.md','w')\"",
])
def test_interpreter_writes_with_unknown_or_project_targets_block(repo, cmd):
    """M4: an allowed literal elsewhere in the command no longer approves the whole script."""
    main, wa, _ = repo
    assert sl(main, A, "set", "ai", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    (wa / ".superlite" / "pool.json").write_text("{}")
    assert guard_bash(main, A, f"cd {wa} && {cmd}").returncode == 2, cmd


def test_traversal_out_of_docs_is_project_code(repo):
    main, wa, _ = repo
    assert sl(main, A, "set", "ai", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    (wa / ".superlite" / "pool.json").write_text("{}")
    assert write(main, A, "docs/superpowers/plans/../../../src/a.py").returncode == 2


def test_read_only_home_does_not_break_set(repo, tmp_path):
    """M5: a sandbox that denies writes to the home folder must not stop the run."""
    main, _, _ = repo
    home = tmp_path / "ro_home"
    home.mkdir()
    home.chmod(0o500)
    try:
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=A, SUPERLITE_HOME=str(home))
        r = subprocess.run([sys.executable, str(ORCH), "set", "ai"], capture_output=True, text=True, cwd=main, env=env)
        assert r.returncode == 0, r.stderr
        assert "session binding not written" in r.stderr
        assert (main / ".superlite" / "orchestrator.json").exists()
    finally:
        home.chmod(0o700)


def test_relative_state_dir_override_is_absolute_in_hooks(repo):
    main, wa, _ = repo
    (wa / ".superlite").mkdir()
    (wa / ".superlite" / "orchestrator.json").write_text('{"mode": "human", "approved": false}')
    raw = json.dumps({"tool_name": "Write", "tool_input": {"file_path": str(wa / "src" / "a.py")}})
    env = dict(os.environ, SUPERLITE_STATE_DIR=".superlite")
    r = subprocess.run([BASH, str(GUARD)], input=raw, capture_output=True, text=True, env=env, cwd=wa)
    assert r.returncode == 2


PARITY = r'''input="$1"; . "$2"; superlite_state; printf '%s' "$SL_SD"'''


@pytest.mark.parametrize("case", ["none", "bound", "bound-missing", "taken-over", "crlf", "owned-live", "owned-stale"])
def test_bash_and_python_resolve_the_same_folder(repo, monkeypatch, case):
    main, wa, wb = repo
    sessions = state.home() / "sessions"
    sessions.mkdir(parents=True, exist_ok=True)
    msd = main / ".superlite"
    if case in ("bound", "taken-over", "crlf"):
        (wa / ".superlite").mkdir()
        (sessions / A).write_text(f"{wa / '.superlite'}" + ("\r\n" if case == "crlf" else "\n"))
        if case == "taken-over":
            (wa / ".superlite" / "session").write_text(B + "\n")
    if case == "bound-missing":
        (sessions / A).write_text(f"{wb / '.superlite'}\n")
    if case in ("owned-live", "owned-stale"):
        msd.mkdir()
        (msd / "session").write_text(B + "\n")
        if case == "owned-live":
            (sessions / B).write_text(f"{msd}\n")
    monkeypatch.setenv("CLAUDE_CODE_SESSION_ID", A)
    monkeypatch.chdir(main)
    py = state.resolve()
    py = None if py == state.private_dir(A) else state._abs(py)  # the hooks have no private folder before a bind
    env = dict(os.environ, CLAUDE_PROJECT_DIR=str(main))
    r = subprocess.run([BASH, "-c", PARITY, "_", json.dumps({"session_id": A}), str(ROOT / "hooks" / "superlite-state.sh")],
                       capture_output=True, text=True, env=env)
    sh = Path(r.stdout) if r.stdout else None
    assert sh == py, (case, sh, py)


# ------------------------------------------------------------------ re-review findings

def test_second_session_human_gate_without_plan_is_enforced(repo):
    """N1: B's `set human` lands in its private folder; the hooks must read it and judge paths against main."""
    from test_routing import mech_plan
    main, _, wb = repo
    assert sl(main, A, "set", "ai").returncode == 0
    assert sl(main, B, "set", "human").returncode == 0
    assert (state.private_dir(B) / "orchestrator.json").is_file()
    assert write(main, B, main / "src" / "a.py").returncode == 2
    assert write(main, B, "src/a.py").returncode == 2
    agent = hook(GUARD, main, B, {"tool_name": "Agent", "tool_input": {"subagent_type": "superlite:implementer"}})
    assert agent.returncode == 2
    assert write(main, A, main / "src" / "a.py").returncode == 0  # A is AI and has no run
    assert prompt(main, B, "approve").returncode == 0
    assert (state.private_dir(B) / "human-replies.jsonl").is_file()
    p = mech_plan(wb / "docs" / "superpowers" / "plans", 2)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=B)
    r = subprocess.run([sys.executable, str(SCRIPTS / "plan_tools.py"), "lint", "--stable", "--plan", str(p)],
                       capture_output=True, text=True, cwd=main, env=env, timeout=120)
    assert r.returncode == 4, r.stdout + r.stderr
    assert (wb / ".superlite" / "orchestrator.json").is_file() and (wb / ".superlite" / "human-replies.jsonl").is_file()


def test_clear_hands_the_binding_to_the_new_session_id(repo):
    """R1: /clear keeps the Claude process (CLAUDE_PID) and starts a new id; the gate stays with the conversation."""
    main, _, _ = repo
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=A, CLAUDE_PID="4242")
    assert subprocess.run([sys.executable, str(ORCH), "set", "human"], cwd=main, env=env, capture_output=True).returncode == 0
    a2 = "aaaa-2222"
    r = subprocess.run([BASH, str(ROOT / "hooks" / "session-start")],
                       input=json.dumps({"session_id": a2, "source": "clear"}), capture_output=True, text=True,
                       env=dict(os.environ, CLAUDE_PID="4242", CLAUDE_PLUGIN_ROOT=str(ROOT)))
    assert r.returncode == 0, r.stderr
    assert state.owner(main / ".superlite") == a2 and state.bound(a2) == main / ".superlite"
    assert not (state.home() / "sessions" / A).exists()
    assert write(main, a2, main / "src" / "a.py").returncode == 2
    assert prompt(main, a2, "approve").returncode == 0
    assert (main / ".superlite" / "human-replies.jsonl").is_file()


def test_clear_in_another_process_hands_nothing_over(repo):
    main, _, _ = repo
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=A, CLAUDE_PID="4242")
    assert subprocess.run([sys.executable, str(ORCH), "set", "human"], cwd=main, env=env, capture_output=True).returncode == 0
    subprocess.run([BASH, str(ROOT / "hooks" / "session-start")], input=json.dumps({"session_id": B, "source": "clear"}),
                   capture_output=True, text=True, env=dict(os.environ, CLAUDE_PID="999", CLAUDE_PLUGIN_ROOT=str(ROOT)))
    assert state.owner(main / ".superlite") == A


def test_symlinked_launch_dir_without_plan(repo, tmp_path):
    """R2: `set` without --plan keeps the logical $PWD, as Claude passes paths."""
    main, _, _ = repo
    link = tmp_path / "link"
    link.symlink_to(main)
    env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=A, PWD=str(link))
    assert subprocess.run([sys.executable, str(ORCH), "set", "ai"], cwd=link, env=env, capture_output=True).returncode == 0
    assert state.bound(A) == link / ".superlite"
    (main / ".superlite" / "pool.json").write_text("{}")
    assert write(link, A, link / "src" / "a.py").returncode == 2


@pytest.mark.parametrize("cmd", [
    "python3 -c \"f = '.superlite/notes.md'; open(f,'w').write('x'); f = 'src/config.py'; open(f,'w').write('y')\"",
    "python3 -c \"f = '.superlite/n.md'\nfor f in ['src/a.py']:\n    open(f,'w')\"",
])
def test_reassigned_names_are_judged_by_every_value(repo, cmd):
    """R4: the second assignment is project code."""
    main, wa, _ = repo
    assert sl(main, A, "set", "ai", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    (wa / ".superlite" / "pool.json").write_text("{}")
    assert guard_bash(main, A, f"cd {wa} && {cmd}").returncode == 2, cmd


def test_reads_with_keyword_arguments_pass(repo):
    main, wa, _ = repo
    assert sl(main, A, "set", "ai", "--plan", wa / "docs" / "superpowers" / "plans" / "p.md").returncode == 0
    (wa / ".superlite" / "pool.json").write_text("{}")
    cmd = ("python3 -c \"d = open('src/a.py', encoding='utf-8', errors='replace').read(); "
           "open('.superlite/notes.md','w').write(d)\"")
    assert guard_bash(main, A, f"cd {wa} && {cmd}").returncode == 0


def test_clear_with_two_sessions_in_one_process_hands_nothing_over(repo):
    main, wa, _ = repo
    for sid, d in ((A, main), (B, wa)):
        env = dict(os.environ, PYTHONIOENCODING="utf-8", CLAUDE_CODE_SESSION_ID=sid, CLAUDE_PID="4242")
        args = ["set", "human"] if sid == A else ["set", "human", "--plan", str(wa / "docs" / "superpowers" / "plans" / "p.md")]
        assert subprocess.run([sys.executable, str(ORCH), *args], cwd=main, env=env, capture_output=True).returncode == 0
    subprocess.run([BASH, str(ROOT / "hooks" / "session-start")], input=json.dumps({"session_id": "cccc-3", "source": "clear"}),
                   capture_output=True, text=True, env=dict(os.environ, CLAUDE_PID="4242", CLAUDE_PLUGIN_ROOT=str(ROOT)))
    assert state.owner(main / ".superlite") == A and state.owner(wa / ".superlite") == B
