"""run_tests --base-skips: run the full run's skipped tests at the run's base commit in a scratch tree (#886)."""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import trees  # noqa: E402

BASE_TESTS = """import pytest


@pytest.mark.skip(reason="gated")
def test_gated():
    pass


def test_plain():
    pass
"""
NEW_TESTS = BASE_TESTS + """

@pytest.mark.skip(reason="new")
def test_new_skip():
    pass
"""
FULL = {"mode": "full", "started": 1763550000.5, "passed": 1, "failed": 0, "skipped": 2,
        "skipped_tests": ["tests/test_a.py::test_gated", "tests/test_a.py::test_new_skip"]}


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def make_repo(tmp_path, checkpoints=True, full=FULL, new_tests=NEW_TESTS, branch_off=False, base_tests=BASE_TESTS):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "tests" / "test_a.py").write_text(base_tests, encoding="utf-8")
    sd = repo / ".superlite"
    sd.mkdir()
    cmd = {"language": "python", "test_file": f"{sys.executable} -m pytest {{files}} -q -p no:cacheprovider -o junit_family=xunit1 --junitxml={{junit}}", "junit": "{junit}"}
    (sd / "test-cmd.json").write_text(json.dumps(cmd), encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    if branch_off:
        git(repo, "checkout", "-q", "-b", "work")
    if checkpoints:
        (sd / "checkpoints.json").write_text(json.dumps({"base": base, "entries": []}), encoding="utf-8")
    (repo / "tests" / "test_a.py").write_text(new_tests, encoding="utf-8")
    git(repo, "add", "tests")
    git(repo, "commit", "-q", "-m", "change")
    if full is not None:
        (sd / "test-summary-full.json").write_text(json.dumps(full), encoding="utf-8")
    return repo, base


def rt(repo, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    return subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), *args], cwd=repo, capture_output=True, text=True, timeout=180, env=env)


def base_file(repo):
    return Path(repo) / ".superlite" / "test-summary-base.json"


def no_tree(repo):
    assert not (Path(repo) / ".superlite" / "trees" / "base-skips").exists()
    assert "base-skips" not in git(repo, "worktree", "list")


def test_base_skips_tags_only_base_skipped(tmp_path):
    repo, base = make_repo(tmp_path)
    r = rt(repo, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    s = json.loads(base_file(repo).read_text(encoding="utf-8"))
    assert s["mode"] == "base" and s["base"] == base and s["full_started"] == 1763550000.5
    assert s["compared"] == FULL["skipped_tests"]
    assert s["skipped_tests"] == ["tests/test_a.py::test_gated"]
    assert f"base {base[:7]} skips 1 of 2" in r.stderr


def test_base_skips_merge_base_without_checkpoints(tmp_path):
    repo, base = make_repo(tmp_path, checkpoints=False, branch_off=True)
    r = rt(repo, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    assert json.loads(base_file(repo).read_text(encoding="utf-8"))["base"] == base


def test_base_skips_no_full_summary(tmp_path):
    repo, _ = make_repo(tmp_path, full=None)
    r = rt(repo, "--base-skips")
    assert r.returncode == 2
    assert "run_tests: --base-skips needs a full run's summary; run sl run_tests --full first" in r.stderr
    assert not base_file(repo).exists()


def test_base_skips_nothing_skipped(tmp_path):
    repo, _ = make_repo(tmp_path, full={**FULL, "skipped": 0, "skipped_tests": []})
    r = rt(repo, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "run_tests: --base-skips: the full run skipped nothing" in r.stderr
    assert not base_file(repo).exists()


def test_base_skips_counted_but_unnamed(tmp_path):
    repo, _ = make_repo(tmp_path, full={**FULL, "skipped": 12, "skipped_tests": []})
    r = rt(repo, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "the full run names none of its 12 skipped tests (its output lists no skipped test names); nothing to compare" in r.stderr
    assert "skipped nothing" not in r.stderr
    assert not base_file(repo).exists()


def test_base_skips_reads_background_full_summary_after_fast_run(tmp_path):
    repo, base = make_repo(tmp_path, full=None)
    sd = repo / ".superlite"
    (sd / "test-summary-20261119-101500.json").write_text(json.dumps(FULL), encoding="utf-8")
    os.utime(sd / "test-summary-20261119-101500.json", (1000, 1000))
    (sd / "test-summary.json").write_text(json.dumps({"mode": "fast", "started": 1763550900.0, "passed": 1, "failed": 0, "skipped": 0, "skipped_tests": []}), encoding="utf-8")
    r = rt(repo, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    d = json.loads(base_file(repo).read_text(encoding="utf-8"))
    assert d["base"] == base and d["compared"] == FULL["skipped_tests"]


@pytest.mark.parametrize("flags", [["--full"], ["--fast", "tests/test_a.py"], ["--affected"], ["--task", "T1"], ["--record"], ["--destination", "all"], ["--background"]])
def test_base_skips_refuses_other_modes(tmp_path, flags):
    repo, _ = make_repo(tmp_path)
    r = rt(repo, "--base-skips", *flags)
    assert r.returncode == 2 and "--base-skips" in r.stderr
    assert not base_file(repo).exists()
    no_tree(repo)


def test_base_skips_writes_no_other_state(tmp_path):
    repo, _ = make_repo(tmp_path)
    sd = repo / ".superlite"
    full = (sd / "test-summary-full.json").read_bytes()
    r = rt(repo, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    assert (sd / "test-summary-full.json").read_bytes() == full
    for name in ("test-summary.json", "test-summary.latest", "incidents.jsonl", "progress.md"):
        assert not (sd / name).exists(), name


def test_tree_removed_on_every_path(tmp_path):
    repo, _ = make_repo(tmp_path)
    assert rt(repo, "--base-skips").returncode == 0
    no_tree(repo)
    # the base test file cannot be imported
    bad_repo, _ = make_repo(tmp_path / "bad", base_tests="import not_there_886\n" + BASE_TESTS)
    r = rt(bad_repo, "--base-skips")
    assert r.returncode == 1, r.stdout + r.stderr
    assert "base run gave no result" in r.stderr or r.stdout.split()[1] != "0"  # no result, or a red count
    no_tree(bad_repo)
    # a missing base commit
    gone_repo, _ = make_repo(tmp_path / "gone")
    (gone_repo / ".superlite" / "checkpoints.json").write_text(json.dumps({"base": "0" * 40, "entries": []}), encoding="utf-8")
    r = rt(gone_repo, "--base-skips")
    assert r.returncode == 2, r.stdout + r.stderr
    no_tree(gone_repo)


def test_prepare_at_detached_no_overlay(tmp_path):
    repo, base = make_repo(tmp_path)
    tree = trees.prepare_at(repo, "k", base)
    assert Path(tree) == Path(repo).resolve() / ".superlite" / "trees" / "k"
    assert git(tree, "rev-parse", "HEAD") == base
    assert subprocess.run(["git", "-C", str(tree), "symbolic-ref", "-q", "HEAD"], capture_output=True).returncode != 0
    (repo / "tests" / "test_a.py").write_text("changed\n", encoding="utf-8")
    assert (Path(tree) / "tests" / "test_a.py").read_text(encoding="utf-8") == BASE_TESTS
    head = git(repo, "rev-parse", "HEAD")
    again = trees.prepare_at(repo, "k", head)
    assert Path(again) == Path(tree) and git(tree, "rev-parse", "HEAD") == head
    assert "test_new_skip" in (Path(tree) / "tests" / "test_a.py").read_text(encoding="utf-8")
