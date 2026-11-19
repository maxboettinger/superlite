"""#950: sl testcmd prints test-cmd.json "cwd" (as written, "" when unset); the testcmd.py docstring names it."""
from __future__ import annotations

from test_testcmd import TESTCMD, config, resolved


def test_cli_prints_cwd(tmp_path):
    config(tmp_path, language="go", test="go test ./...", cwd="app")
    assert resolved(tmp_path)["cwd"] == "app"


def test_cli_cwd_empty_when_unset(tmp_path):
    config(tmp_path, language="go", test="go test ./...")
    assert resolved(tmp_path)["cwd"] == ""


def test_python_default_prints_cwd(tmp_path):
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    out = resolved(tmp_path)
    assert out["python"] is True and out["cwd"] == ""


def test_docstring_names_cwd():
    head = TESTCMD.read_text(encoding="utf-8").split('"""', 2)[1]
    assert "`cwd` in (a) is the folder" in head and 'spec["cwd"]' in head
