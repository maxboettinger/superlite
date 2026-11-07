import json
import os
import stat
import subprocess
import sys
from pathlib import Path

import pytest

POSIX_ONLY = pytest.mark.skipif(os.name == "nt", reason="fake ssh is an sh script")
SCRIPT = (Path(__file__).resolve().parents[2] / "skills"
          / "subagent-driven-development" / "scripts" / "feedback.py")
REMOTE_ID = "abcdefabcdef"


def run(*args, cwd=None, env=None):
    e = dict(os.environ)
    e.update(env or {})
    return subprocess.run([sys.executable, str(SCRIPT), *args],
                          capture_output=True, text=True, cwd=cwd, env=e)


def entries():
    f = Path(os.environ["SUPERLITE_HOME"]) / "feedback.jsonl"
    return [json.loads(x) for x in f.read_text(encoding="utf-8").splitlines()]


def triaged_file():
    return Path(os.environ["SUPERLITE_HOME"]) / "feedback-triaged.json"


def add_two(tmp_path):
    assert run("add", "first finding here", cwd=tmp_path).returncode == 0
    assert run("add", "second finding there", cwd=tmp_path).returncode == 0
    a, b = (e["id"] for e in entries())
    return a, b


def fake_ssh(tmp_path, body):
    fake = tmp_path / "fake-ssh"
    fake.write_text("#!/bin/sh\n" + body, encoding="utf-8")
    fake.chmod(fake.stat().st_mode | stat.S_IEXEC)
    return fake


def remote_ssh(tmp_path):
    remote = {"v": 1, "id": REMOTE_ID, "date": "2026-10-20T10:00:00Z", "host": "mini",
              "kind": "slow", "text": "remote slowness in run_tests", "version": "1.2.5",
              "harness": "pi", "project": "p", "session": "", "plan": ""}
    return fake_ssh(tmp_path, f"case \"$*\" in *mini*) echo '{json.dumps(remote)}';; *) exit 255;; esac\n")


def stored():
    return json.loads(triaged_file().read_text(encoding="utf-8"))["ids"]


def test_mark_splits_a_space_joined_argument(tmp_path):
    a, b = add_two(tmp_path)
    r = run("mark", f"{a} {b}", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert json.loads(triaged_file().read_text(encoding="utf-8")) == {"ids": sorted([a, b])}
    assert "feedback marked: 2" in r.stdout


def test_mark_rejects_an_unknown_id(tmp_path):
    a, _ = add_two(tmp_path)
    r = run("mark", a, "deadbeef0000", cwd=tmp_path)
    assert r.returncode == 2
    assert "unknown feedback id deadbeef0000" in r.stderr
    assert not triaged_file().exists()


def test_mark_typo_in_joined_argument_writes_nothing(tmp_path):
    a, b = add_two(tmp_path)
    assert run("mark", a, cwd=tmp_path).returncode == 0
    r = run("mark", f"{b} {b}x", cwd=tmp_path)
    assert r.returncode == 2
    assert f"{b}x" in r.stderr
    assert json.loads(triaged_file().read_text(encoding="utf-8")) == {"ids": [a]}


def test_mark_blank_argument_is_usage_error(tmp_path):
    add_two(tmp_path)
    r = run("mark", "  ", cwd=tmp_path)
    assert r.returncode == 2
    assert "no feedback ids given" in r.stderr


def test_mark_again_is_idempotent(tmp_path):
    a, _ = add_two(tmp_path)
    assert run("mark", a, cwd=tmp_path).returncode == 0
    assert run("mark", a, cwd=tmp_path).returncode == 0
    assert json.loads(triaged_file().read_text(encoding="utf-8")) == {"ids": [a]}


def test_mark_duplicates_collapse(tmp_path):
    a, _ = add_two(tmp_path)
    r = run("mark", f"{a} {a}", a, cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    assert "feedback marked: 1" in r.stdout


@POSIX_ONLY
def test_mark_accepts_an_id_from_a_host(tmp_path):
    r = run("mark", REMOTE_ID, "--host", "mini", cwd=tmp_path, env={"SUPERLITE_SSH": str(remote_ssh(tmp_path))})
    assert r.returncode == 0, r.stderr
    assert stored() == [REMOTE_ID]


@POSIX_ONLY
def test_mark_reads_the_hosts_file(tmp_path):
    home = Path(os.environ["SUPERLITE_HOME"])
    home.mkdir(parents=True, exist_ok=True)
    (home / "feedback-hosts").write_text("# macs\nmini\n", encoding="utf-8")
    r = run("mark", REMOTE_ID, cwd=tmp_path, env={"SUPERLITE_SSH": str(remote_ssh(tmp_path))})
    assert r.returncode == 0, r.stderr
    assert stored() == [REMOTE_ID]


@POSIX_ONLY
def test_mark_local_ids_start_no_ssh(tmp_path):
    a, _ = add_two(tmp_path)
    fake = fake_ssh(tmp_path, f"touch '{tmp_path / 'ssh-ran'}'\nexit 255\n")
    r = run("mark", a, "--host", "mini", cwd=tmp_path, env={"SUPERLITE_SSH": str(fake)})
    assert r.returncode == 0, r.stderr
    assert not (tmp_path / "ssh-ran").exists()


@POSIX_ONLY
def test_mark_unreachable_host_rejects(tmp_path):
    fake = fake_ssh(tmp_path, "exit 255\n")
    r = run("mark", REMOTE_ID, "--host", "gone", cwd=tmp_path, env={"SUPERLITE_SSH": str(fake)})
    assert r.returncode == 2
    assert f"unknown feedback id {REMOTE_ID}" in r.stderr and "gone" in r.stderr


def test_docstring_documents_mark_host_and_split():
    import importlib.util
    path = Path(__file__).resolve().parents[2] / "skills/subagent-driven-development/scripts/feedback.py"
    doc = path.read_text().split('"""')[1]
    assert "feedback.py mark ID... [--host H]..." in doc
    assert "splits on whitespace" in doc and "exit 2" in doc
