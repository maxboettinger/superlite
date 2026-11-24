"""#1133: run_tests --fast in a worktree nested in the main checkout imports the worktree's package, not main's: a `uv run --no-project` command whose only environment is a .venv above the run root runs in the root's own `uv run --frozen --project` environment."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import _pyrun  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
CMD = "uv run --no-project --with pytest python -m pytest a.py -q"


@pytest.fixture(autouse=True)
def _no_virtual_env(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)


def touch(base, rel, text=""):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def uv_project(root):
    touch(root, "uv.lock")
    touch(root, "pyproject.toml", "[project]\nname = 'where1133'\n")


def nested(tmp_path):
    """A main checkout with a .venv and a worktree nested in it, as .claude/worktrees/wt."""
    main = tmp_path.resolve() / "main"
    touch(main, ".venv/bin/python")
    return main, main / ".claude" / "worktrees" / "wt"


def test_parent_venv_above_uv_root_runs_root_env(tmp_path):
    main, wt = nested(tmp_path)
    uv_project(wt)
    assert _pyrun.uv_project_env(CMD, wt, wt, {}) == (
        f"uv run --frozen --project {wt} --with pytest python -m pytest a.py -q",
        {},
        f"uv run --no-project would use {main / '.venv'}, which lies outside {wt}; running in {wt}'s own environment: uv run --frozen --project {wt} (#1133)",
    )


def test_task_tree_below_worktree_venv_runs_tree_env(tmp_path):
    main, wt = nested(tmp_path)
    touch(wt, ".venv/bin/python")
    tree = wt / ".superlite" / "trees" / "T1"
    uv_project(tree)
    cmd, env, note = _pyrun.uv_project_env(CMD, tree, tree, {})
    assert cmd == f"uv run --frozen --project {tree} --with pytest python -m pytest a.py -q"
    assert env == {}
    assert note.startswith(f"uv run --no-project would use {wt / '.venv'}, which lies outside {tree};")


def test_venv_in_root_untouched(tmp_path):
    main, wt = nested(tmp_path)
    uv_project(wt)
    touch(wt, ".venv/bin/python")
    assert _pyrun.uv_project_env(CMD, wt, wt, {}) == (CMD, {}, "")


@pytest.mark.parametrize("venv_at", [".", "packages/x"])
def test_run_folder_below_root_untouched(tmp_path, venv_at):
    main, wt = nested(tmp_path)
    uv_project(wt)
    touch(wt / venv_at, ".venv/bin/python")
    assert _pyrun.uv_project_env(CMD, wt, wt / "packages" / "x", {}) == (CMD, {}, "")


@pytest.mark.skipif(os.name == "nt", reason="symlink")
def test_symlinked_cwd_compares_resolved(tmp_path):
    real = tmp_path.resolve() / "real"
    uv_project(real)
    touch(real, ".venv/bin/python")
    link = tmp_path.resolve() / "link"
    link.symlink_to(real)
    assert _pyrun.uv_project_env(CMD, real, link, {}) == (CMD, {}, "")


def test_parent_venv_without_lock_notes_only(tmp_path):
    main, wt = nested(tmp_path)
    wt.mkdir(parents=True)
    assert _pyrun.uv_project_env(CMD, wt, wt, {}) == (
        CMD,
        {},
        f"uv run --no-project would use {main / '.venv'}, which lies outside {wt}, and {wt} has no uv.lock for an environment of its own; the tests may import that folder's package, not {wt}'s (#1133)",
    )


def test_virtual_env_wins_over_parent_venv(tmp_path):
    main, wt = nested(tmp_path)
    uv_project(wt)
    assert _pyrun.uv_project_env(CMD, wt, wt, {"VIRTUAL_ENV": str(main / ".venv")}) == (CMD, {}, "")


# A stand-in for uv. `run --project P` syncs P/.venv, whose editable install puts P/src on sys.path;
# `run --no-project` uses the first .venv from the cwd up, as uv does. site.txt names the folder an
# environment's editable install puts on sys.path (main's .venv names main's src: the .pth seen in #1133).
FAKE_UV = r'''
import os
import sys
from pathlib import Path

args = sys.argv[2:]
env_dir, i = None, 0
while i < len(args) and args[i].startswith("-"):
    if args[i] == "--project":
        project = Path(args[i + 1])
        env_dir = project / ".venv"
        (env_dir / "bin").mkdir(parents=True, exist_ok=True)
        (env_dir / "bin" / "python").write_text("")
        (env_dir / "site.txt").write_text(str(project / "src"))
    i += 2 if args[i] in ("--project", "--with", "--python", "--group") else 1
if env_dir is None:
    here = Path.cwd()
    env_dir = next((f / ".venv" for f in (here, *here.parents) if (f / ".venv" / "site.txt").is_file()), None)
src = (env_dir / "site.txt").read_text() if env_dir else ""
os.execve(sys.executable, [sys.executable, *args[i + 1:]], {**os.environ, "PYTHONPATH": src})
'''
CFG = {"language": "python", "test": "true",
       "test_file": "uv run --no-project --with pytest python -m pytest {files} -q -p no:cacheprovider"}


def checkout(tmp_path):
    main, wt = nested(tmp_path)
    touch(main, ".venv/site.txt", str(main / "src"))
    touch(main, "src/where1133/__init__.py", "WHERE = 'main'\n")
    uv_project(wt)
    touch(wt, "src/where1133/__init__.py", "WHERE = 'tree'\n")
    touch(wt, "tests/test_where.py", "import where1133\n\n\ndef test_imports_the_tree():\n    assert where1133.WHERE == 'tree'\n")
    touch(wt, ".superlite/test-cmd.json", json.dumps(CFG))
    return main, wt


def run_fast(wt, tmp_path):
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    (bindir / "fake_uv.py").write_text(FAKE_UV)
    uv = bindir / "uv"
    uv.write_text(f'#!/bin/sh\nexec "{sys.executable}" "{bindir / "fake_uv.py"}" "$@"\n')
    uv.chmod(0o755)
    env = {k: v for k, v in os.environ.items()
           if k != "VIRTUAL_ENV" and not k.startswith(("SUPERLITE_FLEET_", "SUPERLITE_STATE_DIR"))}
    env["PATH"] = f"{bindir}{os.pathsep}{os.environ['PATH']}"
    return subprocess.run([sys.executable, str(RUN_TESTS), "--fast", "tests/test_where.py"], cwd=wt, env=env,
                          capture_output=True, text=True, timeout=120)


@pytest.mark.skipif(os.name == "nt", reason="posix sh script")
def test_fast_in_nested_worktree_imports_the_worktree_package(tmp_path):
    main, wt = checkout(tmp_path)
    r = run_fast(wt, tmp_path)
    assert r.returncode == 0, r.stdout + r.stderr
    assert f"running in {wt}'s own environment: uv run --frozen --project {wt} (#1133)" in r.stderr
    again = run_fast(wt, tmp_path)
    assert again.returncode == 0, again.stdout + again.stderr
    assert "(#1133)" not in again.stderr
