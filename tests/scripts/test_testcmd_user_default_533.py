"""#533: a user-level default test command, read when the project has no .superlite/test-cmd.json."""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

MIXED = "final class AlphaTests: XCTestCase {\n  func testA() {}\n}\nclass BetaTests: XCTestCase {\n  func testB() {}\n}\n"
PLACER = {"test": "placer test", "test_file": "placer test {only_testing}"}


def user(tmp_path, monkeypatch, data):
    p = tmp_path / "home-config" / "test-cmd.json"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(data if isinstance(data, str) else json.dumps(data), encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(p))
    return p


def xcode(tmp_path):
    root = tmp_path / "app"
    (root / "App.xcodeproj").mkdir(parents=True)
    (root / "Tests" / "KitTests").mkdir(parents=True)
    (root / "Tests" / "KitTests" / "Mixed.swift").write_text(MIXED, encoding="utf-8")
    return root


def test_conftest_isolates_the_user_file(tmp_path):
    p = Path(os.environ["SUPERLITE_USER_TEST_CMD"])
    assert not p.exists() and ".config" not in p.parts


def test_user_path_default_and_override(monkeypatch, tmp_path):
    monkeypatch.delenv("SUPERLITE_USER_TEST_CMD")
    assert testcmd.user_config_path() == Path.home() / ".config" / "superlite" / "test-cmd.json"
    assert testcmd.shown(testcmd.user_config_path()) == "~/.config/superlite/test-cmd.json"
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(tmp_path / "u.json"))
    assert testcmd.user_config_path() == tmp_path / "u.json"


def test_swift_user_default_full_and_fast(tmp_path, monkeypatch):
    p = user(tmp_path, monkeypatch, {"swift": PLACER})
    root = xcode(tmp_path)
    full = testcmd.resolve(root, [])
    assert (full["command"], full["source"], full["origin"], full["language"]) == ("placer test", "user", testcmd.shown(p), "swift")
    assert full["isolate"] is True and full["python"] is False
    fast = testcmd.resolve(root, ["Tests/KitTests/Mixed.swift"])
    assert fast["command"] == "placer test -only-testing:KitTests/AlphaTests -only-testing:KitTests/BetaTests"


def test_entry_isolate_false_is_kept(tmp_path, monkeypatch):
    user(tmp_path, monkeypatch, {"swift": {**PLACER, "isolate": False}})
    assert testcmd.resolve(xcode(tmp_path), [])["isolate"] is False


def test_project_file_wins(tmp_path, monkeypatch):
    user(tmp_path, monkeypatch, {"swift": PLACER})
    root = xcode(tmp_path)
    (root / ".superlite").mkdir()
    (root / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": "xcodebuild test -scheme X"}), encoding="utf-8")
    r = testcmd.resolve(root, [])
    assert (r["command"], r["source"], r["origin"]) == ("xcodebuild test -scheme X", "test-cmd.json", ".superlite/test-cmd.json")


def _git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), "-c", "user.email=t@t", "-c", "user.name=t", *args], check=True, capture_output=True)


def test_main_checkout_file_wins_over_user(tmp_path, monkeypatch):
    user(tmp_path, monkeypatch, {"go": {"test": "placer go"}})
    main = tmp_path / "main"
    main.mkdir()
    _git(main, "init", "-q")
    (main / "go.mod").write_text("module m\n", encoding="utf-8")
    _git(main, "add", "go.mod")
    _git(main, "commit", "-qm", "init")
    wt = tmp_path / "wt"
    _git(main, "worktree", "add", "-q", str(wt), "-b", "side")
    (main / ".superlite").mkdir()
    (main / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "go", "test": "echo main"}), encoding="utf-8")
    r = testcmd.resolve(wt, [])
    assert (r["command"], r["source"]) == ("echo main", "test-cmd.json")
    assert Path(r["origin"]) == (main / ".superlite" / "test-cmd.json").resolve()


def test_no_user_file_changes_nothing(tmp_path):
    (tmp_path / "Package.swift").write_text("// swift-tools-version:5.9\n", encoding="utf-8")
    r = testcmd.resolve(tmp_path, [])
    assert (r["command"], r["source"], r["origin"]) == ("swift test --xunit-output {junit}", "markers", "detection")


def test_other_language_key_falls_through(tmp_path, monkeypatch):
    user(tmp_path, monkeypatch, {"python": {"test": "remote pytest"}})
    (tmp_path / "go.mod").write_text("module m\n", encoding="utf-8")
    assert testcmd.resolve(tmp_path, [])["command"] == "go test ./..."


def test_python_entry_replaces_the_pytest_path(tmp_path, monkeypatch):
    user(tmp_path, monkeypatch, {"python": {"test": "remote pytest", "test_file": "pytest {files}"}})
    (tmp_path / "pyproject.toml").write_text("[project]\n", encoding="utf-8")
    r = testcmd.resolve(tmp_path, ["tests/test_a.py"])
    assert (r["python"], r["command"], r["source"], r["language"]) == (False, "pytest tests/test_a.py", "user", "python")


def test_bad_json_is_ignored_with_a_line(tmp_path, monkeypatch, capsys):
    p = user(tmp_path, monkeypatch, "{not json")
    (tmp_path / "go.mod").write_text("module m\n", encoding="utf-8")
    assert testcmd.resolve(tmp_path, [])["source"] == "markers"
    assert f"user test-cmd.json ignored ({testcmd.shown(p)}):" in capsys.readouterr().err


def test_top_level_list_is_ignored(tmp_path, monkeypatch, capsys):
    user(tmp_path, monkeypatch, [1, 2])
    (tmp_path / "go.mod").write_text("module m\n", encoding="utf-8")
    assert testcmd.resolve(tmp_path, [])["source"] == "markers"
    assert "needs a JSON object keyed by language" in capsys.readouterr().err


def test_entry_without_test_is_ignored(tmp_path, monkeypatch, capsys):
    user(tmp_path, monkeypatch, {"go": {"test_file": "x {files}"}})
    (tmp_path / "go.mod").write_text("module m\n", encoding="utf-8")
    assert testcmd.resolve(tmp_path, [])["source"] == "markers"
    assert 'user test-cmd.json ignored for go (' in capsys.readouterr().err


def test_read_user_config_sets_language(tmp_path, monkeypatch):
    user(tmp_path, monkeypatch, {"rust": {"test": "placer cargo", "language": "other"}})
    assert testcmd.read_user_config("rust") == {"test": "placer cargo", "language": "rust"}
    assert testcmd.read_user_config("go") is None


def test_missing_reason_names_the_user_file(tmp_path):
    root = tmp_path / "app"
    (root / "App.xcodeproj").mkdir(parents=True)
    r = testcmd.missing_reason(root)
    assert "{only_testing}" in r and f'or a "swift" entry in {testcmd.shown(testcmd.user_config_path())}' in r


def test_cli_prints_origin(tmp_path, monkeypatch):
    p = user(tmp_path, monkeypatch, {"swift": PLACER})
    cp = run(SCRIPTS / "testcmd.py", "--root", xcode(tmp_path))
    out = json.loads(cp.out)
    assert (out["origin"], out["source"], out["command"]) == (testcmd.shown(p), "user", "placer test")
