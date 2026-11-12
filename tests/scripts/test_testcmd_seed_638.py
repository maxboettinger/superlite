"""testcmd: a seeded .superlite/test-cmd.json follows the main checkout's file unless edited (#638)."""
from __future__ import annotations

import json
import subprocess
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import testcmd  # noqa: E402


@pytest.fixture
def pair(tmp_path, monkeypatch):
    main, wt = tmp_path / "main", tmp_path / "wt"
    for d in (main, wt):
        (d / ".superlite").mkdir(parents=True)
    monkeypatch.setattr(testcmd, "_main_checkout_root", lambda root: main if testcmd.Path(root) == wt else None)
    return main, wt


def put(d, name, text):
    (d / ".superlite" / name).write_text(text)


def test_config_source_follows_main_while_copy_unedited(pair):
    main, wt = pair
    put(wt, "test-cmd.json", '{"test": "old"}'); put(wt, "test-cmd.seeded", '{"test": "old"}')
    put(main, "test-cmd.json", '{"test": "new"}')
    cfg, src, origin = testcmd.config_source(wt)
    assert (cfg["test"], src, origin) == ("new", "test-cmd.json", str(main / testcmd.CONFIG))
    assert "changed since it was seeded" in testcmd.seed_note(wt) and str(main / testcmd.CONFIG) in testcmd.seed_note(wt)


def test_edited_copy_runs(pair):
    main, wt = pair
    put(wt, "test-cmd.json", '{"test": "mine"}'); put(wt, "test-cmd.seeded", '{"test": "old"}')
    put(main, "test-cmd.json", '{"test": "new"}')
    assert testcmd.config_source(wt)[0]["test"] == "mine"
    assert "is the one that runs" in testcmd.seed_note(wt)


def test_no_record_keeps_copy(pair):
    main, wt = pair
    put(wt, "test-cmd.json", '{"test": "mine"}'); put(main, "test-cmd.json", '{"test": "new"}')
    assert testcmd.config_source(wt)[0]["test"] == "mine"
    assert "differs from the main checkout's" in testcmd.seed_note(wt)


def test_unreadable_main_keeps_copy(pair):
    main, wt = pair
    put(wt, "test-cmd.json", '{"test": "old"}'); put(wt, "test-cmd.seeded", '{"test": "old"}')
    put(main, "test-cmd.json", "not json")
    assert testcmd.config_source(wt)[0]["test"] == "old"


def test_note_empty_when_same_main_or_no_copy(pair):
    main, wt = pair
    assert testcmd.seed_note(wt) == ""
    put(wt, "test-cmd.json", '{"test": "a"}'); put(main, "test-cmd.json", '{"test": "a"}')
    assert testcmd.seed_note(wt) == "" and testcmd.seed_note(main) == ""


def test_record_seed(tmp_path, capsys):
    wt = tmp_path / "wt"; (wt / ".superlite").mkdir(parents=True)
    assert testcmd.record_seed(wt) is False and not (wt / testcmd.SEEDED).exists()
    put(wt, "test-cmd.json", '{"test": "a"}\n')
    assert testcmd.record_seed(wt) is True
    assert (wt / testcmd.SEEDED).read_bytes() == b'{"test": "a"}\n'
    out = capsys.readouterr()
    assert (out.out, out.err) == ("", "")


def test_testcmd_cli_prints_note(tmp_path):
    main, wt = tmp_path / "main", tmp_path / "wt"
    env = {"GIT_AUTHOR_NAME": "t", "GIT_AUTHOR_EMAIL": "t@t", "GIT_COMMITTER_NAME": "t", "GIT_COMMITTER_EMAIL": "t@t", "PATH": __import__("os").environ["PATH"], "HOME": str(tmp_path)}
    g = lambda *a, cwd=main: subprocess.run(["git", *a], cwd=cwd, env=env, check=True, capture_output=True)
    main.mkdir(); g("init", "-q"); g("commit", "-q", "--allow-empty", "-m", "i"); g("worktree", "add", "-q", str(wt))
    for d in (main, wt):
        (d / ".superlite").mkdir(exist_ok=True)
    put(main, "test-cmd.json", '{"test": "echo main"}'); put(wt, "test-cmd.json", '{"test": "echo mine"}')
    r = subprocess.run([sys.executable, str(SCRIPTS / "testcmd.py"), "--root", str(wt)], capture_output=True, text=True, env=env)
    assert r.stderr.strip().startswith("testcmd: this worktree's .superlite/test-cmd.json differs")
    out = json.loads(r.stdout)
    assert out["command"] == "echo mine" and out["source"] == "test-cmd.json" and out["origin"] == testcmd.CONFIG
