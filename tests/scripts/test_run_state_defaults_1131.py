"""#1131: run_tests' run-state defaults go through state.default_dir(), never a bare cwd-relative .superlite."""
from __future__ import annotations

import argparse
import json
import sys

import pytest

from test_session_state import SCRIPTS, state  # noqa: F401

sys.path.insert(0, str(SCRIPTS))
import run_tests  # noqa: E402

A = "a1"


@pytest.fixture
def plug(tmp_path, monkeypatch):
    plugin = tmp_path / "plugin"
    (plugin / ".git").mkdir(parents=True)
    skills = plugin / "skills"
    scripts = skills / "subagent-driven-development" / "scripts"
    scripts.mkdir(parents=True)
    proj = tmp_path / "proj"
    (proj / ".git").mkdir(parents=True)
    monkeypatch.setattr(state, "PLUGIN_SKILLS", skills)
    for v in ("SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "SUPERLITE_PROJECT_DIR"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.setenv("SUPERLITE_SESSION_ID", A)
    monkeypatch.chdir(scripts)
    monkeypatch.setenv("PWD", str(scripts))
    monkeypatch.setenv("SUPERLITE_PROJECT_DIR", str(proj))
    return tmp_path, skills, proj


@pytest.fixture
def parsed(monkeypatch):
    got = {}
    real = argparse.ArgumentParser.parse_args

    def spy(self, argv=None, namespace=None):
        ns = real(self, argv, namespace)
        got["a"] = ns
        return ns

    monkeypatch.setattr(argparse.ArgumentParser, "parse_args", spy)
    return got


def test_record_from_plugin_writes_summary_in_session_project(plug):
    tmp, skills, proj = plug
    assert run_tests.main(["--record", "--passed", "1", "--command", "true"]) == 0
    assert (proj / ".superlite" / "test-summary.json").is_file()
    assert not any(skills.rglob(".superlite"))


def test_defaults_follow_state_dir(tmp_path, monkeypatch, parsed):
    s, w = tmp_path / "s" / ".superlite", tmp_path / "w"
    s.mkdir(parents=True)
    w.mkdir()
    monkeypatch.chdir(w)
    monkeypatch.setenv("PWD", str(w))
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(s))
    assert run_tests.main(["--record", "--passed", "1", "--command", "true"]) == 0
    a = parsed["a"]
    assert (a.log, a.ledger, a.summary) == (str(s / "incidents.jsonl"), str(s / "progress.md"), str(s / "test-summary.json"))
    assert (s / "test-summary.json").is_file()


def test_defaults_outside_plugin_unchanged(tmp_path, monkeypatch, parsed):
    for v in ("SUPERLITE_STATE_DIR", "CLAUDE_PROJECT_DIR", "SUPERLITE_PROJECT_DIR", "SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID"):
        monkeypatch.delenv(v, raising=False)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("PWD", str(tmp_path))
    assert run_tests.main(["--record", "--passed", "1", "--command", "true"]) == 0
    a = parsed["a"]
    assert (a.summary, a.log) == (".superlite/test-summary.json", ".superlite/incidents.jsonl")
    assert (tmp_path / ".superlite" / "test-summary.json").is_file()


def test_stable_plan_reads_state_dir(tmp_path, monkeypatch):
    s, w = tmp_path / "s" / ".superlite", tmp_path / "w"
    s.mkdir(parents=True)
    w.mkdir()
    (s / "stable.json").write_text(json.dumps({"plan": "docs/p.md"}), encoding="utf-8")
    monkeypatch.chdir(w)
    monkeypatch.setenv("PWD", str(w))
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(s))
    assert run_tests.stable_plan() == "docs/p.md"


def test_warned_file_in_state_dir(tmp_path, monkeypatch, capsys):
    s, w = tmp_path / "s" / ".superlite", tmp_path / "w"
    s.mkdir(parents=True)
    w.mkdir()
    monkeypatch.chdir(w)
    monkeypatch.setenv("PWD", str(w))
    monkeypatch.setenv("SUPERLITE_STATE_DIR", str(s))
    run_tests.warn_once("cmd", "warn line")
    assert json.loads((s / "derived-data-warned.json").read_text(encoding="utf-8")) == ["cmd"]
    assert not (w / ".superlite").exists()


def test_explicit_paths_need_no_state_folder(plug, monkeypatch):
    tmp, skills, proj = plug
    for v in ("SUPERLITE_SESSION_ID", "CLAUDE_CODE_SESSION_ID", "SUPERLITE_PROJECT_DIR"):
        monkeypatch.delenv(v, raising=False)
    out = tmp / "out"
    out.mkdir()
    argv = ["--record", "--passed", "1", "--command", "true", "--log", str(out / "l.jsonl"),
            "--ledger", str(out / "p.md"), "--summary", str(out / "s.json")]
    assert run_tests.main(argv) == 0
    assert (out / "s.json").is_file()
    assert not any(skills.rglob(".superlite"))
