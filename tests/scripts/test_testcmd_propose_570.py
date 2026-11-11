"""#570: testcmd proposes the project's own test command and writes .superlite/test-cmd.json."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS, run

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402

TESTCMD = SCRIPTS / "testcmd.py"
XCODE_SCRIPT = ("#!/usr/bin/env bash\nset -euo pipefail\ncd \"$(dirname \"$0\")/../Packages/AppKit\" && "
                "exec xcodebuild test -scheme AppKit-Package -destination 'platform=macOS' \"$@\"\n")
SWIFT_CFG = {"language": "swift", "test": "Scripts/test.sh", "test_file": "Scripts/test.sh {only_testing}"}


@pytest.fixture(autouse=True)
def no_user_file(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(tmp_path / "no-user-file.json"))


def script(root, rel, body=XCODE_SCRIPT, executable=True):
    p = root / rel
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(body, encoding="utf-8")
    p.chmod(0o755 if executable else 0o644)
    return p


def swift_app(tmp_path):
    root = tmp_path / "app"
    (root / "App.xcodeproj").mkdir(parents=True)
    (root / "Packages" / "AppKit").mkdir(parents=True)
    (root / "Packages" / "AppKit" / "Package.swift").write_text("// swift-tools-version:5.9\n", encoding="utf-8")
    script(root, "Scripts/test.sh")
    return root


def saved(root):
    return json.loads((root / ".superlite" / "test-cmd.json").read_text(encoding="utf-8"))


def git(cwd, *args):
    subprocess.run(["git", "-C", str(cwd), *args], check=True, capture_output=True)


def test_propose_project_test_script_swift(tmp_path):
    assert testcmd.propose(swift_app(tmp_path)) == {"config": SWIFT_CFG, "from": "project test script Scripts/test.sh"}


def test_propose_nested_package_without_xcodeproj_is_swift(tmp_path):
    root = tmp_path / "pkg"
    (root / "Packages" / "Core").mkdir(parents=True)
    (root / "Packages" / "Core" / "Package.swift").write_text("// swift-tools-version:5.9\n", encoding="utf-8")
    script(root, "scripts/test", body="#!/bin/sh\nswift test --package-path Packages/Core\n")
    assert testcmd.propose(root) == {"config": {"language": "swift", "test": "scripts/test"}, "from": "project test script scripts/test"}


def test_propose_script_preference_and_non_executable(tmp_path):
    root = tmp_path / "r"
    script(root, "bin/test", body="#!/bin/sh\nexit 0\n")
    script(root, "script/run-tests.sh", body="echo hi\n", executable=False)
    assert testcmd.propose(root) == {"config": {"test": "bin/test"}, "from": "project test script bin/test"}
    (root / "bin" / "test").unlink()
    assert testcmd.propose(root) == {"config": {"test": "bash script/run-tests.sh"}, "from": "project test script script/run-tests.sh"}


def test_propose_makefile_target(tmp_path):
    root = tmp_path / "m"
    root.mkdir()
    (root / "Makefile").write_text("CC := cc\ntest:\n\t./run\n", encoding="utf-8")
    assert testcmd.propose(root) == {"config": {"test": "make test"}, "from": "Makefile target test"}
    (root / "Makefile").write_text("test := 1\ntests: all\n", encoding="utf-8")
    assert testcmd.propose(root) is None


def test_propose_order_script_then_makefile_then_detection(tmp_path):
    root = tmp_path / "g"
    root.mkdir()
    (root / "go.mod").write_text("module m\n", encoding="utf-8")
    assert testcmd.propose(root) == {"config": {"language": "go", "test": "go test ./...", "test_file": "go test {files}"}, "from": "detection"}
    (root / "Makefile").write_text("test:\n\tgo test ./...\n", encoding="utf-8")
    assert testcmd.propose(root) == {"config": {"language": "go", "test": "make test"}, "from": "Makefile target test"}
    script(root, "scripts/test.sh", body="#!/bin/sh\ngo test ./...\n")
    assert testcmd.propose(root) == {"config": {"language": "go", "test": "scripts/test.sh"}, "from": "project test script scripts/test.sh"}


def test_propose_python_project_and_empty_folder(tmp_path):
    py = tmp_path / "py"
    py.mkdir()
    (py / "pyproject.toml").write_text("[project]\nname='x'\n", encoding="utf-8")
    assert testcmd.propose(py) is None
    (tmp_path / "empty").mkdir()
    assert testcmd.propose(tmp_path / "empty") is None


def test_propose_none_when_project_file_exists(tmp_path):
    root = swift_app(tmp_path)
    (root / ".superlite").mkdir()
    (root / ".superlite" / "test-cmd.json").write_text('{"test": "x"}', encoding="utf-8")
    assert testcmd.propose(root) is None


def test_write_creates_file_and_refuses_second(tmp_path):
    root = swift_app(tmp_path)
    target = (root / ".superlite" / "test-cmd.json").resolve()
    cp = run(TESTCMD, "--root", root, "--write")
    assert cp.returncode == 0, cp.both
    assert cp.out.strip() == f"wrote {target.as_posix()}: Scripts/test.sh"
    assert saved(root) == SWIFT_CFG
    assert testcmd.resolve(root)["command"] == "Scripts/test.sh"
    again = run(TESTCMD, "--root", root, "--write")
    assert again.returncode == 2 and "nothing written" in again.err
    with pytest.raises(FileExistsError):
        testcmd.write_config(root, {"test": "y"})


def test_write_overrides_and_nothing_to_write(tmp_path):
    root = tmp_path / "e"
    root.mkdir()
    cp = run(TESTCMD, "--root", root, "--write")
    assert cp.returncode == 1 and "nothing to write" in cp.err
    assert not (root / ".superlite" / "test-cmd.json").exists()
    cp = run(TESTCMD, "--root", root, "--write", "--test", "make check", "--language", "rust")
    assert cp.returncode == 0, cp.both
    assert saved(root) == {"language": "rust", "test": "make check"}


def test_write_test_override_drops_proposed_test_file(tmp_path):
    root = swift_app(tmp_path)
    cp = run(TESTCMD, "--root", root, "--write", "--test", "lockf /tmp/x Scripts/test.sh")
    assert cp.returncode == 0, cp.both
    assert saved(root) == {"language": "swift", "test": "lockf /tmp/x Scripts/test.sh"}


def test_write_in_linked_worktree_targets_main_checkout(tmp_path):
    main = swift_app(tmp_path)
    git(main, "init", "-q", "-b", "main")
    git(main, "add", ".")
    git(main, "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-q", "-m", "init")
    wt = tmp_path / "wt"
    git(main, "worktree", "add", "-q", "-b", "topic", str(wt))
    target = (main / ".superlite" / "test-cmd.json").resolve()
    assert testcmd.config_target(wt) == target
    cp = run(TESTCMD, "--root", wt, "--propose")
    assert cp.returncode == 0, cp.both
    assert json.loads(cp.out) == {"proposal": SWIFT_CFG, "from": "project test script Scripts/test.sh",
                                  "target": target.as_posix(), "exists": False}
    assert run(TESTCMD, "--root", wt, "--write").returncode == 0
    assert target.is_file() and not (wt / ".superlite" / "test-cmd.json").exists()
    assert testcmd.resolve(wt)["command"] == "Scripts/test.sh"


def test_missing_reason_names_setup_and_proposal(tmp_path):
    root = swift_app(tmp_path)
    r = testcmd.missing_reason(root)
    assert r.startswith("no test command found: add .superlite/test-cmd.json") and "{only_testing}" in r
    assert r.endswith("; /superlite:setup proposes `Scripts/test.sh` (project test script Scripts/test.sh) and writes it to .superlite/test-cmd.json")
    (tmp_path / "e").mkdir()
    assert testcmd.missing_reason(tmp_path / "e").endswith("; /superlite:setup writes .superlite/test-cmd.json from the command you name")
