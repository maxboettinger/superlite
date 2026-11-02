"""_pyrun.project_python: the project's own interpreter, never run, only looked up."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import _pyrun  # noqa: E402


@pytest.fixture(autouse=True)
def _no_virtual_env(monkeypatch):
    monkeypatch.delenv("VIRTUAL_ENV", raising=False)


def touch(base, rel):
    p = base / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("")
    return p


def test_root_venv_wins(tmp_path, monkeypatch):
    root = tmp_path / "proj"
    other = tmp_path / "other"
    touch(root, ".venv/bin/python")
    touch(other, "bin/python")
    monkeypatch.setenv("VIRTUAL_ENV", str(other))
    assert _pyrun.project_python(root) == str(root / ".venv/bin/python")


def test_root_venv_windows_layout(tmp_path):
    touch(tmp_path, ".venv/Scripts/python.exe")
    assert _pyrun.project_python(tmp_path) == str(tmp_path / ".venv/Scripts/python.exe")


def test_virtual_env_used(tmp_path, monkeypatch):
    venv = tmp_path / "x" / "venv"
    touch(venv, "bin/python")
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    root = tmp_path / "proj"
    root.mkdir()
    assert _pyrun.project_python(root) == str(venv / "bin/python")


def test_virtual_env_windows_layout(tmp_path, monkeypatch):
    venv = tmp_path / "venv"
    touch(venv, "Scripts/python.exe")
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    assert _pyrun.project_python(tmp_path / "proj") == str(venv / "Scripts/python.exe")


def test_falls_back_to_sys_executable(tmp_path):
    assert _pyrun.project_python(tmp_path) == sys.executable


def test_missing_interpreter_file_ignored(tmp_path, monkeypatch):
    (tmp_path / ".venv" / "bin").mkdir(parents=True)
    venv = tmp_path / "venv"
    (venv / "bin").mkdir(parents=True)
    monkeypatch.setenv("VIRTUAL_ENV", str(venv))
    assert _pyrun.project_python(tmp_path) == sys.executable


def test_empty_virtual_env_ignored(tmp_path, monkeypatch):
    monkeypatch.setenv("VIRTUAL_ENV", "")
    assert _pyrun.project_python(tmp_path) == sys.executable


def test_root_may_be_str(tmp_path):
    touch(tmp_path, ".venv/bin/python")
    got = _pyrun.project_python(str(tmp_path))
    assert isinstance(got, str)
    assert got == str(tmp_path / ".venv/bin/python")


def test_interpreter_not_resolved(tmp_path):
    real = touch(tmp_path, "real/python")
    link = tmp_path / ".venv" / "bin" / "python"
    link.parent.mkdir(parents=True)
    try:
        link.symlink_to(real)
    except OSError:
        pytest.skip("symlinks unavailable")
    assert _pyrun.project_python(tmp_path) == str(link)
