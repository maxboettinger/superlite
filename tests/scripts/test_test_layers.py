"""test_layers: matrix, stamps, Stop hook protocol."""
from __future__ import annotations

import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[2] / "scripts" / "test_layers.py"
spec = importlib.util.spec_from_file_location("test_layers", SCRIPT)
tl = importlib.util.module_from_spec(spec)
sys.modules["test_layers"] = tl
spec.loader.exec_module(tl)

FILES = ["hooks/x", "hooks/session-start", "skills/a/SKILL.md", "agents/a.md", "commands/a.md",
         "tests/e2e/harness.py", "evals/c/prompt.md"]


def git(root, *args):
    subprocess.run(["git", *args], cwd=root, check=True, capture_output=True)


@pytest.fixture
def repo(tmp_path):
    root = tmp_path / "repo"
    root.mkdir()
    git(root, "init", "-q")
    git(root, "config", "user.email", "a@b.c")
    git(root, "config", "user.name", "t")
    for f in FILES:
        p = root / f
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text("x\n")
    git(root, "add", "-A")
    git(root, "commit", "-qm", "init")
    return root


def cli(root, *args, stdin="", env=None):
    e = {**os.environ, "SUPERLITE_TEST_LAYERS": ""}
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), *args, "--root", str(root)], input=stdin,
                          capture_output=True, text=True, env=e)


def stamp_all(root):
    for layer in ("unit", "headless", "tui", "evals"):
        assert cli(root, "stamp", layer, "--ruling", "r").returncode == 0


def test_layers_for_matrix():
    assert tl.layers_for(["hooks/session-start"]) == ["unit", "headless", "tui"]
    assert tl.layers_for(["skills/brainstorming/SKILL.md"]) == ["headless", "evals"]
    assert tl.layers_for(["docs/testing.md"]) == []
    assert tl.layers_for(["README.md"], {"README.md": "+ set CLAUDE_CODE_FORK_SUBAGENT=0"}) == ["tui"]
    assert tl.layers_for(["tests/scripts/test_x.py"]) == ["unit"]
    assert tl.layers_for(["agents/implementer.md"]) == ["headless", "evals"]
    assert tl.layers_for(["evals/c/graders/g.md"]) == ["evals"]


def test_check_exit_codes(repo):
    r = cli(repo, "check")
    assert r.returncode == 2
    assert r.stdout.split() == ["unit", "headless", "tui", "evals"]
    stamp_all(repo)
    r = cli(repo, "check")
    assert (r.returncode, r.stdout) == (0, "")


def test_stamp_then_clean_is_not_stale(repo):
    cli(repo, "stamp", "headless", "--ruling", "r")
    assert "headless" not in cli(repo, "check").stdout.split()


def test_change_after_stamp_is_stale(repo):
    stamp_all(repo)
    with open(repo / "hooks" / "session-start", "a") as f:
        f.write("more\n")
    assert cli(repo, "check").stdout.split() == ["unit", "headless", "tui"]


def test_layer_hash_ignores_untracked_results(repo):
    before = tl.layer_hash("evals", repo)
    (repo / "evals" / "results").mkdir()
    (repo / "evals" / "results" / "last.json").write_text("{}")
    assert tl.layer_hash("evals", repo) == before
    (repo / "evals" / "c" / "new.md").write_text("n")
    assert tl.layer_hash("evals", repo) != before


def test_hook_blocks_with_layers_and_commands(repo):
    stamp_all(repo)
    (repo / "agents" / "a.md").write_text("changed\n")
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": False, "cwd": str(repo)}))
    assert r.returncode == 0
    out = json.loads(r.stdout.strip())
    assert out["decision"] == "block"
    assert "headless" in out["reason"]
    assert "python3 scripts/test_layers.py run headless" in out["reason"]


def test_hook_silent_when_stop_hook_active(repo):
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": True, "cwd": str(repo)}))
    assert (r.returncode, r.stdout) == (0, "")
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": False, "cwd": str(repo)}),
            env={"SUPERLITE_TEST_LAYERS": "off"})
    assert (r.returncode, r.stdout) == (0, "")
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": True}),
            env={"SUPERLITE_TEST_LAYERS": "off"})
    assert (r.returncode, r.stdout) == (0, "")


def test_hook_silent_during_active_run(repo):
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "pool.json").write_text("{}")
    r = cli(repo, "check", "--hook", stdin=json.dumps({"stop_hook_active": False, "cwd": str(repo)}))
    assert (r.returncode, r.stdout) == (0, "")


def test_run_stamps_only_green_layers(repo):
    r = cli(repo, "run", "unit", "headless", "--command-override", "unit=true", "headless=false")
    assert r.returncode == 1
    assert "unit: green" in r.stdout and "headless: red" in r.stdout
    stale = cli(repo, "check").stdout.split()
    assert "unit" not in stale and "headless" in stale


def test_default_e2e_commands_use_sl_run_tests():
    for layer, name in (("headless", "test_headless"), ("tui", "test_tui")):
        cmd = tl.COMMANDS[layer]
        assert f"run_tests --fast tests/e2e/{name}.py" in cmd
        assert "-m pytest" not in cmd


