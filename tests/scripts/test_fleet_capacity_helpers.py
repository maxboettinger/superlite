# tests/scripts/test_fleet_capacity_helpers.py
import sys
from test_accounts import acc
from test_herdr_client import fake  # noqa: F401  (fixture)
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import accounts as ac  # noqa: E402
import fleet_state as fs  # noqa: E402
import herdr_client as hc  # noqa: E402

LISTING = {"accounts": [{"name": "claude1", "dir": "/u/.claude-account1"}, {"name": "claude3", "dir": "/u/.claude-account3"}]}

def pane(i, rows, cols=73):
    return {"pane_id": f"w6:p{i}", "rows": rows, "cols": cols}

def row(name, i=1):
    return {"name": name, "agent_status": "working", "cwd": "/u/x", "pane_id": f"w9:p{i}"}

def test_place_examples():
    assert fs.place([pane(1, 64, 147)]) == ("right", "w6:p1")
    assert fs.place([pane(1, 64), pane(2, 64)]) == ("down", "w6:p1")
    assert fs.place([pane(1, 32), pane(2, 64), pane(3, 32)]) == ("down", "w6:p2")
    assert fs.place([pane(i, 32) for i in (1, 2, 3, 4)]) == ("tab", None)
    assert fs.place([]) == ("tab", None)

def test_place_down_split_under_20_rows_opens_tab():
    assert fs.place([pane(1, 39), pane(2, 39)]) == ("tab", None)
    assert fs.place([pane(1, 40), pane(2, 39)]) == ("down", "w6:p1")

def test_live_by_account_counts_other_sessions():
    for name, account in (("sl-main-1a2b-w2", "claude3"), ("sl-dashmax-3c4d-w31", "claude3"),
                          ("sl-other-5e6f-w1", "current"), ("sl-proj-7a8b-w1", "claude1")):
        fs.register_agent(name, account)
    names = ("sl-main-1a2b-w2", "sl-dashmax-3c4d-w31", "sl-other-5e6f-w1", "sl-proj-7a8b-w1", "sl-gone-0000-w1", "reviewer")
    assert fs.live_by_account([row(n, i) for i, n in enumerate(names)], {"sl-proj-7a8b-w1"}) == {"claude3": 2}

def test_register_agent_overwrites_under_superlite_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "h"))
    fs.register_agent("sl-a-0000-w1", "claude1"); fs.register_agent("sl-a-0000-w1", "claude2")
    assert (tmp_path / "h" / "fleet" / "agents" / "sl-a-0000-w1").read_text().strip() == "claude2"
    assert fs.live_by_account([row("sl-a-0000-w1")], set()) == {"claude2": 1}

def test_aliases_match_config_dirs():
    entries = ["current", "/u/.claude-account1/", "/u/.claude-x", "claude3"]
    assert ac.aliases(LISTING, entries, {"CLAUDE_CONFIG_DIR": "/u/.claude-account1"}) == {"current": "claude1", ".claude-account1": "claude1"}
    assert ac.aliases({}, ["current"], {"CLAUDE_CONFIG_DIR": "/u/.claude-account1"}) == {}

def test_capped_alias_is_refused_with_reason():
    usage = {"accounts": [acc("claude1", 1, session=95, weekly_all=10)]}
    assert ac.pick_account(usage, ["current"], {}, "sonnet", {"current": "claude1"}) is None
    assert ac.reasons(usage, ["current"], "sonnet", {"current": "claude1"}) == ["current: 5-hour 95%"]
    weekly = {"accounts": [acc("claude1", 1, weekly_all=100)]}
    assert ac.reasons(weekly, [".claude-account1"], "sonnet", {".claude-account1": "claude1"}) == [".claude-account1: weekly_all 100%"]

def test_alias_with_headroom_is_picked():
    usage = {"accounts": [acc("claude1", 1, weekly_all=10)]}
    assert ac.pick_account(usage, ["current"], {}, "sonnet", {"current": "claude1"}) == "current"
    assert ac.pick_account(usage, ["current"]) is None   # no alias: no usage data, as before

def test_create_tab_flags_and_ids(fake):
    assert hc.create_tab("w6", "/proj", {"SUPERLITE_FLEET_WORKER": "W5"}) == ("w6:t2", "w6:p5")
    argv = fake()[0]
    assert argv[:4] == ["tab", "create", "--workspace", "w6"] and "SUPERLITE_FLEET_WORKER=W5" in argv and "--no-focus" in argv

def test_pane_layout_reads_rects(fake):
    assert hc.pane_layout("w6:p1") == [{"pane_id": "w6:p1", "rows": 64, "cols": 73}, {"pane_id": "w6:p2", "rows": 64, "cols": 73}]
    assert fake()[0] == ["pane", "layout", "--pane", "w6:p1"]

def test_agents_lists_named_agents_with_cwd(fake):
    assert [(a["name"], a["cwd"]) for a in hc.agents()] == [("sl-proj-w1", "/u/proj"), ("sl-proj-w2", "/u/proj")]
