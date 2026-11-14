import json, stat, sys
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import accounts as ac  # noqa: E402

MARKS = ("Select login method:", "Paste code here if prompted", "Browser didn't open? Use the url below to sign in", "Opening browser to sign in")
USAGE = {"accounts": [{"name": "a1", "error": "not signed in", "limits": []}, {"name": "a2", "error": None, "limits": []}]}


def fake_bin(tmp_path, out, code):
    p = tmp_path / "claude-profile"
    p.write_text(f"#!/bin/sh\ncat <<'EOF'\n{out}\nEOF\nexit {code}\n")
    p.chmod(p.stat().st_mode | stat.S_IXUSR)
    return {"SUPERLITE_CLAUDE_PROFILE_BIN": str(p)}


def test_run_keeps_json_of_exit_1(tmp_path):
    env = fake_bin(tmp_path, json.dumps(USAGE), 1)
    u = ac.read_usage(env)
    assert u == USAGE and ac.pick_account(u, ["a1", "a2"]) == "a2"


def test_run_exit_1_bad_json_is_empty(tmp_path):
    assert ac.read_usage(fake_bin(tmp_path, "oops", 1)) == {}


def test_run_exit_1_json_list_is_empty(tmp_path):
    assert ac.read_usage(fake_bin(tmp_path, "[1]", 1)) == {}


def test_sign_in_marks():
    for m in MARKS:
        for pre in ("", "  ", "│ ", "❯ ", "● ", "> "):
            assert ac.sign_in_screen(f"top\n{pre}{m}\nbottom") is True
    assert ac.sign_in_screen(" Select login method:\n\n ❯ 1. Claude account with subscription") is True
    assert ac.sign_in_screen("│ Paste code here if prompted >  │") is True


def test_sign_in_quoted_is_false():
    assert ac.sign_in_screen("+    MARKS = ('Select login method:',)") is False
    assert ac.sign_in_screen("+Select login method:") is False
    assert ac.sign_in_screen("I saw Select login method: there") is False
    assert ac.sign_in_screen('"Select login method:"') is False


def test_sign_in_empty_false():
    assert ac.sign_in_screen("") is False
    assert ac.sign_in_screen("READY") is False
