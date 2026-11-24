"""#1140: commit_task's import check (_pyrun.project_env) and #1120's VIRTUAL_ENV export follow #1133's per-tree rule: the main checkout's .venv is another checkout's environment for a root in a linked worktree or task tree."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import _pyrun  # noqa: E402

UV = "/opt/bin/uv"
CMD = "uv run --no-project --with pytest python -m pytest a.py -q"


@pytest.fixture(autouse=True)
def _no_virtual_env(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)


@pytest.fixture
def uv_on_path(monkeypatch):
    monkeypatch.setattr(_pyrun.shutil, "which", lambda name: UV if name == "uv" else None)


def touch(base, rel, text=""):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(text)
    return p


def linked(main, wt, name):
    """wt laid out as git writes a linked worktree of main (no git run)."""
    gitdir = main / ".git" / "worktrees" / name
    gitdir.mkdir(parents=True, exist_ok=True)
    (gitdir / "commondir").write_text("../..\n")
    wt.mkdir(parents=True, exist_ok=True)
    (wt / ".git").write_text(f"gitdir: {gitdir}\n")
    return wt


def uv_project(root):
    touch(root, "uv.lock")
    touch(root, "pyproject.toml", "[project]\nname = 'where1140'\n")


def nested(tmp_path):
    main = tmp_path.resolve() / "main"
    py = touch(main, ".venv/bin/python")
    return main, py, linked(main, main / ".claude" / "worktrees" / "wt", "wt")


def base(main, root):
    return f"{main / '.venv'} is the main checkout's environment, outside {root}"


def test_uv_worktree_runs_its_own_env(tmp_path, uv_on_path):
    main, py, wt = nested(tmp_path)
    uv_project(wt)
    argv = [UV, "run", "--frozen", "--project", str(wt), "python"]
    assert _pyrun.other_checkout_python(wt) == str(py)
    assert _pyrun.project_env(wt) == (argv, f"{base(main, wt)}; running the import check in {wt}'s own environment: uv run --frozen --project {wt} (#1140)")
    assert _pyrun.project_cmd(wt) == argv


def test_task_tree_in_a_worktree_runs_its_own_env(tmp_path, uv_on_path):
    main, py, wt = nested(tmp_path)
    tree = linked(main, wt / ".superlite" / "trees" / "T1", "T1")
    uv_project(tree)
    assert _pyrun.project_cmd(tree) == [UV, "run", "--frozen", "--project", str(tree), "python"]


def test_worktree_without_lock_keeps_main_env_with_note(tmp_path, uv_on_path):
    main, py, wt = nested(tmp_path)
    touch(wt, "pyproject.toml")
    assert _pyrun.project_env(wt) == ([str(py)], f"{base(main, wt)}, and {wt} has no uv.lock for an environment of its own; the import check may import that folder's package, not {wt}'s (#1140)")


def test_uv_missing_keeps_main_env_with_note(tmp_path, monkeypatch):
    main, py, wt = nested(tmp_path)
    uv_project(wt)
    monkeypatch.setattr(_pyrun.shutil, "which", lambda name: None)
    assert _pyrun.project_env(wt) == ([str(py)], f"{base(main, wt)}, and uv is not on PATH for {wt}'s own environment; the import check may import that folder's package, not {wt}'s (#1140)")


def test_own_venv_has_no_note(tmp_path, uv_on_path):
    main, py, wt = nested(tmp_path)
    uv_project(wt)
    own = touch(wt, ".venv/bin/python")
    assert _pyrun.other_checkout_python(wt) is None
    assert _pyrun.project_env(wt) == ([str(own)], "")


def test_main_checkout_and_its_subfolder_keep_their_env(tmp_path, uv_on_path):
    main, py, wt = nested(tmp_path)
    sub = main / "pkg"
    uv_project(sub)
    uv_project(main)
    assert _pyrun.project_env(main) == ([str(py)], "")
    assert _pyrun.other_checkout_python(sub) is None
    assert _pyrun.project_env(sub) == ([str(py)], "")


def test_no_repository_gives_no_other_checkout(tmp_path):
    assert _pyrun.other_checkout_python(tmp_path / "nowhere") is None


def test_virtual_env_without_main_venv_is_unchanged(tmp_path, monkeypatch, uv_on_path):
    main = tmp_path.resolve() / "main"
    (main / ".git").mkdir(parents=True)
    wt = linked(main, tmp_path.resolve() / "wt", "wt")
    uv_project(wt)
    vpy = touch(tmp_path, "venv/bin/python")
    monkeypatch.setenv("VIRTUAL_ENV", str(tmp_path / "venv"))
    assert _pyrun.project_env(wt) == ([str(vpy)], "")


def test_project_cmd_keeps_the_project_python_seam(tmp_path, monkeypatch):
    main, py, wt = nested(tmp_path)
    monkeypatch.setattr(_pyrun, "project_python", lambda root: "/x/venv/bin/python")
    assert _pyrun.project_env(wt) == (["/x/venv/bin/python"], "")


def test_export_of_the_main_checkout_venv_names_it(tmp_path):
    main = tmp_path.resolve() / "main"
    touch(main, ".venv/bin/python")
    wt = linked(main, tmp_path.resolve() / "wt", "wt")
    cmd, env, note = _pyrun.uv_project_env(CMD, wt, wt, {})
    assert (cmd, env) == (CMD, {"VIRTUAL_ENV": str(main / ".venv")})
    assert note == (f"uv run --no-project finds no environment from {wt}; using the project's environment {main / '.venv'} (VIRTUAL_ENV), "
                    f"the main checkout's, outside {wt}; {wt} has no uv.lock for an environment of its own, so the tests may import that folder's package, not {wt}'s (#1140)")


def test_export_of_the_root_own_venv_keeps_the_1120_note(tmp_path):
    root = tmp_path.resolve() / "proj"
    touch(root, ".venv/bin/python")
    cwd = tmp_path.resolve() / "elsewhere"
    cwd.mkdir()
    cmd, env, note = _pyrun.uv_project_env(CMD, root, cwd, {})
    assert env == {"VIRTUAL_ENV": str(root / ".venv")}
    assert note == f"uv run --no-project finds no environment from {cwd}; using the project's environment {root / '.venv'} (VIRTUAL_ENV) (#1120)"