def test_run_sets_superlite_e2e_for_e2e_layers_only(repo, tmp_path):
    out = tmp_path / "out"
    env = {"SUPERLITE_E2E": ""}
    over = [f"{layer}=printf %s \"$SUPERLITE_E2E\" > {out}-{layer}" for layer in ("unit", "headless")]
    assert cli(repo, "run", "unit", "headless", "--command-override", *over, env=env).returncode == 0
    assert (Path(f"{out}-headless").read_text(), Path(f"{out}-unit").read_text()) == ("1", "")


def test_stamp_ruling_appends_progress_line(repo):
    assert cli(repo, "stamp", "tui", "--ruling", "no tmux here").returncode == 0
    text = (repo / ".superlite" / "progress.md").read_text()
    assert "Ruling: skip tui - no tmux here" in text


def test_hook_never_raises_on_bad_cwd():
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "--hook"],
                       input=json.dumps({"cwd": ["not", "a", "path"]}), capture_output=True, text=True,
                       env={**os.environ, "SUPERLITE_TEST_LAYERS": ""}, cwd="/")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    r = subprocess.run([sys.executable, str(SCRIPT), "check", "--hook"], input="{not json",
                       capture_output=True, text=True, env={**os.environ, "SUPERLITE_TEST_LAYERS": ""},
                       cwd="/")
    assert r.returncode == 0 and r.stderr == ""


def test_tui_keyword_file_is_stamped_clear_and_plans_skipped(repo):
    (repo / "README.md").write_text("set CLAUDE_CODE_FORK_SUBAGENT=0\n")
    (repo / "docs" / "plans").mkdir(parents=True)
    (repo / "docs" / "plans" / "p.md").write_text("agent_summary\n")
    assert "README.md" in tl.layer_files("tui", repo)
    assert "docs/plans/p.md" not in tl.layer_files("tui", repo)
    cli(repo, "stamp", "tui", "--ruling", "r")
    git(repo, "add", "-A")
    git(repo, "commit", "-qm", "c")
    assert "tui" not in cli(repo, "check").stdout.split()
    (repo / "README.md").write_text("changed CLAUDE_CODE_FORK_SUBAGENT=1\n")
    assert "tui" in cli(repo, "check").stdout.split()


def test_stale_layers_ignores_unmapped(tmp_path):
    root = tmp_path / "r"
    root.mkdir()
    git(root, "init", "-q")
    (root / "docs").mkdir()
    (root / "docs" / "a.md").write_text("x")
    assert tl.stale_layers(root, root / "s.json") == []


def hook_no_root(cwd, stdin):
    return subprocess.run([sys.executable, str(SCRIPT), "check", "--hook"], input=stdin, capture_output=True,
                          text=True, env={**os.environ, "SUPERLITE_TEST_LAYERS": ""}, cwd=cwd)


def test_hook_silent_on_empty_stdin(tmp_path):
    r = hook_no_root(tmp_path, "")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_hook_silent_on_non_json_stdin(tmp_path):
    r = hook_no_root(tmp_path, "{not json")
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_hook_silent_in_git_worktree_cwd(repo, tmp_path):
    wt = tmp_path / "wt"
    git(repo, "worktree", "add", "-q", str(wt), "-b", "side")
    assert (wt / ".git").is_file()
    for layer in ("unit", "headless", "tui", "evals"):
        assert cli(wt, "stamp", layer, "--ruling", "r").returncode == 0
    r = hook_no_root("/", json.dumps({"stop_hook_active": False, "cwd": str(wt)}))
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")
    (wt / "agents" / "a.md").write_text("changed\n")
    r = hook_no_root("/", json.dumps({"cwd": str(wt)}))
    assert r.returncode == 0 and json.loads(r.stdout)["decision"] == "block"


def test_hook_silent_in_non_repo_cwd(tmp_path):
    plain = tmp_path / "plain"
    plain.mkdir()
    (plain / "hooks").mkdir()
    (plain / "hooks" / "x").write_text("x")
    r = hook_no_root("/", json.dumps({"cwd": str(plain)}))
    assert (r.returncode, r.stdout, r.stderr) == (0, "", "")


def test_layers_for_normalises_backslash_paths():
    assert tl.layers_for(["hooks\\session-start"]) == tl.layers_for(["hooks/session-start"])
    assert tl.layers_for(["hooks\\session-start"]) == ["unit", "headless", "tui"]
    assert tl.layers_for(["evals\\results\\x.json"]) == []
    assert tl.layers_for(["README.md"], {"README.md": "agent_summary"}) == ["tui"]


def test_layer_hash_ignores_results_and_superlite_state(repo):
    before = {l: tl.layer_hash(l, repo) for l in ("evals", "unit")}
    (repo / "evals" / "results").mkdir()
    (repo / "evals" / "results" / "run.json").write_text("{}")
    (repo / ".superlite").mkdir()
    (repo / ".superlite" / "progress.md").write_text("p")
    (repo / ".superlite" / "test-layers.json").write_text("{}")
    assert {l: tl.layer_hash(l, repo) for l in before} == before
    (repo / "evals" / "results" / "run.json").write_text('{"changed": 1}')
    assert {l: tl.layer_hash(l, repo) for l in before} == before
