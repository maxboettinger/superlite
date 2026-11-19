"""sl testcmd prints the default pytest command run_tests runs for a Python project without a configured test (#806)."""
from __future__ import annotations

import json
import shlex
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import _pyrun as pyrun  # noqa: E402
import testcmd  # noqa: E402

TAIL = ["-q", "-rP", "-p", "no:cacheprovider", "-o", "junit_family=xunit1"]


@pytest.fixture
def root(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(tmp_path / "no-user-config.json"))
    r = tmp_path / "proj"
    (r / "tests").mkdir(parents=True)
    (r / "tests" / "test_x.py").write_text("def test_x():\n    pass\n", encoding="utf-8")
    (r / "pyproject.toml").write_text("[project]\nname = 'p'\n", encoding="utf-8")
    return r


def cli(root, capsys, *extra):
    rc = testcmd.main(["--root", str(root), *extra])
    cap = capsys.readouterr()
    return rc, json.loads(cap.out), cap.err


def test_python_command_default_full(root, monkeypatch):
    monkeypatch.setattr(pyrun, "have_pytest", lambda: True)
    assert testcmd.python_command(root, []) == [sys.executable, "-m", "pytest", "tests", *TAIL, "--junitxml={junit}"]


def test_python_command_paths_marker_junit(root, monkeypatch):
    monkeypatch.setattr(pyrun, "have_pytest", lambda: True)
    cmd = testcmd.python_command(root, ["tests/test_a.py"], marker="slow", junit="/x/j.xml")
    assert cmd == [sys.executable, "-m", "pytest", "tests/test_a.py", "-m", "slow", *TAIL, "--junitxml=/x/j.xml"]


def test_python_command_uv_fallback(root, monkeypatch):
    monkeypatch.setattr(pyrun, "have_pytest", lambda: False)
    monkeypatch.setattr(pyrun.shutil, "which", lambda name: "/x/uv")
    cmd = testcmd.python_command(root, [])
    assert cmd[:9] == ["/x/uv", "run", "--no-project", "--with", "pytest", "python", "-m", "pytest", "tests"]


def test_python_command_neither_raises(root, monkeypatch):
    monkeypatch.setattr(pyrun, "have_pytest", lambda: False)
    monkeypatch.setattr(pyrun.shutil, "which", lambda name: None)
    with pytest.raises(pyrun.PytestUnavailable):
        testcmd.python_command(root, [])


def test_cli_prints_default_command(root, capsys, monkeypatch):
    monkeypatch.setattr(pyrun, "have_pytest", lambda: True)
    rc, out, _ = cli(root, capsys)
    assert rc == 0
    assert out["command"] == shlex.join(testcmd.python_command(root, []))
    assert out["default_command"] is True and out["origin"] == "detection"


def test_cli_fast_paths_in_default_command(root, capsys, monkeypatch):
    monkeypatch.setattr(pyrun, "have_pytest", lambda: True)
    _, out, _ = cli(root, capsys, "--fast", "tests/test_x.py")
    assert "tests/test_x.py" in out["command"] and " tests -q" not in out["command"]


def test_cli_no_runner_keeps_null(root, capsys, monkeypatch):
    monkeypatch.setattr(pyrun, "have_pytest", lambda: False)
    monkeypatch.setattr(pyrun.shutil, "which", lambda name: None)
    rc, out, err = cli(root, capsys)
    assert rc == 0 and out["command"] is None and "default_command" not in out
    assert err.startswith("testcmd: pytest is not installed")


def test_cli_configured_command_unchanged(root, capsys, monkeypatch):
    monkeypatch.setattr(pyrun, "have_pytest", lambda: True)
    (root / ".superlite").mkdir()
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "python", "test": "make check"}), encoding="utf-8")
    _, out, _ = cli(root, capsys)
    assert out["command"] == "make check" and "default_command" not in out


def test_resolve_keeps_null_command(root):
    assert testcmd.resolve(root)["command"] is None
