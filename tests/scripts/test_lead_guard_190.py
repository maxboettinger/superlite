# tests/scripts/test_lead_guard_190.py
import json, os, subprocess
import pytest
from test_block_coordinator_edits import BASH, HOOK

@pytest.fixture
def proj(tmp_path):
    p = tmp_path / "proj"; (p / ".superlite").mkdir(parents=True); return p

def hook(proj, tool, inp, env=None):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    e.update({"CLAUDE_PROJECT_DIR": str(proj), "SUPERLITE_HOME": str(proj.parent / "slhome"), **(env or {})})
    raw = json.dumps({"session_id": "s190", "tool_name": tool, "tool_input": inp, "cwd": str(proj)})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=e)

def w(proj, path, env=None):
    return hook(proj, "Write", {"file_path": str(path), "content": "x"}, env).returncode

def lead(sd, **kw):
    return {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_STATE_DIR": str(sd), **kw}

def test_lead_is_guarded_like_a_coordinator(proj):
    sd = proj / ".superlite"; (sd / "pool.json").write_text("{}")
    assert w(proj, proj / "app.py", lead(sd)) == 2 and w(proj, proj / "docs" / "plans" / "p.md", lead(sd)) == 0
    assert hook(proj, "Bash", {"command": "sed -i s/a/b/ app.py"}, lead(sd)).returncode == 2
    for env in (lead(sd, SUPERLITE_FLEET_ROLE="implementer"), {"SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_STATE_DIR": str(sd)}):
        assert w(proj, proj / "app.py", env) == 0 and hook(proj, "Bash", {"command": "sed -i s/a/b/ app.py"}, env).returncode == 0

def test_state_and_parent_folders_are_protected_by_absolute_path(proj, tmp_path):
    sd = proj.parent / "slhome" / "sessions" / "s190"; sd.mkdir(parents=True)
    r = hook(proj, "Write", {"file_path": str(sd / "orchestrator.json"), "content": "x"}, {"SUPERLITE_STATE_DIR": str(sd)})
    assert r.returncode == 2 and "never written directly" in r.stderr and w(proj, sd / "progress.md", {"SUPERLITE_STATE_DIR": str(sd)}) == 0
    parent = tmp_path / "main" / ".superlite"; parent.mkdir(parents=True); (tmp_path / "alias").symlink_to(tmp_path / "main")
    env = lead(proj / ".superlite", SUPERLITE_FLEET_PARENT_DIR=str(parent))
    assert w(proj, parent / "backlog.json", env) == 2 and w(proj, tmp_path / "alias" / ".superlite" / "human-replies.jsonl", env) == 2
    assert w(proj, parent / "backlog" / "B1.md", env) == 0

def test_idle_writes_to_run_files_in_a_worktree_or_through_a_link_block(proj):
    wt = proj / ".claude" / "worktrees" / "w1"; (wt / ".superlite").mkdir(parents=True); (wt / ".git").write_text("gitdir: /x/.git/worktrees/w1\n")
    assert w(proj, wt / ".superlite" / "orchestrator.json") == 2 and w(proj, wt / ".superlite" / "progress.md") == 0 and w(proj, wt / "a.py") == 0
    (proj / "docs" / "plans").mkdir(parents=True); (proj / "docs" / "plans" / "up").symlink_to(proj)
    assert w(proj, proj / "docs" / "plans" / "up" / ".superlite" / "orchestrator.json") == 2
    assert w(proj, proj / "docs" / "plans" / "up" / "README.md") == 0

def test_backlog_json_in_the_project_is_protected(proj):
    r = hook(proj, "Write", {"file_path": ".superlite/backlog.json", "content": "x"})
    assert r.returncode == 2 and "backlog.json" in r.stderr
