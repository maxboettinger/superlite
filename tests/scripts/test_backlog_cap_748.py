import json
import stat
import sys

import pytest

from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import backlog_cap as bc  # noqa: E402
import herdr_client  # noqa: E402

D = bc.DEFAULTS
OK = ("ok", [])


def script(path, body):
    path.write_text("#!/usr/bin/env python3\n" + body)
    path.chmod(path.stat().st_mode | stat.S_IEXEC)
    return path


def machine(tmp_path, monkeypatch, obj):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path))
    (tmp_path / "machine.json").write_text(obj if isinstance(obj, str) else json.dumps(obj))
    return tmp_path


def room_script(tmp_path, body):
    return script(tmp_path / "room.py", body)


# ---- decide

def test_repo_bound_decides():
    assert bc.decide(0, {"room": 30, "unit": "cores"}, "", D, 0, OK, 0) == (
        6, "cap: 6 (6 per repository; room 30 cores, 2 per lead; accounts ok)")


def test_example_room_and_held():
    assert bc.decide(0, {"room": 12, "unit": "cores"}, "", D, 3, OK, 1) == (
        6, "cap: 6 (room 12 cores, 2 per lead; accounts ok; 1 held by overlap)")


def test_fixed_cap():
    assert bc.decide(0, None, "machine.json names no room command", D, None, OK, 0) == (
        2, "cap: 2 (fixed cap 2: machine.json names no room command; accounts ok)")


def test_machine_bound():
    assert bc.decide(1, {"room": 40, "unit": "cores"}, "", D, 11, OK, 0) == (
        2, "cap: 2 (11 of 12 leads on the machine; room 40 cores, 2 per lead; accounts ok)")


def test_no_account_usable():
    cfg = {**D, "lead_weekly_max": 90}
    acc = ("none", ["a1: weekly_all 95% >= lead_weekly_max 90%"])
    assert bc.decide(1, {"room": 12, "unit": "cores"}, "", cfg, 2, acc, 0) == (
        1, "cap: 1 (no account usable: a1: weekly_all 95% >= lead_weekly_max 90%; room 12 cores, 2 per lead)")


def test_room_zero_reason():
    r = {"room": 0, "unit": "cores", "reason": "two full suites run"}
    assert bc.decide(2, r, "", D, 4, OK, 0) == (2, "cap: 2 (room 0 cores: two full suites run; accounts ok)")


def test_accounts_unknown():
    cap, line = bc.decide(0, {"room": 12, "unit": "cores"}, "", D, None, ("unknown", []), 0)
    assert cap == 6 and "accounts unknown (no usage data)" in line


def test_reasons_capped_at_three():
    _, line = bc.decide(0, {"room": 12, "unit": "cores"}, "", D, None, ("none", ["r1", "r2", "r3", "r4", "r5"]), 0)
    assert "no account usable: r1, r2, r3 (+2 more)" in line and "r4" not in line


def test_cap_never_below_zero():
    assert bc.decide(3, {"room": 0, "unit": "c"}, "", {**D, "leads_per_repo": 1}, None, OK, 0)[0] == 1


# ---- machine_cfg

def test_invalid_cfg_note(tmp_path, monkeypatch):
    machine(tmp_path, monkeypatch, {"lead_units": 0})
    cfg = bc.machine_cfg(tmp_path)
    assert cfg["lead_units"] == 2 and cfg["_invalid"] == ["machine.json lead_units invalid, default 2"]


def test_lead_units_true_invalid(tmp_path, monkeypatch):
    machine(tmp_path, monkeypatch, {"lead_units": True})
    cfg = bc.machine_cfg(tmp_path)
    assert cfg["lead_units"] == 2 and len(cfg["_invalid"]) == 1


def test_cfg_valid_and_weekly_invalid(tmp_path, monkeypatch):
    machine(tmp_path, monkeypatch, {"leads_per_repo": 8, "lead_weekly_max": 101})
    cfg = bc.machine_cfg(tmp_path)
    assert cfg["leads_per_repo"] == 8 and cfg["lead_weekly_max"] is None
    assert cfg["_invalid"] == ["machine.json lead_weekly_max invalid, default none"]


