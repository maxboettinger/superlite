"""#1120: the Node guard walks parent folders like Node and names the remote route; a `uv run --no-project` command runs in the project's environment."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
RUN_TESTS = SCRIPTS / "run_tests.py"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

PKG = json.dumps({"devDependencies": {"vitest": "1"}})
SPEC = {"language": "typescript", "python": False, "setup": "", "command": "npx vitest run a.test.ts", "junit": "", "env": {}}
HINT = ('; the project\'s "test" runs through maxapp remote: install here, or give "test_file" the same maxapp remote form '
        "so --fast runs there (#1120)")


def project(path, config=None):
    path.mkdir(parents=True, exist_ok=True)
    (path / "package.json").write_text(PKG)
    if config is not None:
        (path / ".superlite").mkdir(exist_ok=True)
        (path / ".superlite" / "test-cmd.json").write_text(json.dumps(config))
    return path


def test_worktree_under_checkout_with_node_modules_runs(tmp_path):
    repo = project(tmp_path / "repo")
    (repo / ".git").mkdir()
    (repo / "node_modules").mkdir()
    wt = project(repo / ".claude" / "worktrees" / "wt")
    (wt / ".git").write_text("gitdir: elsewhere\n")
    assert run_tests.node_install_line(wt, SPEC) is None


def test_parent_without_git_dir_not_searched(tmp_path):
    (tmp_path / "node_modules").mkdir()
    root = project(tmp_path / "a" / "b")
    line = run_tests.node_install_line(root, SPEC)
    assert line and line.startswith(f"node_modules missing in {root}: run ")


def test_remote_test_hint(tmp_path):
    root = project(tmp_path / "p", {"language": "typescript", "test": "maxapp remote 'npm test'",
                                    "test_file": "npx vitest run {files}"})
    line = run_tests.node_install_line(root, SPEC)
    assert line and line.startswith("node_modules missing in ") and line.endswith(HINT)


def test_no_hint_for_local_test(tmp_path):
    root = project(tmp_path / "p", {"language": "typescript", "test": "npm test", "test_file": "npx vitest run {files}"})
    assert "maxapp remote" not in run_tests.node_install_line(root, SPEC)


FAKE_UV = """#!/bin/sh
printf '%s\\n' "$*" > "$FAKE_OUT"
printf '%s\\n' "${VIRTUAL_ENV:-}" >> "$FAKE_OUT"
echo '1 passed in 0.01s'
"""
UV_CFG = {"language": "python", "test": "true",
          "test_file": "uv run --no-project --with pytest python -m pytest {files} -q"}


def run_uv(root, tmp_path, monkeypatch):
    bindir = tmp_path / "fakebin"
    bindir.mkdir(exist_ok=True)
    uv = bindir / "uv"
    uv.write_text(FAKE_UV)
    uv.chmod(0o755)
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)
    env = {**os.environ, "PATH": f"{bindir}{os.pathsep}{os.environ['PATH']}", "FAKE_OUT": str(tmp_path / "out.txt")}
    env.pop("VIRTUAL_ENV", None)
    (root / ".superlite").mkdir(exist_ok=True)
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps(UV_CFG))
    (root / "tests").mkdir(exist_ok=True)
    (root / "tests" / "test_a.py").write_text("def test_a():\n    pass\n")
    r = subprocess.run([sys.executable, str(RUN_TESTS), "--fast", "tests/test_a.py"], cwd=root, env=env,
                       capture_output=True, text=True, timeout=120)
    out = (tmp_path / "out.txt").read_text().splitlines() if (tmp_path / "out.txt").exists() else []
    return r, out


@pytest.mark.skipif(os.name == "nt", reason="posix sh script")
def test_uv_no_project_rewritten_in_run(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    root.mkdir()
    (root / "uv.lock").write_text("")
    (root / "pyproject.toml").write_text("[project]\nname='x'\n")
    r, out = run_uv(root, tmp_path, monkeypatch)
    assert r.returncode == 0, r.stderr
    assert f"--frozen --project {root.resolve()}" in out[0] or f"--frozen --project {root}" in out[0]
    assert "--no-project" not in out[0]
    assert "run_tests: uv run --no-project finds no environment from " in r.stderr


@pytest.mark.skipif(os.name == "nt", reason="posix sh script")
def test_uv_virtual_env_exported(tmp_path, monkeypatch):
    main = tmp_path.resolve() / "main"
    (main / ".venv" / "bin").mkdir(parents=True)
    (main / ".venv" / "bin" / "python").write_text("")
    gitdir = main / ".git" / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    wt = tmp_path.resolve() / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    r, out = run_uv(wt, tmp_path.resolve(), monkeypatch)
    assert r.returncode == 0, r.stderr
    assert out[1] == str(main / ".venv")
    assert "using the project's environment" in r.stderr
