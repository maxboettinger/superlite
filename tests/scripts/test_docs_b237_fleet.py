"""B237: docs/fleet.md and the SDD fleet.md name the sign-in screen, spawn timeout, standing note, git deny list and builds."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
FLEET = (ROOT / "docs" / "fleet.md").read_text(encoding="utf-8")
SDD = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")


def read(name):
    return (SCRIPTS / name).read_text(encoding="utf-8")


def section(title):
    body = FLEET.split(f"## {title}\n", 1)[1]
    return body.split("\n## ", 1)[0]


def test_fleet_names_sign_in_screen():
    assert "signed out (Claude Code sign-in screen)" in FLEET and "(signed out: account" in FLEET
    assert "signed out (Claude Code sign-in screen)" in read("fleet.py")
    assert "(signed out: account" in read("fleet_io.py")


def test_fleet_names_spawn_timeout():
    for text in (FLEET, SDD):
        assert "`fleet spawn` Bash call" in text and "600000 ms" in text
    assert "give the Bash call a timeout of 600000 ms" in read("fleet.py")


def test_fleet_names_standing_note_end():
    assert "run end: standing note" in FLEET and "--note /dev/null" in FLEET
    src = read("backlog_run.py")
    assert "run end: standing note" in src and "sl backlog note /dev/null" in src


def test_fleet_names_git_deny_and_root():
    for p in ("Bash(git checkout *)", "Bash(git restore *)", "Bash(git stash *)", "ROOT="):
        assert p in FLEET, p
    src = read("fleet_roles.py")
    for p in ("Bash(git checkout *)", "Bash(git restore *)", "Bash(git stash)", "Bash(git stash *)"):
        assert p in src, p


def test_fleet_names_whole_tree_and_builds():
    s = section("Run root and task trees")
    assert "whole-tree" in s and "two workers" in s