def test_cfg_missing_file(tmp_path):
    assert bc.machine_cfg(tmp_path) == D


# ---- read_room why texts

def why_of(tmp_path, monkeypatch, obj, **kw):
    machine(tmp_path, monkeypatch, obj)
    return bc.read_room(tmp_path, **kw)


def test_room_ok(tmp_path, monkeypatch):
    s = room_script(tmp_path, 'print(\'{"room": 6, "unit": "cores"}\')')
    room, why = why_of(tmp_path, monkeypatch, {"room": [str(s)]})
    assert room == {"room": 6, "unit": "cores"} and why == ""


def test_room_missing_file(tmp_path):
    assert bc.read_room(tmp_path) == (None, "machine.json names no room command")


def test_room_missing_key(tmp_path, monkeypatch):
    assert why_of(tmp_path, monkeypatch, {})[1] == "machine.json names no room command"


def test_room_bad_json(tmp_path, monkeypatch):
    assert why_of(tmp_path, monkeypatch, "{")[1] == "machine.json unreadable"


def test_room_not_object(tmp_path, monkeypatch):
    assert why_of(tmp_path, monkeypatch, "[1]")[1] == "machine.json unreadable"


def test_room_not_argv(tmp_path, monkeypatch):
    assert why_of(tmp_path, monkeypatch, {"room": "x"})[1] == "machine.json room is not an argv list"


def test_room_missing_binary(tmp_path, monkeypatch):
    why = why_of(tmp_path, monkeypatch, {"room": [str(tmp_path / "nope")]})[1]
    assert why.startswith("room command did not run: ")


def test_room_exit_3(tmp_path, monkeypatch):
    s = room_script(tmp_path, "import sys\nsys.exit(3)")
    assert why_of(tmp_path, monkeypatch, {"room": [str(s)]})[1] == "room command exited 3"


def test_room_timeout(tmp_path, monkeypatch):
    s = room_script(tmp_path, "import time\ntime.sleep(5)")
    monkeypatch.setattr(bc, "ROOM_TIMEOUT", 0.3)
    assert why_of(tmp_path, monkeypatch, {"room": [str(s)]})[1] == "room command timed out after 0.3 s"


def test_room_timeout_text_default(tmp_path, monkeypatch):
    s = room_script(tmp_path, "import time\ntime.sleep(5)")
    assert why_of(tmp_path, monkeypatch, {"room": [str(s)]}, timeout=0.2)[1] == "room command timed out after 0.2 s"
    assert bc.ROOM_TIMEOUT == 20


@pytest.mark.parametrize("out,why", [
    ("[1]", "room command printed no JSON object"),
    ("nonsense", "room command printed no JSON object"),
    ('{"room": -1, "unit": "c"}', "room output: room must be an integer >= 0"),
    ('{"room": true, "unit": "c"}', "room output: room must be an integer >= 0"),
    ('{"room": 1}', "room output: unit must be a text"),
])
def test_room_output_why(tmp_path, monkeypatch, out, why):
    s = room_script(tmp_path, "print(%r)" % out)
    assert why_of(tmp_path, monkeypatch, {"room": [str(s)]}) == (None, why)


def test_room_reason_sanitised(tmp_path, monkeypatch):
    obj = {"room": 0, "unit": "c" * 100, "reason": "a\n" + "b" * 200}
    s = room_script(tmp_path, "import json\nprint(json.dumps(%r))" % obj)
    room, _ = why_of(tmp_path, monkeypatch, {"room": [str(s)]})
    assert "\n" not in room["reason"] and len(room["reason"]) == 80 and room["reason"].startswith("a b")
    assert len(room["unit"]) == 40


# ---- account_state

def profile(tmp_path, a2):
    usage = {"accounts": [
        {"name": "a1", "n": 1, "error": None, "limits": [{"kind": "weekly_all", "percent": 95}]},
        {"name": "a2", "n": 2, "error": None, "limits": [{"kind": "weekly_all", "percent": a2}]}]}
    return script(tmp_path / "cp.py", "import json, sys\nif sys.argv[1] == 'usage':\n    print(json.dumps(%r))\nelse:\n    print('{}')" % usage)


