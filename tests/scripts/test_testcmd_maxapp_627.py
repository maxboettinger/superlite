"""#627: a `.maxapp` project resolves to `maxapp test`; the `not_code` setting."""
from __future__ import annotations

import json
import os
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

SUITE = "final class FooTests: XCTestCase {\n  func testA() {}\n}\n"


def fake_maxapp(tmp_path, monkeypatch):
    bindir = tmp_path / "bin"
    bindir.mkdir(exist_ok=True)
    exe = bindir / "maxapp"
    exe.write_text("#!/bin/sh\nexit 0\n", encoding="utf-8")
    exe.chmod(0o755)
    monkeypatch.setenv("PATH", str(bindir) + os.pathsep + os.environ.get("PATH", ""))


def project(tmp_path, maxapp="# c\n\npackage=App\npackage_scheme=App\n"):
    root = tmp_path / "app"
    (root / "Tests" / "CoreTests").mkdir(parents=True)
    (root / "Tests" / "CoreTests" / "FooTests.swift").write_text(SUITE, encoding="utf-8")
    (root / "Package.swift").write_text("// swift\n", encoding="utf-8")
    if maxapp is not None:
        (root / ".maxapp").write_text(maxapp, encoding="utf-8")
    return root


def test_maxapp_detect_needs_keys_and_path(tmp_path, monkeypatch):
    root = project(tmp_path, maxapp="package=App\n")
    fake_maxapp(tmp_path, monkeypatch)
    assert testcmd.resolve(root)["command"].startswith("swift test")
    root = project(tmp_path / "b")
    monkeypatch.setenv("PATH", str(tmp_path / "empty"))
    assert testcmd.resolve(root)["command"].startswith("swift test")
    fake_maxapp(tmp_path, monkeypatch)
    spec = testcmd.resolve(root)
    assert spec["command"] == "maxapp test" and spec["language"] == "swift" and spec["not_code"] == []
    assert spec["origin"] == ".maxapp"


def test_maxapp_only_testing_expands_to_only(tmp_path, monkeypatch):
    fake_maxapp(tmp_path, monkeypatch)
    root = project(tmp_path)
    spec = testcmd.resolve(root, ["Tests/CoreTests/FooTests.swift"])
    assert spec["command"] == "maxapp test --only CoreTests/FooTests"


def test_maxapp_beats_user_entry(tmp_path, monkeypatch):
    fake_maxapp(tmp_path, monkeypatch)
    user = tmp_path / "u.json"
    user.write_text(json.dumps({"swift": {"test": "placer test"}}), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(user))
    spec = testcmd.resolve(project(tmp_path))
    assert spec["command"] == "maxapp test" and spec["origin"] == ".maxapp"


def test_project_file_still_wins(tmp_path, monkeypatch):
    fake_maxapp(tmp_path, monkeypatch)
    root = project(tmp_path)
    (root / ".superlite").mkdir()
    (root / ".superlite" / "test-cmd.json").write_text(
        json.dumps({"language": "swift", "test": "make check", "not_code": ["docs/**"]}), encoding="utf-8")
    spec = testcmd.resolve(root)
    assert spec["command"] == "make check" and spec["not_code"] == ["docs/**"]


def test_not_code_globs():
    assert testcmd.not_code_globs({"not_code": ["docs/**", "**/*.md"]}) == ["docs/**", "**/*.md"]
    assert testcmd.not_code_globs(None) == []
    assert testcmd.not_code_globs({}) == []


def test_not_code_bad_value_ignored_with_note(capsys):
    assert testcmd.not_code_globs({"not_code": "docs"}) == []
    assert 'test-cmd.json "not_code" must be a list of glob strings; ignored' in capsys.readouterr().err
