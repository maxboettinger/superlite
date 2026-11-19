"""worktree scratch: build the run's start SHA in a scratch tree that is removed afterwards (#816)."""
from __future__ import annotations

import json
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
WORKTREE = SCRIPTS / "worktree.py"
sys.path.insert(0, str(SCRIPTS))

import trees  # noqa: E402
import worktree  # noqa: E402

USAGE = "usage: worktree scratch [--rev REV] [--repo DIR] -- COMMAND...\n"


def clean_env():
    env = dict(os.environ)
    for k in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE"):
        env.pop(k, None)
    return env


def git(cwd, *args):
    return subprocess.run(["git", "-C", str(cwd), *args], capture_output=True, text=True, check=True, env=clean_env()).stdout.strip()


def commit(repo, text, msg):
    (repo / "v").write_text(text)
    git(repo, "add", "v")
    git(repo, "commit", "-q", "-m", msg)
    return git(repo, "rev-parse", "HEAD")


@pytest.fixture
def repo(tmp_path):
    r = tmp_path.resolve() / "repo"
    r.mkdir()
    git(r, "init", "-q", "-b", "main")
    git(r, "config", "user.name", "t")
    git(r, "config", "user.email", "t@t")
    r.joinpath("v").write_text("1")
    a = commit(r, "1\n", "A")
    (r / ".superlite").mkdir()
    (r / ".superlite" / "checkpoints.json").write_text(json.dumps({"base": a}))
    with (r / ".git" / "info" / "exclude").open("a") as f:
        f.write(".superlite/\n")
    commit(r, "2\n", "B")
    return r


def A(repo):
    return git(repo, "rev-parse", "HEAD~1")


def run(cwd, *args, **kw):
    return subprocess.run([sys.executable, str(WORKTREE), *args], cwd=str(cwd), capture_output=True, text=True, env=clean_env(), **kw)


def scratch_dirs(repo):
    d = repo / ".superlite" / "trees"
    return sorted(p.name for p in d.glob("scratch-*") if p.is_dir()) if d.exists() else []


def test_scratch_command_examples():
    sc = worktree.scratch_command
    assert sc("xcodebuild -scheme App build", "/w/.superlite/trees/scratch-7", "/w/.build/SourcePackages") == (
        "xcodebuild -derivedDataPath /w/.superlite/trees/scratch-7/.build/DerivedData -clonedSourcePackagesDirPath /w/.build/SourcePackages -scheme App build")
    assert sc("make build", "/w/t", "/w/p") == "make build"
    out = sc("xcodebuild -scheme App -clonedSourcePackagesDirPath X build", "/w/t", "/w/p")
    assert "-clonedSourcePackagesDirPath X" in out and out.count("-clonedSourcePackagesDirPath") == 1 and "-derivedDataPath /w/t/.build/DerivedData" in out
    assert sc("xcodebuild -version", "/w/t", "/w/p") == "xcodebuild -version"
    out = sc("xcodebuild -xctestrun r.xctestrun test-without-building", "/w/t", "/w/p")
    assert "-clonedSourcePackagesDirPath" not in out and "-derivedDataPath" in out
    out = sc("xcodebuild -scheme A build && xcodebuild -scheme B build", "/w/t", "/w/p")
    assert out.count("-clonedSourcePackagesDirPath /w/p") == 2 and out.count("-derivedDataPath") == 2
    assert "'/w x/.build/SourcePackages'" in sc("xcodebuild -scheme A build", "/w/t", "/w x/.build/SourcePackages")


def test_scratch_runs_at_start_sha(repo):
    a = A(repo)
    cmd = 'cat v > "$SUPERLITE_RUN_ROOT/seen"; git rev-parse HEAD >> "$SUPERLITE_RUN_ROOT/seen"; pwd -P >> "$SUPERLITE_RUN_ROOT/seen"'
    r = run(repo, "scratch", "--", cmd)
    assert r.returncode == 0, r.stderr
    seen = (repo / "seen").read_text().split("\n")
    assert seen[0] == "1" and seen[1] == a
    assert seen[2].startswith(str(repo / ".superlite" / "trees" / "scratch-"))
    assert "worktree: scratch tree " in r.stderr
    assert f" at {a[:12]} (start SHA); shared packages {repo}/.build/SourcePackages" in r.stderr
    assert "worktree: scratch tree removed" in r.stderr
    assert scratch_dirs(repo) == []
    assert git(repo, "worktree", "list", "--porcelain").count("worktree ") == 1
    b = git(repo, "rev-parse", "HEAD")
    r = run(repo, "scratch", "--rev", "HEAD", "--", cmd)
    seen = (repo / "seen").read_text().split("\n")
    assert seen[0] == "2" and seen[1] == b and " (--rev HEAD)" in r.stderr


