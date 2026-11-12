"""#598: run_tests runs one xcodebuild per destination, merges the results and warns about platforms a full run skipped."""
from __future__ import annotations

import json
import os
import stat
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import run_tests  # noqa: E402

RUN_TESTS = Path(run_tests.__file__)
MAC = "platform=macOS"
IOS = "platform=iOS Simulator,name=iPhone 16"
FAKE = """#!/bin/sh
dest=""
while [ $# -gt 0 ]; do
  if [ "$1" = "-destination" ]; then dest="$2"; fi
  shift
done
echo "$dest" >> "$FAKE_LOG"
case "$dest" in
  *macOS*) [ -n "$FAKE_MAC_RED" ] && { echo "Executed 1 test, with 1 failure (1 unexpected) in 0.1 (0.1) seconds"; exit 65; } ;;
esac
echo "Executed 2 tests, with 0 failures (0 unexpected) in 0.1 (0.1) seconds"
exit 0
"""


def project(tmp_path, destinations=None, command="xcodebuild test -scheme A", package=None):
    (tmp_path / ".superlite").mkdir()
    (tmp_path / "bin").mkdir()
    fake = tmp_path / "bin" / "xcodebuild"
    fake.write_text(FAKE, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR)
    cfg = {"language": "swift", "test": command}
    if destinations is not None:
        cfg["destinations"] = destinations
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    if package:
        (tmp_path / "Package.swift").write_text(package, encoding="utf-8")
    subprocess.run(["git", "init", "-q"], cwd=tmp_path, check=True)
    return tmp_path


def child_env(tmp_path):
    env = {k: v for k, v in os.environ.items() if (not k.startswith("SUPERLITE_") or k == "SUPERLITE_USER_TEST_CMD") and k not in ("FAKE_MAC_RED",)}
    env.update(SUPERLITE_HOME=str(tmp_path / "home"), SUPERLITE_DISK_FLOOR_GB="0", SUPERLITE_DISK_WARN_GB="0",
               SUPERLITE_MACHINE_LIMIT="0", PYTHONIOENCODING="utf-8", FAKE_LOG=str(tmp_path / "fake.log"),
               PATH=str(tmp_path / "bin") + os.pathsep + os.environ["PATH"])
    return env


def run(tmp_path, *args, red=False):
    env = child_env(tmp_path)
    if red:
        env["FAKE_MAC_RED"] = "1"
    sl = tmp_path / ".superlite"
    cp = subprocess.run([sys.executable, str(RUN_TESTS), "--log", str(sl / "incidents.jsonl"),
                         "--ledger", str(sl / "ledger.md"), "--summary", str(sl / "test-summary.json"), *map(str, args)],
                        capture_output=True, cwd=tmp_path, env=env, timeout=120, text=True)
    cp.both = cp.stdout + cp.stderr
    return cp


def ran(tmp_path):
    log = tmp_path / "fake.log"
    return log.read_text(encoding="utf-8").splitlines() if log.exists() else []


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def test_red_destination_named(tmp_path):
    project(tmp_path, [MAC, IOS])
    cp = run(tmp_path, "--full", red=True)
    assert cp.returncode == 1, cp.both
    assert "destination platform=macOS: exit 65" in " ".join(summary(tmp_path)["failures"])
    assert ran(tmp_path) == [MAC, IOS]


def test_platform_warning_full_run(tmp_path):
    pkg = 'let package = Package(name: "P", platforms: [.iOS(.v17), .macOS(.v14)], targets: [])\n'
    project(tmp_path, None, "xcodebuild test -scheme A -destination 'platform=iOS Simulator,name=iPhone 16'", package=pkg)
    cp = run(tmp_path, "--full")
    assert "WARNING: Package.swift declares iOS, macOS" in cp.stderr, cp.both
    assert "macOS" in summary(tmp_path)["warning"]
    started = run(tmp_path, "--full", "--background")
    path = next(ln.split(" ", 1)[1] for ln in started.stdout.splitlines() if ln.startswith("summary: "))
    waited = run(tmp_path, "--wait", path)
    assert waited.stderr.index("warning: ") < waited.stderr.index("tests (full)"), waited.both


def test_full_runs_every_destination(tmp_path):
    project(tmp_path, [MAC, IOS])
    cp = run(tmp_path, "--full")
    assert cp.returncode == 0, cp.both
    assert ran(tmp_path) == [MAC, IOS]
    assert "run_tests: destination platform=macOS" in (Path(summary(tmp_path)["output"]).read_text(encoding="utf-8"))


def test_fast_runs_first_destination(tmp_path):
    project(tmp_path, [MAC, IOS])
    (tmp_path / "FooTests.swift").write_text("import XCTest\n", encoding="utf-8")
    cp = run(tmp_path, "--fast", "FooTests.swift")
    assert ran(tmp_path) == [MAC], cp.both


def test_destination_flag_overrides(tmp_path):
    project(tmp_path, [MAC, IOS])
    run(tmp_path, "--full", "--destination", IOS)
    assert ran(tmp_path) == [IOS]


def test_destination_all(tmp_path):
    project(tmp_path, [MAC, IOS])
    (tmp_path / "FooTests.swift").write_text("import XCTest\n", encoding="utf-8")
    run(tmp_path, "--fast", "FooTests.swift", "--destination", "all")
    assert ran(tmp_path) == [MAC, IOS]


def test_counts_summed(tmp_path):
    project(tmp_path, [MAC, IOS])
    run(tmp_path, "--full")
    assert summary(tmp_path)["passed"] == 4


def test_non_xcodebuild_warns_runs_once(tmp_path):
    project(tmp_path, [MAC, IOS], command="echo 'Executed 2 tests, with 0 failures (0 unexpected)' >> $FAKE_LOG")
    cp = run(tmp_path, "--full")
    assert "destinations need an xcodebuild command; ran `" in cp.stderr, cp.both
    assert len(ran(tmp_path)) == 1


def test_no_warning_when_covered(tmp_path):
    pkg = 'let package = Package(name: "P", platforms: [.iOS(.v17), .macOS(.v14)], targets: [])\n'
    project(tmp_path, [MAC, IOS], package=pkg)
    cp = run(tmp_path, "--full")
    assert "WARNING" not in cp.stderr, cp.both
    assert "warning" not in summary(tmp_path)


def test_child_env_ignores_outer_disk_floor(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "100000")
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", "x")
    env = child_env(tmp_path)
    assert (env["SUPERLITE_DISK_FLOOR_GB"], env["SUPERLITE_DISK_WARN_GB"], env["SUPERLITE_MACHINE_LIMIT"]) == ("0", "0", "0")
    assert env["SUPERLITE_HOME"] == str(tmp_path / "home") and env["SUPERLITE_USER_TEST_CMD"] == "x"
