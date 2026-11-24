"""#1131: state.default_dir() and state.default_root() name the folder and root a tool's bare default stands for."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_session_state import state  # noqa: F401
from test_state_plugin_folder_1116 import A, plug  # noqa: F401


@pytest.fixture
def plain(tmp_path, monkeypatch):
    for v in ("SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "SUPERLITE_PROJECT_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SUPERLITE_SESSION_ID", A)
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    (tmp_path / "w").mkdir()
    monkeypatch.chdir(tmp_path / "w")
    monkeypatch.setenv("PWD", str(tmp_path / "w"))
    return tmp_path


def test_default_dir_outside_plugin_is_cwd_folder(plain):
    assert state.default_dir() == Path(".superlite")


def test_default_dir_env_wins(plain, monkeypatch):
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(plain / "s" / ".superlite"))
    assert state.default_dir() == plain / "s" / ".superlite"


def test_default_dir_from_plugin_goes_to_session_project(plug, monkeypatch):
    tmp, _, _, proj = plug
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    assert state.default_dir() == proj / ".superlite"
    assert not any((tmp / "plugin" / "skills").rglob(".superlite"))


def _linked(tmp, monkeypatch):
    main = tmp / "main"
    (main / ".git").mkdir(parents=True)
    w = main / ".claude" / "worktrees" / "x"
    w.mkdir(parents=True)
    (w / ".git").write_text(f"gitdir: {main}/.git/worktrees/x\n")
    monkeypatch.chdir(w)
    monkeypatch.setenv("PWD", str(w))
    return w


def test_default_dir_foreign_binding_keeps_cwd_folder(plain, monkeypatch, capsys):
    w = _linked(plain, monkeypatch)
    other = plain / "elsewhere" / ".superlite"
    other.mkdir(parents=True)
    state.bind(other, sid=A)
    assert state.resolve(strict=False) == other
    assert state.default_dir() == state.plan_dir(".superlite")
    assert state.default_dir() == w / ".superlite"
    assert "session binding names" not in capsys.readouterr().err


def test_default_root_outside_plugin_is_dot(plain, monkeypatch):
    assert state.default_root() == Path(".")
    other = plain / "elsewhere" / ".superlite"
    other.mkdir(parents=True)
    state.bind(other, sid=A)
    assert state.default_root() == Path(".")


def test_default_root_from_plugin_is_session_project(plug, monkeypatch):
    _, _, _, proj = plug
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    assert state.default_root() == proj


def test_default_root_from_plugin_private_folder_refuses(plug, capsys):
    with pytest.raises(state.Refused) as e:
        state.default_root()
    assert e.value.code == 2
    assert "lies inside the superlite plugin" in capsys.readouterr().err


def test_default_root_from_plugin_no_session_refuses(plug, monkeypatch):
    monkeypatch.delenv("SUPERLITE_SESSION_ID")
    monkeypatch.delenv("CLAUDE_CODE_SESSION_ID", raising=False)
    with pytest.raises(state.Refused) as e:
        state.default_root()
    assert e.value.code == 2
