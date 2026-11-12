"""#627, #639: a full run covered by a green `maxapp test` stamp returns that result without a run; maxapp toolchain and no derived-data warning."""
from __future__ import annotations

import json
import os
import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
PY = sys.executable
ENV_DROP = ("SUPERLITE_STATE_DIR", "SUPERLITE_FLEET_ROLE", "SUPERLITE_FLEET_PARENT_DIR")


def env(tmp_path):
    bin_dir = tmp_path / "bin"
    return {**{k: v for k, v in os.environ.items() if k not in ENV_DROP},
            "PATH": f"{bin_dir}{os.pathsep}{os.environ['PATH']}", "SUPERLITE_HOME": str(tmp_path / "home"),
            "GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t"}


def git(repo, *a):
    return subprocess.run(["git", "-C", str(repo), *a], capture_output=True, text=True, check=True).stdout.strip()


def project(tmp_path, not_code=()):
    proj = tmp_path / "proj"
    (proj / "src").mkdir(parents=True)
    (proj / "docs").mkdir()
    (proj / "src" / "a.swift").write_text("x\n")
    (proj / "docs" / "x.md").write_text("a\n")
    (proj / ".superlite").mkdir()
    (proj / ".superlite" / "test-cmd.json").write_text(json.dumps(
        {"language": "swift", "test": "maxapp test", "not_code": list(not_code)}))
    (proj / ".gitignore").write_text(".superlite/\n")
    git(proj, "init", "-q")
    git(proj, "add", "-A")
    git(proj, "commit", "-qm", "base")
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    fake = bin_dir / "maxapp"
    fake.write_text(f"#!/bin/sh\necho ran >> '{tmp_path}/marker'\necho 'Executed 3 tests, with 0 failures'\n")
    fake.chmod(0o755)
    return proj


def stamp(proj, rev="HEAD", tests="12"):
    tree = git(proj, "rev-parse", rev + "^{tree}")
    d = proj / ".git" / "maxapp" / "test"
    d.mkdir(parents=True, exist_ok=True)
    (d / f"{tree}.macOS").write_text(f"tree={tree}\nplatform=macOS\ncommit={git(proj, 'rev-parse', rev)}\ntests={tests}\n")
    return tree


def rt(tmp_path, proj, *args):
    return subprocess.run([PY, str(RUN_TESTS), *args], cwd=proj, env=env(tmp_path), capture_output=True, text=True)


def summary(proj):
    return json.loads((proj / ".superlite" / "test-summary.json").read_text())


def test_stamp_hit_runs_no_command(tmp_path):
    proj = project(tmp_path)
    tree = stamp(proj)
    cp = rt(tmp_path, proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert not (tmp_path / "marker").exists()
    s = summary(proj)
    assert s["passed"] == 12 and s["failed"] == 0 and s["mode"] == "full"
    assert s["stamp"]["tree"] == tree and s["stamp"]["platforms"] == ["macOS"] and s["stamp"]["changed"] == []
    assert f"full suite green by the maxapp test stamp for {git(proj, 'rev-parse', 'HEAD')[:12]} (tree {tree[:12]}, 12 tests on macOS); no run" in cp.stderr


def test_no_stamp_runs(tmp_path):
    proj = project(tmp_path)
    cp = rt(tmp_path, proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert (tmp_path / "marker").read_text().count("ran") == 1
    assert "stamp" not in summary(proj)


def test_fast_and_task_never_read_stamp(tmp_path):
    proj = project(tmp_path)
    stamp(proj)
    (proj / "tests").mkdir()
    (proj / "tests" / "ATests.swift").write_text("import XCTest\nfinal class ATests: XCTestCase {}\n")
    rt(tmp_path, proj, "--fast", "tests/ATests.swift")
    assert (tmp_path / "marker").exists()
    (tmp_path / "marker").unlink()
    plan = tmp_path / "plan.md"
    plan.write_text("### T1 x\n**Owns:** src/a.swift\n**Tests:** fast\n")
    rt(tmp_path, proj, "--task", "T1", "--full", "--plan", str(plan))
    assert (tmp_path / "marker").exists()


def test_docs_only_hit_names_changes(tmp_path):
    proj = project(tmp_path, not_code=["docs/**"])
    stamp(proj)
    (proj / "docs" / "x.md").write_text("b\n")
    git(proj, "commit", "-qam", "docs")
    cp = rt(tmp_path, proj, "--full")
    assert cp.returncode == 0, cp.stdout + cp.stderr
    assert not (tmp_path / "marker").exists()
    assert "docs/x.md" in cp.stderr and summary(proj)["stamp"]["changed"] == ["docs/x.md"]


def test_maxapp_lock_toolchain():
    assert run_tests.lock_toolchain({"command": "maxapp test", "language": "swift"}) == "xcode"
    assert run_tests.lock_toolchain({"command": "maxapp build --ios", "language": "swift"}) == "xcode"
    assert run_tests.lock_toolchain({"command": "maxapp smoke", "language": "swift"}) == "xcode"
    assert run_tests.lock_toolchain({"command": "make test", "language": "swift"}) == "swift"


def test_maxapp_no_derived_data_warning(tmp_path):
    (tmp_path / "A.xcodeproj").mkdir()
    assert run_tests.wrapped_build_warning("maxapp test", tmp_path, tmp_path, "swift") is None
    assert run_tests.wrapped_build_warning("make test", tmp_path, tmp_path, "swift") is not None


def test_stamp_hit_unit(tmp_path):
    proj = project(tmp_path)
    assert run_tests.stamp_hit(None, {"command": "maxapp test", "python": False, "not_code": []}, "fast") is None