def test_scratch_without_checkpoints_uses_merge_base(repo):
    a = A(repo)
    (repo / ".superlite" / "checkpoints.json").unlink()
    git(repo, "branch", "feat", "main")
    git(repo, "reset", "-q", "--hard", a)
    git(repo, "checkout", "-q", "-b", "feat2")
    commit(repo, "3\n", "C")
    r = run(repo, "scratch", "--", 'cat v > "$SUPERLITE_RUN_ROOT/seen"')
    assert r.returncode == 0, r.stderr
    assert (repo / "seen").read_text() == "1\n"


def test_scratch_exit_code_and_removal(repo):
    r = run(repo, "scratch", "--", "exit 3")
    assert r.returncode == 3 and scratch_dirs(repo) == []
    r = run(repo, "scratch", "--", "kill -TERM $$")
    assert r.returncode == 143 and scratch_dirs(repo) == []


@pytest.mark.parametrize("args", [["scratch"], ["scratch", "--"], ["scratch", "--rev", "HEAD"]])
def test_scratch_needs_command(repo, args):
    r = run(repo, *args)
    assert r.returncode == 2 and r.stderr == USAGE
    assert not (repo / ".superlite" / "trees").exists()


def test_scratch_plan_only_before_dashdash(repo):
    r = run(repo, "--plan", ".superlite", "scratch", "--", "printf", "%s ", "--plan", "keep")
    assert r.returncode == 0, r.stderr
    assert r.stdout == "--plan keep "


def test_scratch_bad_rev(repo):
    r = run(repo, "scratch", "--rev", "nope", "--", "true")
    assert r.returncode == 2 and "worktree: scratch: unknown revision nope" in r.stderr.splitlines()
    assert scratch_dirs(repo) == []
    assert worktree.scratch_rev(str(repo), "nope") == ("", "unknown revision nope")
    sha, label = worktree.scratch_rev(str(repo))
    assert sha == A(repo) and label == "start SHA"


def test_scratch_not_a_repo(tmp_path):
    d = tmp_path / "empty"
    d.mkdir()
    r = run(d, "scratch", "--", "true")
    assert r.returncode == 2 and r.stderr.strip() == "worktree: scratch needs a git repository with a commit"


def test_scratch_env_and_packages(repo):
    (repo / ".env").write_text("x")
    with (repo / ".git" / "info" / "exclude").open("a") as f:
        f.write(".env\n")
    cmd = 'env > "$SUPERLITE_RUN_ROOT/env"; pwd -P > "$SUPERLITE_RUN_ROOT/cwd"'
    r = run(repo, "scratch", "--", cmd)
    assert r.returncode == 0, r.stderr
    env = dict(ln.split("=", 1) for ln in (repo / "env").read_text().splitlines() if "=" in ln)
    tree = (repo / "cwd").read_text().strip()
    assert env["SUPERLITE_SCRATCH_TREE"] == tree
    assert env["SUPERLITE_RUN_ROOT"] == str(repo)
    assert env["SUPERLITE_SCRATCH_SHA"] == A(repo)
    assert env["SUPERLITE_DERIVED_DATA_PATH"] == f"{tree}/.build/DerivedData"
    assert env["SUPERLITE_SOURCE_PACKAGES"] == f"{repo}/.build/SourcePackages"
    assert (repo / ".build" / "SourcePackages").is_dir()
    assert subprocess.run(["git", "-C", str(repo), "check-ignore", "-q", ".build/x"], env=clean_env()).returncode == 0
    run(repo, "scratch", "--", "true")
    assert (repo / ".git" / "info" / "exclude").read_text().splitlines().count(".build/") == 1
    assert "worktree: ignored in the main checkout, missing here: .env" in r.stderr


def test_scratch_drops_stale_trees(repo):
    a = A(repo)
    trees.prepare_at(repo, "scratch-999999", a)
    trees.prepare_at(repo, "scratch-1", a)
    marker = repo / ".superlite" / "trees" / f"scratch-1.busy.{os.getpid()}"
    marker.write_text("")
    try:
        r = run(repo, "scratch", "--", "true")
        assert r.returncode == 0, r.stderr
        assert "worktree: removed stale scratch tree scratch-999999" in r.stderr.splitlines()
        assert scratch_dirs(repo) == ["scratch-1"]
    finally:
        marker.unlink(missing_ok=True)


