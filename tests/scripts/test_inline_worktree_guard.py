"""hooks/inline-worktree-guard and `sl worktree inplace`: once an inline superlite flow is marked
(<state folder>/inline-flow.json), an Edit/Write/NotebookEdit inside the main checkout is refused until the work moves to
a worktree (`sl worktree ensure`) or `sl worktree inplace --reason TEXT` records an opt-out (#148)."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "inline-worktree-guard"
SL = ROOT / "skills" / "subagent-driven-development" / "scripts" / "sl"
_GIT_BASH = r"C:\Program Files\Git\bin\bash.exe"
BASH = _GIT_BASH if os.name == "nt" and os.path.exists(_GIT_BASH) else shutil.which("bash")


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True).stdout


@pytest.fixture
def repo(tmp_path):
    r = tmp_path.resolve() / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.name", "t")
    git(r, "config", "user.email", "t@t")
    (r / "src").mkdir()
    (r / "src" / "a.py").write_text("a = 1\n")
    git(r, "add", ".")
    git(r, "commit", "-q", "-m", "init")
    (r / ".superlite").mkdir()
    return r


def mark(repo, flow="small", inplace=None):
    (repo / ".superlite" / "inline-flow.json").write_text(
        json.dumps({"flow": flow, "at": 1, "inplace": inplace}), encoding="utf-8")


def env_for(repo, **extra):
    e = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_")}
    e.update({"CLAUDE_PROJECT_DIR": str(repo), "SUPERLITE_HOME": str(repo.parent / "home"), **extra})
    return e


def edit(repo, path, tool="Edit", raw=None, agent_id=None, **env):
    key = "notebook_path" if tool == "NotebookEdit" else "file_path"
    body = {"tool_name": tool, "tool_input": {key: str(path)}, "cwd": str(repo)}
    if agent_id:
        body["agent_id"] = agent_id
    return subprocess.run([BASH, str(HOOK)], input=raw if raw is not None else json.dumps(body), capture_output=True,
                          text=True, env=env_for(repo, **env))


def sl_inplace(repo, *args, **env):
    return subprocess.run([BASH, str(SL), "worktree", "inplace", *args], capture_output=True, text=True,
                          encoding="utf-8", cwd=repo, env=env_for(repo, SUPERLITE_STATE_DIR=str(repo / ".superlite"), **env))


def test_marked_flow_refuses_main_checkout_write(repo):
    mark(repo, "small")
    git(repo, "worktree", "add", "-q", "-b", "superlite/x", str(repo / ".claude" / "worktrees" / "superlite-x"))
    r = edit(repo, repo / "src" / "a.py")
    assert r.returncode == 2
    assert "sl worktree ensure" in r.stderr and "sl worktree inplace --reason" in r.stderr
    assert edit(repo, repo / ".claude" / "worktrees" / "superlite-x" / "src" / "a.py").returncode == 0
    rec = json.loads((repo / ".superlite" / "incidents.jsonl").read_text().splitlines()[0])
    assert rec["kind"] == "rule-block" and rec["tool"] == "Edit" and rec["target"].endswith("src/a.py")


def test_every_flow_and_tool_is_refused(repo):
    for flow in ("small", "debug", "tdd", "debugging"):
        mark(repo, flow)
        assert edit(repo, repo / "src" / "new.py", "Write").returncode == 2, flow
    assert edit(repo, repo / "nb.ipynb", "NotebookEdit").returncode == 2
    assert edit(repo, "src/rel.py").returncode == 2   # a relative path is the project's


def test_unmarked_passes(repo):
    assert edit(repo, repo / "src" / "a.py").returncode == 0
    (repo / ".superlite" / "inline-flow.json").write_text("garbage", encoding="utf-8")
    assert edit(repo, repo / "src" / "a.py").returncode == 0


def test_run_marker_passes(repo):
    mark(repo)
    for name in ("pool.json", "stable.json", "prime.md"):
        (repo / ".superlite" / name).write_text("{}")
        assert edit(repo, repo / "src" / "a.py").returncode == 0, name
        (repo / ".superlite" / name).unlink()
    assert edit(repo, repo / "src" / "a.py").returncode == 2


def test_superlite_and_claude_dirs_pass(repo):
    mark(repo)
    for p in (".superlite/x", ".superlite/fixes/F-T1-1.md", ".claude/settings.json", ".SUPERLITE/x"):
        assert edit(repo, repo / p).returncode == 0, p


def test_outside_repo_passes(repo, tmp_path):
    mark(repo)
    assert edit(repo, tmp_path / "elsewhere" / "a.py").returncode == 0
    assert edit(repo, "/etc/hosts").returncode == 0
    assert edit(repo, repo.parent / "repo-sibling" / "a.py").returncode == 0   # shares only a name prefix


def test_linked_worktree_paths_pass(repo):
    mark(repo)
    wt = repo / "wt-other"
    git(repo, "worktree", "add", "-q", "-b", "other", str(wt))
    assert (wt / ".git").is_file()
    assert edit(repo, wt / "src" / "a.py").returncode == 0
    assert edit(repo, wt / "src" / "deeper" / "new.py", "Write").returncode == 0
    assert edit(repo, repo / "src" / "a.py").returncode == 2


def test_session_in_a_linked_worktree_passes(repo):
    wt = repo / ".claude" / "worktrees" / "superlite-y"
    git(repo, "worktree", "add", "-q", "-b", "superlite/y", str(wt))
    (wt / ".superlite").mkdir()
    (wt / ".superlite" / "inline-flow.json").write_text('{"flow": "small", "at": 1, "inplace": null}')
    assert edit(wt, wt / "src" / "a.py").returncode == 0


def test_dotdot_cannot_hide_the_main_checkout(repo):
    mark(repo)
    wt = repo / ".claude" / "worktrees" / "superlite-x"
    assert edit(repo, f"{wt}/../../../src/a.py").returncode == 2
    assert edit(repo, f"{repo}/src/./a.py").returncode == 2
    assert edit(repo, f"{repo}/.claude/../src/a.py").returncode == 2
    assert edit(repo, f"{repo}/src/../.claude/x.json").returncode == 0


def test_project_relative_comparison_ignores_case(repo):
    mark(repo)
    assert edit(repo, str(repo).upper() + "/SRC/a.py").returncode == 2
    assert edit(repo, str(repo) + "/.CLAUDE/x.json").returncode == 0


def test_inplace_opt_out(repo):
    mark(repo)
    assert edit(repo, repo / "src" / "a.py").returncode == 2
    r = sl_inplace(repo, "--reason", "typo")
    assert r.returncode == 0, r.stderr
    data = json.loads((repo / ".superlite" / "inline-flow.json").read_text(encoding="utf-8"))
    assert data["inplace"] == "typo" and data["flow"] == "small" and data["at"] == 1
    assert "Ruling: in place - typo" in (repo / ".superlite" / "progress.md").read_text(encoding="utf-8").splitlines()
    assert edit(repo, repo / "src" / "a.py").returncode == 0


def test_inplace_needs_a_reason_and_a_marker(repo):
    mark(repo)
    assert sl_inplace(repo).returncode == 2
    assert sl_inplace(repo, "--reason", "  ").returncode == 2
    assert json.loads((repo / ".superlite" / "inline-flow.json").read_text())["inplace"] is None
    (repo / ".superlite" / "inline-flow.json").unlink()
    r = sl_inplace(repo, "--reason", "typo")
    assert r.returncode == 0 and "no inline flow" in r.stderr
    assert not (repo / ".superlite" / "inline-flow.json").exists()
    assert not (repo / ".superlite" / "progress.md").exists()


def test_inplace_keeps_the_reason_json_safe(repo):
    mark(repo, "tdd")
    assert sl_inplace(repo, "--reason", 'say "hi" \\ done').returncode == 0
    assert json.loads((repo / ".superlite" / "inline-flow.json").read_text(encoding="utf-8"))["inplace"] == 'say "hi" \\ done'
    assert edit(repo, repo / "src" / "a.py").returncode == 0


def test_subagent_and_worker_pass(repo):
    mark(repo)
    assert edit(repo, repo / "src" / "a.py", agent_id="a1").returncode == 0
    assert edit(repo, repo / "src" / "a.py", SUPERLITE_FLEET_WORKER="W1").returncode == 0
    assert edit(repo, repo / "src" / "a.py").returncode == 2


def test_other_tools_and_bad_input_pass(repo):
    mark(repo)
    for raw in ("", "not json", json.dumps({"tool_name": "Read", "tool_input": {"file_path": str(repo / "src" / "a.py")}}),
                json.dumps({"tool_name": "Edit", "tool_input": {}}), '{"tool_name": "Edit", "tool_input": {"file_path": "'):
        assert edit(repo, "x", raw=raw).returncode == 0, raw


def test_no_git_dir_passes(tmp_path):
    (tmp_path / ".superlite").mkdir()
    mark(tmp_path)
    assert edit(tmp_path, tmp_path / "a.py").returncode == 0


def test_lf_endings():
    assert b"\r" not in HOOK.read_bytes()
