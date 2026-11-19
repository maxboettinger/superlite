# tests/scripts/test_run_tests_base_skips_999.py
"""run_tests --base-skips reruns the base where the full run ran: a `maxapp remote` full run's base goes through the same remote command (#999)."""
import json
import os
import shlex
import stat
import subprocess
import sys
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

BASE_TESTS = '''import os

import pytest


@pytest.mark.skipif(os.environ.get("FAKE_REMOTE_HOST") == "1", reason="local host only")
def test_local_only():
    pass


@pytest.mark.skip(reason="gated")
def test_gated():
    pass


def test_plain():
    pass
'''
NEW_TESTS = BASE_TESTS + '''

@pytest.mark.skip(reason="new")
def test_new_skip():
    pass
'''
SKIPPED = ["tests/test_a.py::test_local_only", "tests/test_a.py::test_gated", "tests/test_a.py::test_new_skip"]
FULL = {"mode": "full", "started": 1763560000.5, "passed": 1, "failed": 0, "skipped": 3, "skipped_tests": SKIPPED}
PYTEST = f"{sys.executable} -m pytest tests -q -rs --no-fold-skipped -p no:cacheprovider"
FAKE_MAXAPP = '''#!/bin/sh
# a fake `maxapp remote`: logs its cwd and words, then runs its last word as the command with FAKE_REMOTE_HOST=1
pwd -P > "$FAKE_LOG"
for w in "$@"; do printf '%s\\n' "$w" >> "$FAKE_LOG"; done
[ "$1" = remote ] || exit 9
for w in "$@"; do last="$w"; done
FAKE_REMOTE_HOST=1 exec sh -c "$last"
'''
INNER = "uv run --group dev python -m pytest tests -q -rfEs --no-fold-skipped -p no:cacheprovider -n 4"


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    r = subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", *args], capture_output=True, text=True, env=env)
    assert r.returncode == 0, r.stderr
    return r.stdout.strip()


def make_repo(tmp_path, test):
    repo = tmp_path / "repo"
    (repo / "tests").mkdir(parents=True)
    (repo / "pytest.ini").write_text("[pytest]\n", encoding="utf-8")
    (repo / "tests" / "test_a.py").write_text(BASE_TESTS, encoding="utf-8")
    sd = repo / ".superlite"
    sd.mkdir()
    cmd = {"language": "python", "test": test, "test_file": f"{sys.executable} -m pytest {{files}} -q -p no:cacheprovider -o junit_family=xunit1 --junitxml={{junit}}", "junit": "{junit}"}
    (sd / "test-cmd.json").write_text(json.dumps(cmd), encoding="utf-8")
    git(repo, "init", "-q", "-b", "main")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "base")
    base = git(repo, "rev-parse", "HEAD")
    (sd / "checkpoints.json").write_text(json.dumps({"base": base, "entries": []}), encoding="utf-8")
    (repo / "tests" / "test_a.py").write_text(NEW_TESTS, encoding="utf-8")
    git(repo, "add", "tests")
    git(repo, "commit", "-q", "-m", "change")
    (sd / "test-summary-full.json").write_text(json.dumps(FULL), encoding="utf-8")
    (tmp_path / "bin").mkdir()
    fake = tmp_path / "bin" / "maxapp"
    fake.write_text(FAKE_MAXAPP, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IXUSR | stat.S_IXGRP | stat.S_IXOTH)
    return repo, base, tmp_path / "maxapp.log"


