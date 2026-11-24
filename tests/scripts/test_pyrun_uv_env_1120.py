"""#1120: uv_project_env rewrites or supplements a `uv run --no-project` command that finds no Python environment."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import _pyrun  # noqa: E402

CMD = "uv run --no-project --with pytest python -m pytest a.py -q"


@pytest.fixture(autouse=True)
def _no_virtual_env(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)


def touch(base, rel):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    return p


def uv_project(root):
    touch(root, "uv.lock")
    touch(root, "pyproject.toml")


def test_rewrite_when_no_env(tmp_path):
    root = tmp_path / "t"
    uv_project(root)
    out = _pyrun.uv_project_env(CMD, root, root, {})
    assert out == (
        f"uv run --frozen --project {root} --with pytest python -m pytest a.py -q",
        {},
        f"uv run --no-project finds no environment from {root}; running in the project's environment: uv run --frozen --project {root} (#1120)",
    )


def test_root_with_space_is_quoted(tmp_path):
    root = tmp_path / "t x"
    uv_project(root)
    cmd, _, _ = _pyrun.uv_project_env(CMD, root, root, {})
    assert f"--project '{root}' --with" in cmd


def test_virtual_env_set_leaves_command(tmp_path):
    root = tmp_path / "t"
    uv_project(root)
    assert _pyrun.uv_project_env(CMD, root, root, {"VIRTUAL_ENV": "/v"}) == (CMD, {}, "")


def test_parent_venv_leaves_command(tmp_path):
    touch(tmp_path / "m", ".venv/bin/python")
    wt = tmp_path / "m" / "wt"
    uv_project(wt)
    assert _pyrun.uv_project_env(CMD, wt, wt, {}) == (CMD, {}, "")


def test_main_checkout_venv_exported(tmp_path):
    main = tmp_path.resolve() / "main"
    touch(main, ".venv/bin/python")
    gitdir = main / ".git" / "worktrees" / "wt"
    gitdir.mkdir(parents=True)
    (gitdir / "commondir").write_text("../..\n")
    wt = tmp_path.resolve() / "wt"
    wt.mkdir()
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    cmd, env, note = _pyrun.uv_project_env(CMD, wt, wt, {})
    assert cmd == CMD
    assert env == {"VIRTUAL_ENV": str(main / ".venv")}
    assert note == f"uv run --no-project finds no environment from {wt}; using the project's environment {main / '.venv'} (VIRTUAL_ENV) (#1120)"


def test_no_lock_no_venv_note_only(tmp_path):
    root = tmp_path / "t"
    root.mkdir()
    assert _pyrun.uv_project_env(CMD, root, root, {}) == (
        CMD,
        {},
        f"uv run --no-project finds no environment from {root} and {root} has no uv.lock; the project's own package may not import (#1120)",
    )


def test_not_no_project_untouched(tmp_path):
    cmd = "uv run --group dev python -m pytest a.py"
    assert _pyrun.uv_project_env(cmd, tmp_path, tmp_path, {}) == (cmd, {}, "")


def test_no_project_after_program_untouched(tmp_path):
    cmd = "uv run python -m pytest --no-project"
    assert _pyrun.uv_project_env(cmd, tmp_path, tmp_path, {}) == (cmd, {}, "")


def test_env_prefix_and_path_uv(tmp_path):
    uv_project(tmp_path)
    cmd, _, note = _pyrun.uv_project_env("A=1 /opt/bin/uv run --no-project python x.py", tmp_path, tmp_path, {})
    assert cmd == f"A=1 /opt/bin/uv run --frozen --project {tmp_path} python x.py"
    assert note


def test_unparsable_untouched(tmp_path):
    cmd = "uv run --no-project python 'x.py"
    assert _pyrun.uv_project_env(cmd, tmp_path, tmp_path, {}) == (cmd, {}, "")


@pytest.mark.parametrize("cmd", [
    "uv run --with pytest --no-project python -m pytest a.py -q",
    "uv run --python python3.12 --no-project pytest a.py",
    "uv run --with=pytest --no-project pytest a.py",
])
def test_value_option_before_no_project_rewritten(tmp_path, cmd):
    root = tmp_path / "t"
    uv_project(root)
    out, _, _ = _pyrun.uv_project_env(cmd, root, root, {})
    assert "--frozen --project" in out and "--no-project" not in out
