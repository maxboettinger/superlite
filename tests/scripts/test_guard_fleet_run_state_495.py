# tests/scripts/test_guard_fleet_run_state_495.py: rule 4 of hooks/block-coordinator-edits reads the session's own run (#495)
import json
import pytest
from test_fleet_hooks import run_hook

ROLES = ["implementer", "fixer-opus", "package-reviewer", "final-reviewer"]


class Env:
    def __init__(self, tmp_path):
        self.tmp = tmp_path
        self.home = tmp_path / "home"
        (self.home / "sessions").mkdir(parents=True)
        self.main = tmp_path / "main"
        (self.main / ".git").mkdir(parents=True)
        self.msd = self.main / ".superlite"
        self.msd.mkdir()
        (self.msd / "session").write_text("s1")
        self.wt = self.main / ".claude" / "worktrees" / "wt1"
        self.wt.mkdir(parents=True)
        (self.wt / ".git").write_text(f"gitdir: {self.main}/.git/worktrees/wt1\n")
        self.bind("s1", f"{self.msd}\n123\n{self.main}\n")

    def bind(self, sid, text):
        (self.home / "sessions" / sid).write_text(text)

    def on(self, folder, **owner):
        folder.mkdir(parents=True, exist_ok=True)
        (folder / "fleet.json").write_text(json.dumps({"on": True, "label": "sl:x", "next": 1, "workers": {}, **owner}, indent=2))

    def call(self, cwd, agent="superlite:final-reviewer", env=None):
        stdin = json.dumps({"session_id": "s1", "tool_name": "Agent", "cwd": str(cwd),
                            "tool_input": {"subagent_type": agent, "description": "d", "prompt": "p"}})
        e = {"SUPERLITE_HOME": str(self.home), "CLAUDE_PROJECT_DIR": "", "CLAUDE_PID": "999", **(env or {})}
        return run_hook("block-coordinator-edits", stdin, e, cwd)


@pytest.fixture
def e(tmp_path):
    return Env(tmp_path)


def test_worktree_ignores_main_checkout_fleet(e):
    e.on(e.msd)
    assert e.call(e.wt).returncode == 0
    assert not (e.msd / "incidents.jsonl").exists()


def test_worktree_own_fleet_blocks(e):
    e.on(e.msd)
    e.on(e.wt / ".superlite", owner_session="s1")
    r = e.call(e.wt)
    assert r.returncode == 2
    assert f"PLAN is the plan file, or {e.wt}/.superlite for a build without a plan." in r.stderr
    rows = (e.wt / ".superlite" / "incidents.jsonl").read_text().splitlines()
    assert json.loads(rows[-1])["rule"] == "fleet"
    assert not (e.msd / "incidents.jsonl").exists()


def test_main_checkout_keeps_binding(e):
    e.on(e.msd)
    r = e.call(e.main)
    assert r.returncode == 2
    assert f"or {e.msd} for a build without a plan." in r.stderr


def test_binding_inside_worktree_kept(e):
    w = e.wt / ".superlite"
    w.mkdir()
    (w / "session").write_text("s1")
    e.bind("s1", f"{w}\n123\n{e.wt}\n")
    e.on(w)
    (e.wt / "sub").mkdir()
    assert e.call(e.wt / "sub").returncode == 2


def test_private_folder_kept(e):
    p = e.home / "sessions" / "s1.d" / ".superlite"
    p.mkdir(parents=True)
    e.bind("s1", f"{p}\n123\n{e.main}\n")
    e.on(p)
    r = e.call(e.wt)
    assert r.returncode == 2
    assert str(p) in r.stderr


def test_submodule_git_file_is_no_worktree(e):
    sub = e.main / "sub"
    sub.mkdir()
    (sub / ".git").write_text("gitdir: ../.git/modules/sub\n")
    e.on(e.msd)
    assert e.call(sub).returncode == 2


def test_state_dir_env_wins(e):
    e.on(e.msd, owner_session="s0")
    assert e.call(e.wt, env={"SUPERLITE_STATE_DIR": str(e.msd)}).returncode == 2


def test_other_finished_session_passes(e):
    e.on(e.msd, owner_session="s0", owner_pid=111)
    assert e.call(e.main).returncode == 0
    assert not (e.msd / "incidents.jsonl").exists()


def test_own_session_blocks(e):
    e.on(e.msd, owner_session="s1", owner_pid=111)
    assert e.call(e.main).returncode == 2


def test_same_process_after_clear_blocks(e):
    e.on(e.msd, owner_session="s0", owner_pid=999)
    assert e.call(e.main).returncode == 2


def test_live_owner_bound_here_blocks(e):
    e.on(e.msd, owner_session="s0", owner_pid=111)
    e.bind("s0", f"{e.msd}/\n111\n")
    assert e.call(e.main).returncode == 2


def test_owner_bound_elsewhere_passes(e):
    e.on(e.msd, owner_session="s0", owner_pid=111)
    e.bind("s0", f"{e.tmp}/other/.superlite\n111\n")
    assert e.call(e.main).returncode == 0


def test_fleet_without_owner_blocks(e):
    e.on(e.msd)
    assert e.call(e.main).returncode == 2


@pytest.mark.parametrize("role", ROLES)
def test_generic_hint_names_the_no_plan_form(e, role):
    e.on(e.msd)
    r = e.call(e.main, agent=f"superlite:{role}")
    assert f"(fleet.md). PLAN is the plan file, or {e.msd} for a build without a plan. sl fleet off goes back to in-process agents." in r.stderr


def test_research_path_names_the_run_folder(e):
    e.on(e.wt / ".superlite", owner_session="s1")
    r = e.call(e.wt, agent="superlite:researcher")
    assert r.returncode == 2
    assert f"write the prompt to {e.wt}/.superlite/briefs/<name>.md;" in r.stderr
    assert f"PLAN is the plan file, or {e.wt}/.superlite before a plan exists." in r.stderr


def test_other_agents_pass_a_live_fleet(e):
    e.on(e.msd)
    assert e.call(e.main, agent="Explore").returncode == 0