def rt(repo, log, *args):
    env = {k: v for k, v in os.environ.items() if not k.startswith("SUPERLITE_") and k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE", "FAKE_REMOTE_HOST")}
    env["PATH"] = f"{log.parent / 'bin'}{os.pathsep}{env.get('PATH', '')}"
    env["FAKE_LOG"] = str(log)
    return subprocess.run([sys.executable, str(SCRIPTS / "run_tests.py"), *args], cwd=repo, capture_output=True, text=True, timeout=180, env=env)


def base_summary(repo):
    return json.loads((repo / ".superlite" / "test-summary-base.json").read_text(encoding="utf-8"))


def logged(log):
    lines = log.read_text(encoding="utf-8").splitlines()
    return lines[0], lines[1:]


def tree_with_tests(tmp_path):
    (tmp_path / "tests" / "a").mkdir(parents=True)
    (tmp_path / "tests" / "a" / "test_x.py").write_text("", encoding="utf-8")
    return tmp_path


def test_remote_full_run_reruns_the_base_on_the_remote_host(tmp_path):
    repo, base, log = make_repo(tmp_path, f"maxapp remote --timeout 40 '{PYTEST}'")
    r = rt(repo, log, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    s = base_summary(repo)
    assert s["skipped_tests"] == ["tests/test_a.py::test_local_only", "tests/test_a.py::test_gated"]
    assert f"base {base[:7]} skips 2 of 3" in r.stderr
    cwd, words = logged(log)
    assert cwd.endswith("/.superlite/trees/base-skips")
    assert words[:3] == ["remote", "--timeout", "40"]
    assert words[3] == shlex.join([sys.executable, "-m", "pytest", "tests/test_a.py", "-q", "-rs", "--no-fold-skipped", "-p", "no:cacheprovider"])
    assert s["host"] == "remote"
    assert s["command"].startswith("maxapp remote --timeout 40 '")
    assert "run_tests: --base-skips runs on the full run's host: maxapp remote --timeout 40 " in r.stderr


def test_unnarrowable_remote_command_runs_whole_at_the_base(tmp_path):
    inner = f"cd . && {PYTEST}"
    repo, _base, log = make_repo(tmp_path, f"maxapp remote --timeout 40 '{inner}'")
    r = rt(repo, log, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    assert "run_tests: --base-skips: the remote test command cannot be narrowed to the skipped tests' files; it runs whole at the base: " in r.stderr
    assert logged(log)[1][3] == inner
    s = base_summary(repo)
    assert s["host"] == "remote"
    assert s["skipped_tests"] == ["tests/test_a.py::test_local_only", "tests/test_a.py::test_gated"]


def test_local_full_run_keeps_the_local_base_run(tmp_path):
    repo, _base, log = make_repo(tmp_path, PYTEST)
    r = rt(repo, log, "--base-skips")
    assert r.returncode == 0, r.stdout + r.stderr
    s = base_summary(repo)
    assert s["host"] == "local" and s["command"]
    assert s["skipped_tests"] == ["tests/test_a.py::test_gated"]
    assert not log.exists()
    assert "full run's host" not in r.stderr


def test_is_remote_command():
    assert run_tests.is_remote_command(f"maxapp remote --timeout 40 '{INNER}'")
    assert run_tests.is_remote_command("FOO=1 /opt/bin/maxapp remote 'pytest tests'")
    assert run_tests.is_remote_command("maxapp remote")
    assert not run_tests.is_remote_command("maxapp test --ios")
    assert not run_tests.is_remote_command(INNER)
    assert not run_tests.is_remote_command("echo 'maxapp remote'")
    assert not run_tests.is_remote_command("maxapp remote 'unclosed")


def test_narrowed_remote_replaces_the_test_paths(tmp_path):
    tree = tree_with_tests(tmp_path)
    got = run_tests.narrowed_remote(f"maxapp remote --timeout 40 '{INNER}'", ["tests/a/test_x.py"], tree)
    assert got == "maxapp remote --timeout 40 'uv run --group dev python -m pytest tests/a/test_x.py -q -rfEs --no-fold-skipped -p no:cacheprovider -n 4'"


def test_narrowed_remote_keeps_option_values_and_forms(tmp_path):
    tree = tree_with_tests(tmp_path)
    cmd = "maxapp remote --timeout=40 --host h1 'pytest -k \"a or b\" --tb short tests/a -o addopts= -n 2'"
    want = "maxapp remote --timeout=40 --host h1 " + shlex.quote("pytest -k 'a or b' --tb short tests/a/test_x.py tests/b/test_y.py -o addopts= -n 2")
    assert run_tests.narrowed_remote(cmd, ["tests/a/test_x.py", "tests/b/test_y.py"], tree) == want
    node = "maxapp remote 'pytest tests/a/test_x.py::test_q -q'"
    assert run_tests.narrowed_remote(node, ["tests/a/test_x.py"], tree) == "maxapp remote 'pytest tests/a/test_x.py -q'"


def test_narrowed_remote_appends_paths_without_positionals(tmp_path):
    tree = tree_with_tests(tmp_path)
    assert run_tests.narrowed_remote("maxapp remote 'python -m pytest -q'", ["tests/a/test_x.py"], tree) == "maxapp remote 'python -m pytest -q tests/a/test_x.py'"


def test_narrowed_remote_keeps_a_quoted_assignment_value(tmp_path):
    tree = tree_with_tests(tmp_path)
    got = run_tests.narrowed_remote("FOO=\"a b\" maxapp remote 'pytest tests'", ["tests/a/test_x.py"], tree)
    assert got == "FOO='a b' maxapp remote 'pytest tests/a/test_x.py'"


def test_narrowed_remote_multi_word_command(tmp_path):
    tree = tree_with_tests(tmp_path)
    got = run_tests.narrowed_remote("maxapp remote --no-cache uv run pytest tests -q", ["tests/a/test_x.py"], tree)
    assert got == "maxapp remote --no-cache uv run pytest tests/a/test_x.py -q"


def test_narrowed_remote_refuses_what_it_cannot_rewrite(tmp_path):
    tree = tree_with_tests(tmp_path)
    for cmd in ("pytest tests -q",
                "maxapp remote",
                "maxapp remote --timeout 40",
                "maxapp remote --frob 'pytest tests'",
                "maxapp remote 'cd sub && pytest tests'",
                "maxapp remote 'pytest tests | tee log'",
                "maxapp remote uv run pytest tests ';' echo",
                "maxapp remote 'pytest tests -n $N'",
                "maxapp remote 'pytest ~/tests'",
                "maxapp remote 'make test'",
                "maxapp remote 'pytest --frobnicate short tests'",
                "maxapp remote 'pytest missing_dir'",
                "maxapp remote 'pytest tests --ignore tests/*'",
                "maxapp remote 'pytest tests --ignore tests/?'",
                "maxapp remote 'pytest tests -k \"a[b]\"'",
                "maxapp remote 'pytest tests --ignore tests/{a,b}'",
                "maxapp remote pytest tests --ignore 'tests/*'",
                "maxapp remote --host 'h*' 'pytest tests'"):
        assert run_tests.narrowed_remote(cmd, ["tests/a/test_x.py"], tree) is None, cmd