@pytest.mark.skipif(os.name != "posix", reason="process groups")
def test_scratch_sigterm_removes_tree(repo):
    p = subprocess.Popen([sys.executable, str(WORKTREE), "scratch", "--", 'echo $$ > "$SUPERLITE_RUN_ROOT/pid"; exec sleep 30'],
                         cwd=str(repo), stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, env=clean_env())
    pidf = repo / "pid"
    end = time.time() + 10
    while time.time() < end and not (pidf.exists() and pidf.read_text().strip()):
        time.sleep(0.05)
    assert pidf.exists()
    child = int(pidf.read_text().strip())
    p.send_signal(signal.SIGTERM)
    assert p.wait(timeout=15) == 143
    p.communicate()
    assert scratch_dirs(repo) == []
    end = time.time() + 5
    alive = True
    while time.time() < end and alive:
        try:
            os.kill(child, 0)
            time.sleep(0.1)
        except ProcessLookupError:
            alive = False
    assert not alive


def _dead(pid, secs=5):
    end = time.time() + secs
    while time.time() < end:
        try:
            os.kill(pid, 0)
        except ProcessLookupError:
            return True
        time.sleep(0.1)
    return False


@pytest.mark.skipif(os.name != "posix", reason="process groups")
def test_scratch_second_sigterm_still_kills_group(repo):
    p = subprocess.Popen([sys.executable, str(WORKTREE), "scratch", "--",
                          'trap "" TERM HUP; echo $$ > "$SUPERLITE_RUN_ROOT/pid"; while :; do sleep 1; done'],
                         cwd=str(repo), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=clean_env())
    pidf = repo / "pid"
    end = time.time() + 10
    while time.time() < end and not (pidf.exists() and pidf.read_text().strip()):
        time.sleep(0.05)
    child = int(pidf.read_text().strip())
    p.send_signal(signal.SIGTERM)
    time.sleep(1)
    p.send_signal(signal.SIGTERM)
    p.wait(timeout=20)
    try:
        assert _dead(child)
        assert scratch_dirs(repo) == []
    finally:
        try:
            os.kill(child, signal.SIGKILL)
        except OSError:
            pass


@pytest.mark.skipif(os.name != "posix", reason="process groups")
def test_scratch_background_member_stopped_after_normal_exit(repo):
    r = run(repo, "scratch", "--", 'sleep 30 >/dev/null 2>&1 & echo $! > "$SUPERLITE_RUN_ROOT/bg"; exit 0')
    assert r.returncode == 0
    bg = int((repo / "bg").read_text().strip())
    try:
        assert _dead(bg)
    finally:
        try:
            os.kill(bg, signal.SIGKILL)
        except OSError:
            pass


@pytest.mark.skipif(os.name != "posix", reason="process groups")
def test_scratch_second_sigint_still_kills_group(repo):
    p = subprocess.Popen([sys.executable, str(WORKTREE), "scratch", "--",
                          'trap "" TERM HUP INT; echo $$ > "$SUPERLITE_RUN_ROOT/pid"; while :; do sleep 1; done'],
                         cwd=str(repo), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=clean_env())
    pidf = repo / "pid"
    end = time.time() + 10
    while time.time() < end and not (pidf.exists() and pidf.read_text().strip()):
        time.sleep(0.05)
    child = int(pidf.read_text().strip())
    p.send_signal(signal.SIGINT)
    time.sleep(1)
    p.send_signal(signal.SIGINT)
    p.wait(timeout=20)
    try:
        assert _dead(child)
        assert scratch_dirs(repo) == []
    finally:
        try:
            os.kill(child, signal.SIGKILL)
        except OSError:
            pass


@pytest.mark.skipif(os.name != "posix", reason="process groups")
def test_scratch_sigterm_stop_is_prompt(repo):
    p = subprocess.Popen([sys.executable, str(WORKTREE), "scratch", "--", 'echo $$ > "$SUPERLITE_RUN_ROOT/pid"; exec sleep 30'],
                         cwd=str(repo), stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, env=clean_env())
    pidf = repo / "pid"
    end = time.time() + 10
    while time.time() < end and not (pidf.exists() and pidf.read_text().strip()):
        time.sleep(0.05)
    time.sleep(0.5)
    start = time.monotonic()
    p.send_signal(signal.SIGTERM)
    assert p.wait(timeout=15) == 143
    assert time.monotonic() - start < 5


def test_scratch_env_statement_lines_carry_complexity_comment():
    lines = WORKTREE.read_text(encoding="utf-8").splitlines()
    start = next(i for i, ln in enumerate(lines) if ln.lstrip().startswith("env = dict(os.environ, SUPERLITE_SCRATCH_TREE"))
    for ln in lines[start : start + 2]:
        assert "# O(" in ln, ln
