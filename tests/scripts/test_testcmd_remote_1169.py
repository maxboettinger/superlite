"""A maxapp remote test command's {junit} is an in-tree report fetched back with --fetch (#1169)."""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
import run_tests as rt  # noqa: E402
import testcmd  # noqa: E402

RUN_TESTS = SCRIPTS / "run_tests.py"
TEST = "maxapp remote --timeout 40 'true && fakerunner tests'"
TEST_FILE = "fakerunner {files} --outputFile.junit={junit}"
FORM = "maxapp remote --timeout 40 --kind file 'true && fakerunner {files} --outputFile.junit={junit}'"
NAME = re.compile(r"^\.superlite-junit-[0-9a-f]{12}\.xml$")

# A fake remote host. `maxapp remote` ships the git tree (tracked and untracked, not ignored) to a fresh folder, runs the
# snippet there and copies each --fetch path back only after exit 0, as maxapp remote does; it logs its words as JSON lines.
FAKE_MAXAPP = r'''#!/usr/bin/env python3
import json, os, shlex, shutil, subprocess, sys, tempfile
args = sys.argv[1:]
with open(os.environ["FAKE_MAXAPP_LOG"], "a", encoding="utf-8") as log:
    log.write(json.dumps(args) + "\n")
assert args[0] == "remote", args
args, fetch = args[1:], []
while args and args[0].startswith("--"):
    opt = args.pop(0)
    if opt == "--fetch":
        fetch.append(args.pop(0))
    elif opt in ("--host", "--timeout", "--kind"):
        args.pop(0)
    elif opt == "--":
        break
snippet = args[0] if len(args) == 1 else shlex.join(args)
top = subprocess.run(["git", "rev-parse", "--show-toplevel"], capture_output=True, text=True, check=True).stdout.strip()
remote = tempfile.mkdtemp(prefix="fake-remote-")
listed = subprocess.run(["git", "-C", top, "ls-files", "-z", "--cached", "--others", "--exclude-standard"], capture_output=True, check=True).stdout
for name in filter(None, listed.decode("utf-8").split("\0")):
    if os.path.isfile(os.path.join(top, name)):
        os.makedirs(os.path.dirname(os.path.join(remote, name)), exist_ok=True)
        shutil.copy(os.path.join(top, name), os.path.join(remote, name))
rc = subprocess.run(["sh", "-c", snippet], cwd=remote, env={**os.environ, "FAKE_REMOTE_ROOT": remote}).returncode
if rc != 0:
    if fetch:
        print("maxapp remote: --fetch skipped: the command failed", file=sys.stderr)
    sys.exit(1)
for p in fetch:
    if not os.path.exists(os.path.join(remote, p)):
        print(f"maxapp remote: --fetch {p}: not found after the command", file=sys.stderr)
        sys.exit(2)
for p in fetch:
    shutil.copy(os.path.join(remote, p), os.path.join(top, p))
sys.exit(0)
'''

# Its test runner refuses a report outside the shipped tree, as the remote container does (EACCES mkdir); two cases per
# file, the second fails when the file says "fail"; it prints counts only when red, so a green count comes from the report.
FAKE_RUNNER = r'''#!/usr/bin/env python3
import os, sys
files = [a for a in sys.argv[1:] if not a.startswith("--")]
out = next(a.split("=", 1)[1] for a in sys.argv[1:] if a.startswith("--outputFile.junit="))
root = os.path.realpath(os.environ.get("FAKE_REMOTE_ROOT", os.getcwd()))
if os.path.commonpath([root, os.path.realpath(os.path.abspath(out))]) != root:
    print(f"Error: EACCES: permission denied, mkdir '{os.path.dirname(out)}'")
    sys.exit(1)
fail = any("fail" in open(f, encoding="utf-8").read() for f in files)
bad = '<failure message="expected 2">x</failure>' if fail else ""
cases = "".join(f'<testcase classname="{f}" name="adds" file="{f}"/><testcase classname="{f}" name="subtracts" file="{f}">{bad}</testcase>' for f in files)
with open(out, "w", encoding="utf-8") as fh:
    fh.write(f'<?xml version="1.0"?><testsuites><testsuite name="s">{cases}</testsuite></testsuites>')
if fail:
    print(f" FAIL  {files[0]} > subtracts")
    print(" Tests  1 failed | 1 passed (2)")
    sys.exit(1)
print("ran")
'''


