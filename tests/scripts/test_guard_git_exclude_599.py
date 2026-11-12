"""#599: appending to the git exclude file passes from a linked worktree."""
import json
import os
import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
HOOK = ROOT / "hooks" / "block-coordinator-edits"
BASH = shutil.which("bash")
GIT_ENV = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(cwd, *a):
    env = {k: v for k, v in os.environ.items() if not k.startswith("GIT_")}
    subprocess.run(["git", "-C", str(cwd), *a], check=True, capture_output=True, env={**env, **GIT_ENV})


def run(proj, cmd):
    env = {k: v for k, v in os.environ.items()
           if k not in ("SUPERLITE_STATE_DIR", "SUPERLITE_SESSION_ID") and not k.startswith("SUPERLITE_FLEET_")}
    env["CLAUDE_PROJECT_DIR"] = str(proj)
    raw = json.dumps({"tool_name": "Bash", "tool_input": {"command": cmd}, "cwd": str(proj)})
    return subprocess.run([BASH, str(HOOK)], input=raw, capture_output=True, text=True, env=env, cwd=str(proj)).returncode


@pytest.fixture
def wt(tmp_path):
    main = tmp_path / "main"
    main.mkdir()
    git(main, "init", "-q")
    (main / "a.txt").write_text("x")
    git(main, "add", "-A")
    git(main, "commit", "-q", "-m", "init")
    git(main, "worktree", "add", "-q", ".claude/worktrees/w1", "-b", "w1")
    w = main / ".claude" / "worktrees" / "w1"
    (w / ".superlite").mkdir()
    (w / ".superlite" / "pool.json").write_text("{}")
    return w


@pytest.fixture
def plain(tmp_path):
    p = tmp_path / "plain"
    p.mkdir()
    git(p, "init", "-q")
    (p / ".superlite").mkdir()
    (p / ".superlite" / "pool.json").write_text("{}")
    return p


PATH_FORM = """printf 'graphify-out/\\n' >> "$(git rev-parse --git-path info/exclude)\""""


def test_git_path_form_passes(wt):
    assert run(wt, PATH_FORM) == 0


def test_common_dir_form_passes(wt):
    assert run(wt, """printf 'graphify-out/\\n' >> "$(git rev-parse --git-common-dir)/info/exclude\"""") == 0


def test_main_checkout_form_passes(plain):
    assert run(plain, PATH_FORM) == 0


def test_compound_call_passes(wt):
    assert run(wt, """printf 'x/\\n' >> "$(git rev-parse --git-path info/exclude)" && echo done""") == 0


def test_other_substitutions_block(wt):
    assert run(wt, 'echo x >> "$(git rev-parse --show-toplevel)/src.py"') == 2
    assert run(wt, 'echo x >> "$(git rev-parse --git-path hooks/pre-commit)"') == 2


def test_git_env_keeps_unknown(wt):
    assert run(wt, 'export GIT_DIR=src; echo x >> "$(git rev-parse --git-path info/exclude)"') == 2
