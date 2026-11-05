import json, os, sys
from pathlib import Path
from _fixtures import FIXTURES
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import accounts as ac  # noqa: E402
FAKE = FIXTURES / "fleet" / "claude-profile"

def acc(name, n, **limits):
    return {"name": name, "n": n, "email": "", "plan": "Ultra", "error": None,
            "limits": [{"kind": k, "percent": v, "resets_at": "2026-11-10T20:59:59+00:00"} for k, v in limits.items()]}

def test_picks_lowest_weekly():
    u = {"accounts": [acc("claude1", 1, weekly_all=65), acc("claude3", 3, weekly_all=3, five_hour=22)]}
    assert ac.pick_account(u, ["claude1", "claude3"]) == "claude3"

def test_five_hour_90_is_skipped():
    u = {"accounts": [acc("claude1", 1, five_hour=95, weekly_all=10)]}
    assert ac.pick_account(u, ["claude1"]) is None and "claude1" in " ".join(ac.reasons(u, ["claude1"]))

def test_weekly_100_is_skipped():
    u = {"accounts": [acc("claude1", 1, five_hour=0, weekly_all=100), acc("claude2", 2, weekly_all=99)]}
    assert ac.pick_account(u, ["claude1", "claude2"]) == "claude2"

def test_tie_lowest_n_wins():
    u = {"accounts": [acc("claude3", 3, weekly_all=40), acc("claude1", 1, weekly_all=40)]}
    assert ac.pick_account(u, ["claude3", "claude1"]) == "claude1"

def test_error_account_skipped():
    a = acc("claude1", 1, weekly_all=1); a["error"] = "login expired"
    u = {"accounts": [a, acc("claude2", 2, weekly_all=50)]}
    assert ac.pick_account(u, ["claude1", "claude2"]) == "claude2"
    assert "claude1: error login expired" in ac.reasons(u, ["claude1", "claude2"])

def test_empty_usage_takes_first_allowed():
    assert ac.pick_account({}, ["claude2", "claude1"]) == "claude2"

def test_allowed_filters_usage():
    u = {"accounts": [acc("claude1", 1, weekly_all=1), acc("claude2", 2, weekly_all=50)]}
    assert ac.pick_account(u, ["claude2"]) == "claude2"

def test_account_dir_and_current(monkeypatch):
    listing = {"accounts": [{"name": "claude1", "dir": "/x/.claude-account1"}]}
    assert ac.account_dir(listing, "claude1") == "/x/.claude-account1"
    monkeypatch.setenv("CLAUDE_CONFIG_DIR", "/y"); assert ac.account_dir(listing, "current") == "/y"
    monkeypatch.delenv("CLAUDE_CONFIG_DIR"); assert ac.account_dir(listing, "current") == os.path.expanduser("~/.claude")
    assert ac.account_dir(listing, "current", {"CLAUDE_CONFIG_DIR": "/z"}) == "/z" and ac.account_dir(listing, "current", {}) == os.path.expanduser("~/.claude")
    assert ac.account_dir(listing, "nope") is None

def test_missing_binary_returns_empty():
    env = {**os.environ, "SUPERLITE_CLAUDE_PROFILE_BIN": "/nonexistent/claude-profile"}
    assert ac.read_usage(env) == {} and ac.read_listing(env) == {}

def test_fake_binary_parsed_and_bad_json_empty(tmp_path):
    env = {**os.environ, "SUPERLITE_CLAUDE_PROFILE_BIN": str(FAKE), "FAKE_PROFILE_USAGE": json.dumps({"accounts": [acc("claude1", 1, weekly_all=5)]})}
    assert ac.read_usage(env)["accounts"][0]["name"] == "claude1"
    env["FAKE_PROFILE_USAGE"] = "not json"; assert ac.read_usage(env) == {}

def test_account_dir_path_entry_needs_no_listing(monkeypatch):
    monkeypatch.setenv("HOME", "/h")
    assert ac.account_dir({}, "/tmp/.claude-x") == "/tmp/.claude-x" and ac.account_dir({}, "~/.claude-y") == "/h/.claude-y"
    assert ac.entry_name("/tmp/.claude-x/") == ".claude-x" and ac.entry_name("claude1") == "claude1"
    assert ac.account_dir({}, "claude1") is None

def test_account_dir_reads_dir_field_of_claude_profile_schema_1():
    listing = {"schema_version": 1, "active": "claude2", "accounts": [
        {"name": "claude2", "n": 2, "dir": "/Users/max/.claude", "available": True, "active": True, "plan": "Ultra", "signed_in": True}]}
    assert ac.account_dir(listing, "claude2") == "/Users/max/.claude"

def test_default_dir_is_home_dot_claude_only():
    env = {"HOME": "/u"}
    assert ac.is_default_dir("/u/.claude", env) and ac.is_default_dir("/u/.claude/", env)
    assert not ac.is_default_dir("/u/.claude-account1", env) and not ac.is_default_dir("/v/.claude", env)

def test_current_without_config_dir_is_the_default_dir_of_that_env():
    assert ac.account_dir({}, "current", {"HOME": "/u"}) == "/u/.claude"
