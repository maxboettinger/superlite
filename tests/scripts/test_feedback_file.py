import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = (Path(__file__).resolve().parents[2] / "skills"
          / "subagent-driven-development" / "scripts" / "feedback.py")


@pytest.fixture(autouse=True)
def _home_in_tmp(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path))  # O(1)


def run(*args, cwd=None, stdin=None):
    return subprocess.run([sys.executable, str(SCRIPT), *args],  # O(1) + spawn
                          capture_output=True, text=True, cwd=cwd, input=stdin,
                          env=dict(os.environ))


def entries(home: Path):
    return [json.loads(x) for x in (home / "feedback.jsonl").read_text(encoding="utf-8").splitlines()]  # O(i*w)


def test_add_from_file(tmp_path):
    (tmp_path / "note.txt").write_text("slow lint", encoding="utf-8")
    r = run("add", "--file", "note.txt", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    [e] = entries(tmp_path)
    assert e["text"] == "slow lint"


def test_add_from_stdin(tmp_path):
    r = run("add", "--file", "-", cwd=tmp_path, stdin="slow lint")
    assert r.returncode == 0, r.stderr
    [e] = entries(tmp_path)
    assert e["text"] == "slow lint"


def test_add_text_still_works(tmp_path):
    r = run("add", "slow lint", cwd=tmp_path)
    assert r.returncode == 0, r.stderr
    [e] = entries(tmp_path)
    assert e["text"] == "slow lint"


def test_add_both_refused(tmp_path):
    (tmp_path / "note.txt").write_text("slow lint", encoding="utf-8")
    r = run("add", "x", "--file", "note.txt", cwd=tmp_path)
    assert r.returncode == 2
    assert "give the text or --file, not both" in r.stderr


def test_add_neither_refused(tmp_path):
    r = run("add", cwd=tmp_path)
    assert r.returncode == 2
    assert "feedback text is empty" in r.stderr


def test_add_empty_stdin_refused(tmp_path):
    r = run("add", "--file", "-", cwd=tmp_path, stdin="")
    assert r.returncode == 2
    assert "feedback text is empty" in r.stderr


def test_add_directory_refused(tmp_path):
    (tmp_path / "d").mkdir()
    r = run("add", "--file", "d", cwd=tmp_path)
    assert r.returncode == 2
    assert "cannot read d" in r.stderr


def test_add_undecodable_file_refused(tmp_path):
    (tmp_path / "b.bin").write_bytes(b"\xff\xfe\x00bad\x80")
    r = run("add", "--file", "b.bin", cwd=tmp_path)
    assert r.returncode == 2
    assert "cannot read b.bin" in r.stderr


def test_add_file_text_is_scrubbed(tmp_path):
    (tmp_path / "n.txt").write_text("failed in /Users/alice/x/a.py\ntoken ghp_abcdefghijklmnop1234", encoding="utf-8")
    assert run("add", "--file", "n.txt", cwd=tmp_path).returncode == 0
    [e] = entries(tmp_path)
    assert "alice" not in e["text"] and "ghp_" not in e["text"] and "<secret>" in e["text"]


def test_add_missing_file(tmp_path):
    r = run("add", "--file", "nope.txt", cwd=tmp_path)
    assert r.returncode == 2
    assert "cannot read nope.txt" in r.stderr