def git(repo, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    subprocess.run(["git", "-C", str(repo), "-c", "user.email=t@t", "-c", "user.name=t", *args], check=True, capture_output=True, env=env)


def project(tmp_path, cfg, body="ok"):
    (tmp_path / "tests").mkdir()
    (tmp_path / "tests" / "a_test.sh").write_text(body, encoding="utf-8")
    (tmp_path / ".gitignore").write_text(".superlite/\nbin/\nmaxapp.log\n", encoding="utf-8")
    (tmp_path / ".superlite").mkdir()
    (tmp_path / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg), encoding="utf-8")
    (tmp_path / "bin").mkdir()
    for name, text in (("maxapp", FAKE_MAXAPP), ("fakerunner", FAKE_RUNNER)):
        (tmp_path / "bin" / name).write_text(text, encoding="utf-8")
        (tmp_path / "bin" / name).chmod(0o755)
    git(tmp_path, "init", "-q")
    git(tmp_path, "add", "-A")
    git(tmp_path, "commit", "-q", "-m", "init")


def go(tmp_path, *args):
    env = {k: v for k, v in os.environ.items() if k not in ("GIT_DIR", "GIT_INDEX_FILE", "GIT_WORK_TREE")}
    env.update(SUPERLITE_GUI_CHECK="0", PYTHONIOENCODING="utf-8", FAKE_MAXAPP_LOG=str(tmp_path / "maxapp.log"),
               PATH=f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    cp = subprocess.run([sys.executable, str(RUN_TESTS), *args], capture_output=True, cwd=tmp_path, env=env, timeout=120)
    cp.both = cp.stdout.decode("utf-8") + cp.stderr.decode("utf-8")
    return cp


def summary(tmp_path):
    return json.loads((tmp_path / ".superlite" / "test-summary.json").read_text(encoding="utf-8"))


def calls(tmp_path):
    return [json.loads(x) for x in (tmp_path / "maxapp.log").read_text(encoding="utf-8").splitlines()]


def leftovers(tmp_path):
    return sorted(p.name for p in tmp_path.glob(".superlite-junit-*"))


def test_remote_fetch_inserts_after_maxapp_remote():
    assert testcmd.remote_fetch("maxapp remote --timeout 40 --kind file 'x --o=r.xml'", "r.xml") == (
        "maxapp remote --fetch r.xml --timeout 40 --kind file 'x --o=r.xml'")
    assert testcmd.remote_fetch("maxapp remote", "r.xml") == "maxapp remote --fetch r.xml"


def test_remote_fetch_keeps_the_head_words_as_written():
    assert testcmd.remote_fetch("CI=1 X='a remote b' /opt/bin/maxapp remote 'x'", "r.xml") == (
        "CI=1 X='a remote b' /opt/bin/maxapp remote --fetch r.xml 'x'")
    assert testcmd.remote_fetch("maxapp remote 'x'", "a b.xml") == "maxapp remote --fetch 'a b.xml' 'x'"


def test_remote_fetch_adds_no_second_fetch():
    cmd = "maxapp remote --timeout 40 --fetch r.xml 'x'"
    assert testcmd.remote_fetch(cmd, "r.xml") == cmd
    assert testcmd.remote_fetch("maxapp remote --fetch out 'x'", "r.xml") == "maxapp remote --fetch r.xml --fetch out 'x'"


def test_remote_fetch_none_cases():
    assert testcmd.remote_fetch("bunx vitest run", "r.xml") is None
    assert testcmd.remote_fetch("echo 'maxapp remote'", "r.xml") is None
    assert testcmd.remote_fetch("maxapp remote 'unclosed", "r.xml") is None
    assert testcmd.remote_fetch("maxapp 'remote' 'x'", "r.xml") is None


def test_remote_junit_names_an_in_tree_report(tmp_path):
    git(tmp_path, "init", "-q")
    cmd, report = rt.remote_junit("maxapp remote --timeout 40 'r --o={junit}'", tmp_path)
    name = report.name
    assert NAME.match(name)
    assert report == Path(subprocess.run(["git", "-C", str(tmp_path), "rev-parse", "--show-toplevel"], capture_output=True, text=True).stdout.strip()) / name
    assert cmd == f"maxapp remote --fetch {name} --timeout 40 'r --o={name}'"
    assert rt.remote_junit("r --o={junit}", tmp_path) == ("r --o={junit}", None)
    assert rt.remote_junit("maxapp remote 'r'", tmp_path) == ("maxapp remote 'r'", None)


def test_fast_runs_the_proposed_remote_form_end_to_end(tmp_path):
    assert testcmd.remote_test_file(TEST, TEST_FILE) == FORM
    project(tmp_path, {"language": "other", "test": TEST, "test_file": FORM, "lock": False})
    cp = go(tmp_path, "--fast", "tests/a_test.sh")
    assert cp.returncode == 0, cp.both
    s = summary(tmp_path)
    assert (s["passed"], s["failed"], s["mode"]) == (2, 0, "fast")
    (words,) = calls(tmp_path)
    assert words[:2] == ["remote", "--fetch"] and NAME.match(words[2]), words
    assert words[-1] == f"true && fakerunner tests/a_test.sh --outputFile.junit={words[2]}"
    assert leftovers(tmp_path) == []


def test_go_keeps_the_superlite_test_environment(tmp_path, monkeypatch):
    project(tmp_path, {"language": "other", "test": TEST, "test_file": FORM, "lock": False})
    monkeypatch.setenv("SUPERLITE_DISK_FLOOR_GB", "99999999")
    cp = go(tmp_path, "--fast", "tests/a_test.sh")
    assert cp.returncode == 2 and "floor" in cp.both, cp.both


def test_red_remote_run_reads_the_printed_output(tmp_path):
    project(tmp_path, {"language": "other", "test": TEST, "test_file": FORM, "junit": "{junit}", "lock": False}, body="fail")
    cp = go(tmp_path, "--fast", "tests/a_test.sh")
    assert cp.returncode == 1, cp.both
    s = summary(tmp_path)
    assert (s["passed"], s["failed"]) == (1, 1)
    log = (tmp_path / ".superlite" / "test-output.log").read_text(encoding="utf-8")  # a red run prints only the log path
    assert "--fetch skipped: the command failed" in cp.both + log
    assert "EACCES" not in cp.both + log
    assert leftovers(tmp_path) == []


def test_base_rerun_of_a_remote_full_command_fetches_its_report(tmp_path, monkeypatch):
    full = "maxapp remote --timeout 40 'fakerunner tests/a_test.sh --outputFile.junit={junit}'"
    project(tmp_path, {"language": "other", "test": full, "lock": False})
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PATH", f"{tmp_path / 'bin'}{os.pathsep}{os.environ['PATH']}")
    monkeypatch.setenv("FAKE_MAXAPP_LOG", str(tmp_path / "maxapp.log"))
    got = rt.run_base_tests(SimpleNamespace(limit=None), tmp_path, tmp_path, ["tests/a_test.sh"])
    assert not isinstance(got, int), got
    _skipped, counts, _seconds, host, ran = got
    assert host == "remote"
    assert counts == {"passed": 2, "failed": 0, "skipped": 0}
    assert ran.startswith("maxapp remote --fetch .superlite-junit-")
    assert leftovers(tmp_path) == []


def test_tools_md_row_names_the_in_tree_report():
    rows = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8").splitlines()
    at = next(i for i, r in enumerate(rows) if r.startswith("| `testcmd` remote test_file (#1147) |"))
    row = rows[at + 1]
    assert row.startswith("| `run_tests` remote {junit} (#1169) |")
    for text in ("`.superlite-junit-<12 hex>.xml`", "`--fetch", "exited 0", "printed output", "--base-skips"):
        assert text in row, text
