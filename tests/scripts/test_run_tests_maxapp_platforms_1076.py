"""#1076: the full-run platform warning reads the platforms a `maxapp test` command builds."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
PKG = 'let package = Package(name: "P", platforms: [.iOS(.v17), .macOS(.v14)], targets: [])\n'
ENV_DROP = ("SUPERLITE_STATE_DIR", "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR")


def project(tmp_path, command, maxapp=None):
    proj = tmp_path / "proj"
    (proj / ".superlite").mkdir(parents=True)
    (proj / ".superlite" / "test-cmd.json").write_text(json.dumps({"language": "swift", "test": command}), encoding="utf-8")
    (proj / "Package.swift").write_text(PKG, encoding="utf-8")
    if maxapp is not None:
        (proj / ".maxapp").write_text(maxapp, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=proj, check=True)
    (tmp_path / "bin").mkdir()
    fake = tmp_path / "bin" / "maxapp"
    fake.write_text("#!/bin/sh\necho 'Executed 3 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds'\n", encoding="utf-8")
    fake.chmod(0o755)
    return proj


def rt(tmp_path, proj):
    env = {**{k: v for k, v in os.environ.items() if k not in ENV_DROP},
           "PATH": f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}", "SUPERLITE_HOME": str(tmp_path / "home"),
           "SUPERLITE_DISK_FLOOR_GB": "0", "SUPERLITE_DISK_WARN_GB": "0"}
    cp = subprocess.run([sys.executable, str(RUN_TESTS), "--full"], cwd=proj, env=env, capture_output=True, text=True, timeout=120)
    cp.both = cp.stdout + cp.stderr
    return cp


def summary(proj):
    return json.loads((proj / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_maxapp_ios_builds_both(tmp_path):
    proj = project(tmp_path, "maxapp test --ios")
    cp = rt(tmp_path, proj)
    assert cp.returncode == 0, cp.both
    assert "Package.swift declares" not in cp.stderr and "warning" not in summary(proj)


def test_plain_maxapp_follows_test_full(tmp_path):
    proj = project(tmp_path, "maxapp test", maxapp="test_full=macOS iOS\n")
    cp = rt(tmp_path, proj)
    assert cp.returncode == 0, cp.both
    assert "Package.swift declares" not in cp.stderr and "warning" not in summary(proj)


def test_plain_maxapp_without_ios_warns_ios(tmp_path):
    proj = project(tmp_path, "maxapp test")
    cp = rt(tmp_path, proj)
    assert "WARNING: Package.swift declares iOS, macOS; this full run built for macOS only" in cp.stderr, cp.both
    assert "built for macOS only" in summary(proj)["warning"]


def test_malformed_test_full_counts_macos(tmp_path):
    proj = project(tmp_path, "maxapp test", maxapp="test_full=iOS\n")
    cp = rt(tmp_path, proj)
    assert "this full run built for macOS only" in cp.stderr, cp.both


def test_built_platforms_unit(tmp_path):
    assert run_tests.built_platforms(tmp_path, "maxapp test --ios", []) == ["macOS", "iOS"]
    assert run_tests.built_platforms(tmp_path, "maxapp test", []) == ["macOS"]
    assert run_tests.built_platforms(tmp_path, "maxapp test --only A/B", []) == []
    assert run_tests.built_platforms(tmp_path, "swift test", []) == ["macOS"]
    assert run_tests.built_platforms(tmp_path, "xcodebuild test -scheme A", ["platform=iOS Simulator,name=iPhone 16", "platform=macOS"]) == ["iOS", "macOS"]


def test_docs_name_both_rules():
    tools = (SCRIPTS.parents[2] / "docs" / "tools.md").read_text(encoding="utf-8")
    assert "every summary block counts: a run that prints several" in tools
    assert "without destinations `maxapp test --ios` counts as built for macOS and iOS" in tools