def test_account_state_weekly_max(tmp_path):
    env = {"SUPERLITE_CLAUDE_PROFILE_BIN": str(profile(tmp_path, 40))}
    assert bc.account_state(tmp_path, None, 90, env) == ("ok", [])
    env = {"SUPERLITE_CLAUDE_PROFILE_BIN": str(profile(tmp_path, 91))}
    state, why = bc.account_state(tmp_path, None, 90, env)
    assert state == "none" and len(why) == 2 and why[0] == "a1: weekly_all 95% >= lead_weekly_max 90%"


def test_account_state_no_weekly_max(tmp_path):
    env = {"SUPERLITE_CLAUDE_PROFILE_BIN": str(profile(tmp_path, 40))}
    assert bc.account_state(tmp_path, None, None, env) == ("ok", [])


def test_account_state_no_usage(tmp_path):
    s = script(tmp_path / "cp.py", "import sys\nsys.exit(1)")
    assert bc.account_state(tmp_path, None, None, {"SUPERLITE_CLAUDE_PROFILE_BIN": str(s)}) == ("unknown", [])


# ---- live_leads

def test_live_leads_counts_lead_names(monkeypatch):
    monkeypatch.setattr(herdr_client, "agents", lambda: [{"name": "sl-x-b1-lead"}, {"name": "sl-x-b1-w1"}, {"name": "other"}])
    assert bc.live_leads() == 1


def test_live_leads_herdr_error(monkeypatch):
    def boom():
        raise herdr_client.HerdrError("down", "no herdr")
    monkeypatch.setattr(herdr_client, "agents", boom)
    assert bc.live_leads() is None


# ---- lead_cap

def test_lead_cap_fixed(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_LEAD_CAP_LIVE", "1")
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(bc, "live_leads", lambda: None)
    env = {"SUPERLITE_CLAUDE_PROFILE_BIN": str(profile(tmp_path, 40))}
    assert bc.lead_cap({"batches": []}, tmp_path, env=env) == (
        2, "cap: 2 (fixed cap 2: machine.json names no room command; accounts ok)")


def test_lead_cap_room_held(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_LEAD_CAP_LIVE", "1")
    s = room_script(tmp_path, 'print(\'{"room": 12, "unit": "cores"}\')')
    machine(tmp_path, monkeypatch, {"room": [str(s)], "leads_per_repo": 8})
    monkeypatch.setattr(bc, "live_leads", lambda: None)
    env = {"SUPERLITE_CLAUDE_PROFILE_BIN": str(profile(tmp_path, 40))}
    data = {"batches": [{"id": "B1", "state": "running"}]}
    assert bc.lead_cap(data, tmp_path, held=1, env=env) == (
        7, "cap: 7 (room 12 cores, 2 per lead; accounts ok; 1 held by overlap)")


def test_lead_cap_invalid_note_in_line(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_LEAD_CAP_LIVE", "1")
    machine(tmp_path, monkeypatch, {"lead_units": 0})
    monkeypatch.setattr(bc, "live_leads", lambda: None)
    env = {"SUPERLITE_CLAUDE_PROFILE_BIN": str(profile(tmp_path, 40))}
    _, line = bc.lead_cap({"batches": []}, tmp_path, env=env)
    assert line.endswith("; machine.json lead_units invalid, default 2)")


def test_lead_cap_live_off_reads_nothing(tmp_path, monkeypatch):
    def boom(*a, **k):
        raise AssertionError("a live read ran")
    monkeypatch.setenv("SUPERLITE_LEAD_CAP_LIVE", "0")
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(bc, "account_state", boom)
    monkeypatch.setattr(bc, "live_leads", boom)
    assert bc.lead_cap({"batches": []}, tmp_path) == (
        2, "cap: 2 (fixed cap 2: machine.json names no room command; accounts unknown (no usage data))")


def test_decide_shows_invalid_notes():
    _, line = bc.decide(0, None, "x", {**D, "_invalid": ["machine.json a invalid, default 1", "machine.json b invalid, default 2"]}, None, OK, 0)
    assert line.endswith("; machine.json a invalid, default 1; machine.json b invalid, default 2)")
