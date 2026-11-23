# tests/scripts/test_fleet.py
import json, os, sys, types
from pathlib import Path
import pytest
from _fixtures import FIXTURES
from test_accounts import LIMIT_KEYS, acc, lim
from test_plan_tools import SCRIPTS, make_plan
sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
REAL = os.environ.get("SUPERLITE_REAL") == "1"

class FakeHerdr:
    """Swappable fake of herdr_client: records calls, scripted failures. The seam check (SUPERLITE_REAL=1) runs the real module against the fake binary of T3."""
    def __init__(self):
        self.calls, self.start_error, self.screen, self.prompt_state = [], None, "READY\n", "done"
        self.screen_after = None
        self.create_error = None
        self.split_error = None
        self.gone, self.state_error = set(), None  # agent names that no longer exist; a scripted agent_state failure code
        self.layout, self.agent_rows, self.tab_panes = None, [], []  # scripted pane_layout and agents replies; panes of the newest tab
        self.HerdrError = type("HerdrError", (Exception,), {"__init__": lambda s, code, message="": (setattr(s, "code", code), setattr(s, "message", message), None)[-1]})
    def create_workspace(self, label, cwd, env_vars):
        if self.create_error: raise self.HerdrError(self.create_error, "missing")
        self.calls.append(("create_workspace", label, env_vars)); self.tab_panes = ["w6:p1"]; return ("w6", "w6:p1")
    def split_pane(self, pane_id, direction, cwd, env_vars):
        self.calls.append(("split_pane", pane_id, direction))
        if self.split_error: e, self.split_error = self.split_error, None; raise self.HerdrError(e, "pane gone")
        pane = f"w6:p{len(self.calls) + 1}"; self.tab_panes.append(pane); return pane
    def create_tab(self, workspace_id, cwd, env_vars):
        self.calls.append(("create_tab", workspace_id)); pane = f"w6:p{len(self.calls) + 1}"; self.tab_panes = [pane]
        return (f"w6:t{len(self.calls)}", pane)
    def pane_layout(self, pane_id):
        self.calls.append(("pane_layout", pane_id))
        return self.layout if self.layout is not None else [{"pane_id": p, "rows": 64, "cols": 73} for p in self.tab_panes]
    def agent_state(self, name):  # a read, not logged
        if name in self.gone: raise self.HerdrError("agent_not_found", "agent target not found")
        if self.state_error: raise self.HerdrError(self.state_error, "x")
        return "idle"
    def agents(self): return list(self.agent_rows)  # a read, not logged: the call-order tests stay as they are
    def start_agent(self, name, pane_id, argv, timeout_ms=90000):
        self.calls.append(("start_agent", name, argv))
        if self.start_error: e, self.start_error = self.start_error, None; raise self.HerdrError(e, "blocked during startup")
        return "idle"
    def read_screen(self, name, lines=40, source="visible"):
        self.calls.append(("read_screen", name))
        if self.screen_after is not None and any(c[0] == "send_keys" for c in self.calls): return self.screen_after
        return "\n".join(self.screen.splitlines()[-lines:]) + "\n"  # like herdr: the bottom `lines` rows of the pane
    def prompt(self, name, text, until, timeout_ms): self.calls.append(("prompt", name, text)); return self.prompt_state
    def send_keys(self, name, keys): self.calls.append(("send_keys", name, keys))
    def wait_state(self, name, until, timeout_ms): self.calls.append(("wait_state", name, until)); return "idle"
    def exit_agent(self, name, slash=False): self.calls.append(("exit_agent", name))
    def close_pane(self, pane_id):
        self.calls.append(("close_pane", pane_id))
        if pane_id in self.tab_panes: self.tab_panes.remove(pane_id)
    def close_workspace(self, ws): self.calls.append(("close_workspace", ws))
    def on(self, machine):
        import contextlib
        @contextlib.contextmanager
        def cm():
            if machine: self.calls.append(("on", machine))
            try: yield
            finally:
                if machine: self.calls.append(("off", machine))
        return cm()
    def machines(self): return [{"label": "box"}]
    def machine_status(self, label, timeout_ms=10000): return "reachable"
    def call(self, args, timeout_ms=30000, env=None): self.calls.append(("call", args)); return {}  # pane rename

@pytest.fixture
def world(tmp_path, monkeypatch):
    proj = tmp_path / "proj"; (proj / ".superlite").mkdir(parents=True); sd = proj / ".superlite"
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
    monkeypatch.delenv("GH_CONFIG_DIR", raising=False)
    (sd / "prime.md").write_text("rules\nReply READY\n"); (sd / "prime-haiku.md").write_text("mini\nReply READY\n")
    plan = make_plan(proj, [{"id": "T1", "owns": "src/a.py"}])
    fh = FakeHerdr()
    if not REAL:
        monkeypatch.setattr(fleet, "hc", fh)
    else:
        fake_bin = FIXTURES / "fleet" / "herdr"
        monkeypatch.setenv("SUPERLITE_HERDR_BIN", str(fake_bin)); monkeypatch.setenv("FAKE_HERDR_LOG", str(tmp_path / "h.log"))
    usage = {"accounts": [acc("claude1", 1, weekly_all=64), acc("claude3", 3, weekly_all=3)]}
    listing = {"accounts": [{"name": "claude1", "dir": "/u/.claude-account1"}, {"name": "claude3", "dir": "/u/.claude-account3"}]}
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: usage); monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: listing)
    monkeypatch.chdir(proj)
    return types.SimpleNamespace(proj=proj, sd=sd, plan=plan, fh=fh, usage=usage)

def test_spawn_records_launch_pool_and_state(world, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert r["id"] == "W1" and r["account"] == "claude3" and r["pane_id"] == "w6:p1"
    assert "W1 account=claude3 pane=w6:p1 agent=superlite:implementer" in capsys.readouterr().out
    launch = [json.loads(l) for l in (world.sd / "metrics.jsonl").read_text().splitlines()][0]
    assert launch["ev"] == "launch" and launch["agent_id"] == "W1" and launch["type"] == "fleet:superlite:implementer"
    pool = json.loads((world.sd / "pool.json").read_text())["agents"][0]
    assert (pool["id"], pool["backend"], pool["account"], pool["tier"]) == ("W1", "herdr", "claude3", "sonnet")
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "ready"

def test_worker_env_contents(world):
    env = fleet.worker_env(world.sd, "W1", "superlite:implementer", "/u/.claude-account3", {"CLAUDE_CODE_PLUGIN_CACHE_DIR": "/u/.claude/plugins", "HOME": "/u"})
    assert env == {"CLAUDE_CONFIG_DIR": "/u/.claude-account3", "SUPERLITE_FLEET_WORKER": "W1", "SUPERLITE_FLEET_AGENT": "superlite:implementer",
                   "SUPERLITE_STATE_DIR": str(world.sd.resolve()), "SUPERLITE_FINAL_REVIEW": "off", "CLAUDE_CODE_PLUGIN_CACHE_DIR": "/u/.claude/plugins"}

def test_gh_config_dir_reaches_workers_and_leads_only_when_set(world, tmp_path):
    """A sealed golden run sets GH_CONFIG_DIR to an empty folder: herdr's explicit --env list must carry it to the lead and its workers."""
    import fleet_lead
    m, l = tmp_path / "m", tmp_path / "wt"
    for base, want in (({"HOME": "/u", "GH_CONFIG_DIR": "/empty"}, {"GH_CONFIG_DIR": "/empty"}), ({"HOME": "/u"}, {})):
        w = fleet.worker_env(world.sd, "W1", "superlite:implementer", "/u/.claude", base)
        ld = fleet_lead.lead_env(m, l, "W2", "/u/.claude", base, [])
        assert {k: v for k, v in w.items() if k == "GH_CONFIG_DIR"} == want
        assert {k: v for k, v in ld.items() if k == "GH_CONFIG_DIR"} == want

def _spawn_env(world, monkeypatch, accounts, env):
    seen = {}
    real = fleet.worker_env
    monkeypatch.setattr(fleet, "worker_env", lambda *a: seen.setdefault("env", real(*a)))
    fleet.main(["on"] + (["--accounts", accounts] if accounts else [])); fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env=env)
    return seen["env"]

def test_current_account_on_the_default_dir_leaves_config_dir_unset(world, monkeypatch):
    """CLAUDE_CONFIG_DIR=~/.claude makes Claude Code start first-run onboarding; the default dir is chosen by not setting it."""
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: {}); monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: {})
    assert "CLAUDE_CONFIG_DIR" not in _spawn_env(world, monkeypatch, "", {"HOME": "/u"})

def test_current_account_keeps_the_coordinators_config_dir(world, monkeypatch):
    assert _spawn_env(world, monkeypatch, "current", {"HOME": "/u", "CLAUDE_CONFIG_DIR": "/u/.claude-account1"})["CLAUDE_CONFIG_DIR"] == "/u/.claude-account1"

def test_named_account_on_the_default_dir_leaves_config_dir_unset(world, monkeypatch):
    monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: {"accounts": [{"name": "claude3", "dir": "/u/.claude"}]})
    assert "CLAUDE_CONFIG_DIR" not in _spawn_env(world, monkeypatch, "claude3", {"HOME": "/u"})

@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_spawn_accepts_trust_dialog(world):
    fleet.main(["on"]); world.fh.start_error = "agent_not_ready"; world.fh.screen = "Quick safety check\n > No, exit\n   Yes, I trust this folder\n"
    world.fh.screen_after = "READY"
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    names = [c[0] for c in world.fh.calls]
    assert names[:5] == ["create_workspace", "start_agent", "read_screen", "send_keys", "wait_state"] and r["id"] == "W1"
    assert ("send_keys", fleet.fs.agent_name(world.sd, "W1"), ["Down", "Enter"]) in world.fh.calls

@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_spawn_login_screen_is_blocked(world, capsys):
    fleet.main(["on"]); world.fh.start_error = "agent_not_ready"; world.fh.screen = "Select login method\n"
    with pytest.raises(SystemExit) as e: fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and capsys.readouterr().out.startswith("BLOCKED: W1 account claude3")
    assert ("close_pane", "w6:p1") in world.fh.calls and not any(c[0] == "send_keys" for c in world.fh.calls)
    assert (world.sd / "fleet" / "screens" / "W1.txt").read_text().startswith("Select login")

@pytest.mark.skipif(REAL, reason="scripted screen needs the in-process fake")
def test_spawn_without_ready_is_blocked(world, capsys):
    fleet.main(["on"]); world.fh.screen = "something else\n"
    with pytest.raises(SystemExit) as e: fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and "no READY" in capsys.readouterr().out
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "blocked"

@pytest.mark.skipif(REAL, reason="call order is read from the in-process fake")
def test_second_spawn_splits_right_then_down(world):
    fleet.main(["on"])
    for _ in range(3): fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    splits = [c for c in world.fh.calls if c[0] == "split_pane"]
    assert [s[1:] for s in splits] == [("w6:p1", "right"), ("w6:p1", "down")]
    assert json.loads((world.sd / "fleet.json").read_text())["workspace_id"] == "w6"

@pytest.mark.skipif(REAL, reason="argv is read from the in-process fake")
def test_haiku_tier_uses_haiku_agent_and_prime(world):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "haiku", world.proj)
    start = next(c for c in world.fh.calls if c[0] == "start_agent"); prompt = next(c for c in world.fh.calls if c[0] == "prompt")
    assert "--agent" in start[2] and start[2][start[2].index("--agent") + 1] == "superlite:implementer-haiku" and "haiku" in start[2]
    assert "--disallowedTools" in start[2] and "prime-haiku.md" in prompt[2]

def test_no_account_is_blocked_exit_3(world, monkeypatch, capsys):
    fleet.main(["on", "--accounts", "claude1"])
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: {"accounts": [acc("claude1", 1, session=99)]})
    with pytest.raises(SystemExit) as e: fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and "BLOCKED: no account with headroom" in capsys.readouterr().out and not world.fh.calls

@pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")
def test_stop_all_closes_everything(world, capsys):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert fleet.stop(world.sd, all_=True) == ["W1", "W2"]
    kinds = [c[0] for c in world.fh.calls]; assert kinds.count("close_pane") == 2 and kinds.count("exit_agent") == 2 and kinds[-1] == "close_workspace"
    data = json.loads((world.sd / "fleet.json").read_text())
    assert all(w["state"] == "stopped" for w in data["workers"].values()) and data["workspace_id"] is None
    assert json.loads((world.sd / "pool.json").read_text())["agents"] == []

def test_on_off_status(world, capsys):
    assert fleet.main(["status"]) == 0 and "fleet: off" in capsys.readouterr().out
    fleet.main(["on", "--accounts", "claude1,claude3"]); assert json.loads((world.sd / "fleet.json").read_text())["accounts"] == ["claude1", "claude3"]
    fleet.main(["status"]); assert "fleet: on" in capsys.readouterr().out
    fleet.main(["off"]); assert not (world.sd / "fleet.json").exists()

def test_on_uses_env_accounts(world, monkeypatch):
    monkeypatch.setenv("SUPERLITE_FLEET_ACCOUNTS", "claude1, claude3")
    fleet.main(["on"]); assert json.loads((world.sd / "fleet.json").read_text())["accounts"] == ["claude1", "claude3"]
    fleet.main(["on", "--accounts", "claude2"]); assert json.loads((world.sd / "fleet.json").read_text())["accounts"] == ["claude2"]

@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_prime_error_is_blocked_not_traceback(world, capsys):
    fleet.main(["on"])
    def boom(*a, **k): raise world.fh.HerdrError("agent_prompt_stalled", "stalled")
    world.fh.prompt = boom
    with pytest.raises(SystemExit) as e: fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and "BLOCKED: W2" in capsys.readouterr().out and ("close_pane", "w6:p1") in world.fh.calls
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "blocked"

@pytest.mark.skipif(REAL, reason="argv is read from the in-process fake")
def test_prime_timeout_and_launch_desc(world):
    fleet.main(["on"]); seen = []
    orig = world.fh.prompt
    world.fh.prompt = lambda n, t, u, ms: (seen.append(ms), orig(n, t, u, ms))[1]
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert seen == [180000]
    launch = json.loads((world.sd / "metrics.jsonl").read_text().splitlines()[0])
    assert launch["desc"] == "fleet worker claude3 pane w6:p1"


@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_spawn_herdr_missing_is_blocked(world, capsys):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    world.fh.create_error = "missing"
    with pytest.raises(SystemExit) as ei:
        fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert ei.value.code == 3
    assert capsys.readouterr().out.startswith("BLOCKED:")

@pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")
def test_spawn_after_stop_w1_splits_live_pane(world):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    w2 = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    fleet.stop(world.sd, ["W1"])
    world.fh.calls.clear()
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    splits = [c for c in world.fh.calls if c[0] == "split_pane"]
    assert splits and splits[0][1] == w2["pane_id"] and splits[0][1] != "w6:p1"


@pytest.mark.skipif(REAL, reason="call order is read from the in-process fake")
def test_parallel_spawns_create_one_workspace(world):
    import threading
    fleet.main(["on"])
    ids, errs = [], []
    def go():
        try: ids.append(fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"])
        except BaseException as e: errs.append(e)
    ts = [threading.Thread(target=go) for _ in range(2)]
    for t in ts: t.start()
    for t in ts: t.join()
    assert not errs and len(set(ids)) == 2
    names = [c[0] for c in list(world.fh.calls)]
    assert names.count("create_workspace") == 1 and names.count("split_pane") == 1
    assert set(json.loads((world.sd / "fleet.json").read_text())["workers"]) == set(ids)
    assert {a["id"] for a in json.loads((world.sd / "pool.json").read_text())["agents"]} == set(ids)


@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_dead_source_pane_is_stopped_and_spawn_retries(world):
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj); w2 = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    world.fh.calls.clear(); world.fh.split_error = "pane_not_found"
    w3 = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    splits = [c for c in world.fh.calls if c[0] == "split_pane"]
    assert [s[1] for s in splits] == ["w6:p1", w2["pane_id"]]
    workers = json.loads((world.sd / "fleet.json").read_text())["workers"]
    assert workers["W1"]["state"] == "stopped" and workers["W2"]["state"] == "ready" and workers[w3["id"]]["state"] == "ready"
    assert {a["id"] for a in json.loads((world.sd / "pool.json").read_text())["agents"]} == {"W2", "W3"}

@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_dead_only_pane_recreates_workspace(world):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    world.fh.split_error = "pane_not_found"
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert [c[0] for c in world.fh.calls].count("create_workspace") == 2 and r["id"] == "W2"
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["state"] == "stopped"

@pytest.mark.skipif(REAL, reason="scripted screen needs the in-process fake")
def test_echoed_prime_prompt_is_not_ready(world, capsys):
    fleet.main(["on"]); world.fh.screen = "❯ Read /x/.superlite/prime.md, then reply READY\n"
    with pytest.raises(SystemExit) as e: fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and "no READY" in capsys.readouterr().out

@pytest.mark.skipif(REAL, reason="scripted screen needs the in-process fake")
def test_echoed_prompt_plus_answer_is_ready(world):
    fleet.main(["on"]); world.fh.screen = "❯ Read /x/.superlite/prime.md, then reply READY\n\n⏺ READY\n"
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"

def _no_profile(world, monkeypatch):
    monkeypatch.setenv("SUPERLITE_CLAUDE_PROFILE_BIN", "/nonexistent/claude-profile")
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: fleet.ac._run("usage", env)); monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: fleet.ac._run("list", env))

def test_path_account_works_without_claude_profile(world, monkeypatch, capsys):
    _no_profile(world, monkeypatch)
    fleet.main(["on", "--accounts", "/tmp/.claude-x"]); assert "warning" not in capsys.readouterr().err
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert r["account"] == ".claude-x" and "account=.claude-x" in capsys.readouterr().out

def test_named_account_without_claude_profile_is_blocked(world, monkeypatch, capsys):
    _no_profile(world, monkeypatch)
    fleet.main(["on", "--accounts", "claude1"]); assert "claude-profile list unavailable" in capsys.readouterr().err
    with pytest.raises(SystemExit) as e: fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert e.value.code == 3 and "BLOCKED: no config dir for account claude1 (claude-profile list unavailable; pass a config dir path instead)" in capsys.readouterr().out

def test_current_account_spawns_although_usage_lists_other_accounts(world, capsys):
    fleet.main(["on", "--accounts", "current"])
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env={"CLAUDE_CONFIG_DIR": "/u/.claude-cur"})
    assert r["account"] == "current" and "W1 account=current" in capsys.readouterr().out

def test_current_is_the_fallback_when_named_accounts_have_no_headroom(world, monkeypatch):
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: {"accounts": [acc("claude1", 1, weekly_all=100)]})
    fleet.main(["on", "--accounts", "claude1,current"])
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env={"CLAUDE_CONFIG_DIR": "/u/.claude-cur"})["account"] == "current"

@pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")
def test_spawn_and_stop_address_herdr_by_one_valid_agent_name(world):
    fleet.main(["on"]); world.fh.start_error = "agent_not_ready"; world.fh.screen = "Yes, I trust this folder\n"; world.fh.screen_after = "READY"
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"
    fleet.stop(world.sd, ["W1"])
    by_name = ("start_agent", "read_screen", "send_keys", "wait_state", "prompt", "exit_agent")
    assert {c[0] for c in world.fh.calls if c[0] in by_name} == set(by_name)
    assert {c[1] for c in world.fh.calls if c[0] in by_name} == {fleet.fs.agent_name(world.sd, "W1")}
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["name"] == fleet.fs.agent_name(world.sd, "W1")

@pytest.mark.skipif(REAL, reason="scripted screen needs the in-process fake")
def test_ready_at_the_top_of_a_tall_fullscreen_pane_is_seen(world):
    fleet.main(["on"]); world.fh.screen = "❯ Read /x/.superlite/prime.md, then reply READY\n\n⏺ READY\n" + "\n" * 62 + "❯\n  ⏵⏵ auto mode on\n"
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"

@pytest.mark.skipif(REAL, reason="scripted failure needs the in-process fake")
def test_trust_dialog_at_the_top_of_a_tall_pane_is_accepted(world):
    fleet.main(["on"]); world.fh.start_error = "agent_not_ready"; world.fh.screen = "Yes, I trust this folder\n" + "\n" * 70; world.fh.screen_after = "READY"
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1"

@pytest.mark.skipif(REAL, reason="argv is read from the in-process fake")
def test_prime_prompt_also_settles_on_idle(world):
    """A pane the user is looking at settles as `idle`, never `done` (herdr 0.9.5)."""
    fleet.main(["on"]); seen = []; world.fh.prompt_state = "idle"
    orig = world.fh.prompt
    world.fh.prompt = lambda n, t, u, ms: (seen.append(u), orig(n, t, u, ms))[1]
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["id"] == "W1" and set(seen[0]) == {"idle", "done", "blocked"}

@pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")
def test_stop_handles_a_worker_record_written_before_names_were_stored(world):
    """A fleet.json of 1.5.0 holds blocked workers without `name`; `fleet stop --all` and `fleet off` must still close them."""
    fleet.main(["on"])
    data = json.loads((world.sd / "fleet.json").read_text())
    data["workers"]["W1"] = {"pane_id": "w6:p1", "account": "claude3", "agent": "superlite:implementer", "tier": "sonnet", "state": "blocked", "task": None}
    (world.sd / "fleet.json").write_text(json.dumps(data))
    assert fleet.stop(world.sd, all_=True) == ["W1"] and ("exit_agent", fleet.fs.agent_name(world.sd, "W1")) in world.fh.calls


def _three_accounts(world, monkeypatch):
    usage = {"accounts": [acc("claude1", 1, weekly_all=10), acc("claude2", 2, weekly_all=30), acc("claude3", 3, weekly_all=20)]}
    listing = {"accounts": [{"name": f"claude{i}", "dir": f"/u/.claude-account{i}"} for i in (1, 2, 3)]}
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: usage); monkeypatch.setattr(fleet.ac, "read_listing", lambda env=None: listing)

def _accounts_in_fleet_json(world):
    return {k: v["account"] for k, v in json.loads((world.sd / "fleet.json").read_text())["workers"].items()}

def test_three_spawns_spread(world, monkeypatch):
    _three_accounts(world, monkeypatch)
    fleet.main(["on"])
    for _ in range(3): fleet.main(["spawn", "--tier", "sonnet"])
    assert _accounts_in_fleet_json(world) == {"W1": "claude1", "W2": "claude3", "W3": "claude2"}

def test_stopped_worker_frees_account(world, monkeypatch):
    _three_accounts(world, monkeypatch)
    fleet.main(["on", "--accounts", "claude1,claude2"])
    assert [fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] for _ in range(2)] == ["claude1", "claude2"]
    fleet.stop(world.sd, ["W2"])  # claude2 now runs nothing; counting the stopped worker would tie 1:1 and pick claude1 by its lower weekly
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] == "claude2"

def test_blocked_worker_holds_no_account(world, monkeypatch):
    _three_accounts(world, monkeypatch)
    fleet.main(["on", "--accounts", "claude1,claude2"])
    data = json.loads((world.sd / "fleet.json").read_text())
    data["workers"]["W1"] = {"name": "sl-proj-w1", "pane_id": "w6:p1", "account": "claude1", "agent": "superlite:implementer", "tier": "sonnet", "state": "blocked", "task": None}
    data["next"] = 2; (world.sd / "fleet.json").write_text(json.dumps(data))
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] == "claude1"

def test_spawn_passes_its_tier_to_the_account_choice(world, monkeypatch):
    seen = []
    real = fleet.ac.pick_account
    monkeypatch.setattr(fleet.ac, "pick_account", lambda usage, allowed, running=None, tier=None, alias=None: (seen.append((dict(running or {}), tier)), real(usage, allowed, running, tier, alias))[1])
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "haiku", world.proj); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert seen == [({}, "haiku"), ({"claude3": 1}, "sonnet")]

def test_scoped_limit_of_the_workers_model_blocks_the_account(world, monkeypatch, capsys):
    usage = {"accounts": [acc("claude1", 1, lim("weekly_scoped", 70, "Sonnet", 70), weekly_all=1), acc("claude3", 3, weekly_all=50)]}
    monkeypatch.setattr(fleet.ac, "read_usage", lambda env=None: usage)
    fleet.main(["on"])
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj)["account"] == "claude3"
    assert fleet.spawn(world.sd, world.plan, "haiku", world.proj)["account"] == "claude1"

def test_fixtures_use_real_shape(world):
    limits = [l for a in world.usage["accounts"] for l in a["limits"]]
    assert limits and all(set(l) == LIMIT_KEYS for l in limits)

def test_status_hides_stopped_rows(world, capsys):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    data = json.loads((world.sd / "fleet.json").read_text())
    data["workers"]["W3"] = {"name": "sl-proj-w3", "pane_id": "w6:p9", "account": "claude1", "agent": "superlite:implementer", "tier": "sonnet", "state": "blocked", "task": None}
    (world.sd / "fleet.json").write_text(json.dumps(data))
    fleet.stop(world.sd, ["W1"]); capsys.readouterr()
    fleet.main(["status"]); out = capsys.readouterr().out
    assert "fleet: on" in out and "W2 ready" in out and "W1" not in out and "W3" not in out
    fleet.main(["status", "--all"]); out = capsys.readouterr().out
    assert "W1 stopped" in out and "W2 ready" in out and "W3 blocked" in out


# --- remote workers (#919) ---
def _remote_rec(machine, pane, state="ready"):
    return {"name": "sl-proj-w", "state": state, "pane_id": pane, "machine": machine, "role": "research", "account": f"default@{machine}"}

@pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")
def test_open_pane_machine_workspace_is_its_own(world):
    r1 = fleet.open_pane(world.sd, "W1", "/h/t", {}, _remote_rec("box", None), machine="box")
    assert r1 == "w6:p1"
    data = json.loads((world.sd / "fleet.json").read_text())
    assert data["machines"] == {"box": {"workspace_id": "w6", "root_pane": "w6:p1"}} and data["workspace_id"] is None
    assert world.fh.calls[0] == ("on", "box") and ("create_workspace", "sl:fleet", {}) in world.fh.calls and world.fh.calls[-1] == ("off", "box")

@pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")
def test_open_pane_splits_only_from_same_machine(world):
    fleet.open_pane(world.sd, "W1", "/h/t", {}, _remote_rec("box", None), machine="box")
    fleet.open_pane(world.sd, "W2", "/p", {}, {"name": "sl-proj-w2", "state": "ready", "role": "implementer"})  # local: own workspace
    splits = [c for c in world.fh.calls if c[0] == "split_pane"]
    assert splits == [] and [c[0] for c in world.fh.calls].count("create_workspace") == 2
    fleet.open_pane(world.sd, "W3", "/h/t", {}, _remote_rec("box", None), machine="box")
    assert [c for c in world.fh.calls if c[0] == "split_pane"][0][1] == "w6:p1"

def test_spawn_machine_hands_off(world, monkeypatch):
    import fleet_remote_worker as frw
    seen = []
    monkeypatch.setattr(frw, "spawn", lambda *a: seen.append(a) or {"id": "W1"})
    monkeypatch.setattr(fleet.ml, "gate", lambda *a, **k: pytest.fail("local machine gate ran"))
    assert fleet.spawn(world.sd, world.plan, "sonnet", world.proj, role="research", machine="box") == {"id": "W1"}
    assert seen == [(world.sd, "research", "sonnet", world.proj, "box", None)]

def test_status_does_not_probe_remote_worker(world, monkeypatch, capsys):
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    data = json.loads((world.sd / "fleet.json").read_text())
    data["workers"]["W7"] = _remote_rec("box", "w9:p9")
    (world.sd / "fleet.json").write_text(json.dumps(data)); capsys.readouterr()
    probed = []
    monkeypatch.setattr(fleet, "agent_gone", lambda name: probed.append(name) or True)
    fleet.main(["status"]); out = capsys.readouterr().out
    assert "W7 ready" in out and "dead: W7" not in out and "sl-proj-w" not in probed
    assert "dead: W1" in out and len(probed) == 1

@pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")
def test_stop_remote_worker(world, monkeypatch):
    import fleet_remote_worker as frw
    fleet.main(["on"]); fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    d = json.loads((world.sd / "fleet.json").read_text()); d["workers"]["W2"] = _remote_rec("box", "w6:p9"); d["next"] = 3
    d["machines"] = {"box": {"workspace_id": "w9", "root_pane": "w9:p1"}}; (world.sd / "fleet.json").write_text(json.dumps(d))
    stopped = []
    monkeypatch.setattr(frw, "stop", lambda sd, wid: (stopped.append(wid), fleet.fs.set_state(sd, wid, "stopped")))
    assert fleet.stop(world.sd, ["W2"]) == ["W2"] and stopped == ["W2"]
    assert not any(c[0] == "exit_agent" for c in world.fh.calls)
    fleet.stop(world.sd, ["W1"])
    assert [c[0] for c in world.fh.calls].count("exit_agent") == 1 and stopped == ["W2"]

@pytest.mark.skipif(REAL, reason="call list is read from the in-process fake")
def test_last_remote_stop_closes_its_workspace(world, monkeypatch):
    import fleet_remote_worker as frw
    d = fleet.fs.default(); d["workers"] = {"W1": _remote_rec("box", "w9:p1"), "W2": _remote_rec("box", "w9:p2")}
    d["machines"] = {"box": {"workspace_id": "w9", "root_pane": "w9:p1"}}; fleet.fs.save(world.sd, d)
    monkeypatch.setattr(frw, "stop", lambda sd, wid: fleet.fs.set_state(sd, wid, "stopped"))
    fleet.stop(world.sd, ["W1"])
    assert not any(c[0] == "close_workspace" for c in world.fh.calls)
    fleet.stop(world.sd, ["W2"])
    assert ("close_workspace", "w9") in world.fh.calls and ("on", "box") in world.fh.calls
    assert json.loads((world.sd / "fleet.json").read_text())["machines"] == {}

def test_cli_machine_needs_supported_spawn(world, capsys):
    fleet.main(["on"])
    assert fleet.main(["spawn", "--package", "X", "--machine", "box"]) == 2
    assert "--machine works with --for-dispatch, --for-review Tn or a plain spawn (--role R --brief F)" in capsys.readouterr().err
    assert fleet.main(["spawn", "--role", "research", "--machine", "box"]) == 2

def test_cli_machine_passed_to_spawn(world, monkeypatch):
    seen = {}; fleet.main(["on"])
    monkeypatch.setattr(fleet, "spawn", lambda *a, **k: seen.update(k) or (_ for _ in ()).throw(ValueError("stop here")))
    brief = world.proj / "b.md"; brief.write_text("q")
    assert fleet.main(["spawn", "--role", "research", "--brief", str(brief), "--machine", "box"]) == 2
    assert seen["machine"] == "box"


@pytest.fixture
def rdisp(world, monkeypatch, capsys):
    """Remote dispatch: scripted dispatch lines, fleet_remote_worker.spawn/send_task record their calls."""
    import dispatch, fleet_remote_worker as frw
    fleet.main(["on"]); capsys.readouterr()
    plan = make_plan(world.proj, [{"id": t, "owns": f"src/{t.lower()}.py"} for t in ("T1", "T2", "T3")], name="plan2.md")
    r = types.SimpleNamespace(**vars(world), plan2=plan, lines=[], spawns=[], sends=[], n=[0])
    monkeypatch.setattr(dispatch, "run", lambda *a, **k: (list(r.lines), {}))
    def spawn(sd, role, tier, project, label, cfg=None, task=None, plan=None, brief=None):
        r.n[0] += 1; wid = f"W{r.n[0]}"; r.spawns.append((role, tier, label, task, plan, brief))
        d = fleet.fs.load(sd); d["workers"][wid] = {"state": "ready", "role": role, "machine": label}; fleet.fs.save(sd, d)
        return {"id": wid}
    def send_task(sd, wid, plan, tasks, sl_path):
        r.sends.append((wid, list(tasks)))
    monkeypatch.setattr(frw, "spawn", spawn); monkeypatch.setattr(frw, "send_task", send_task)
    return r


def test_for_dispatch_machine_never_reuses(rdisp, capsys):
    rdisp.lines = [("T1,T2", "fresh tier=sonnet agent=superlite:implementer"), ("T3", "agent=W9 tier=haiku")]
    d = fleet.fs.load(rdisp.sd); d["workers"]["W9"] = {"state": "ready", "role": "implementer", "machine": "box"}; fleet.fs.save(rdisp.sd, d)
    assert fleet.main(["spawn", "--for-dispatch", "--machine", "box", "--plan", str(rdisp.plan2)]) == 0
    assert capsys.readouterr().out.splitlines()[:3] == ["W1 T1 sent machine=box", "W2 T2 sent machine=box", "W3 T3 sent machine=box"]
    assert [x[:4] for x in rdisp.spawns] == [("implementer", "sonnet", "box", "T1"), ("implementer", "sonnet", "box", "T2"), ("implementer", "haiku", "box", "T3")]
    assert rdisp.sends == [("W1", ["T1"]), ("W2", ["T2"]), ("W3", ["T3"])]
    assert fleet.fs.load(rdisp.sd)["workers"]["W9"]["state"] == "ready"  # an idle remote worker is neither reused nor stopped


def test_dropped_ready_skips_remote_workers(world):
    d = fleet.fs.default(); d["workers"] = {"W1": {"state": "ready", "role": "implementer", "machine": "box"}, "W2": {"state": "ready", "role": "implementer"}}
    fleet.fs.save(world.sd, d)
    (world.sd / "pool.json").write_text(json.dumps({"agents": []}))
    assert fleet._dropped_ready(world.sd) == ["W2"]


def test_for_dispatch_machine_blocked_spawn_continues(rdisp, capsys, monkeypatch):
    import fleet_remote_worker as frw
    real = frw.spawn
    def spawn(sd, role, tier, project, label, cfg=None, task=None, plan=None, brief=None):
        if task == "T1":
            print(f"BLOCKED: fleet spawn: machine {label}: account claude2 is not signed in on {label}"); raise SystemExit(3)
        return real(sd, role, tier, project, label, cfg, task, plan, brief)
    monkeypatch.setattr(frw, "spawn", spawn)
    rdisp.lines = [("T1,T2", "fresh tier=sonnet agent=superlite:implementer")]
    assert fleet.main(["spawn", "--for-dispatch", "--machine", "box", "--plan", str(rdisp.plan2)]) == 3
    out = capsys.readouterr().out
    assert "BLOCKED: T1 not sent (" in out and "not signed in" in out and "W1 T2 sent machine=box" in out


def test_local_dispatch_unchanged(rdisp, capsys):
    import fleet_remote_worker as frw
    rdisp.lines = [("T1", "fresh tier=sonnet agent=superlite:implementer")]
    assert fleet.main(["spawn", "--for-dispatch", "--plan", str(rdisp.plan2)]) in (0, 3)
    assert rdisp.spawns == [] and rdisp.sends == []


def test_spawn_machine_passes_task_and_brief(world, monkeypatch):
    import fleet_remote_worker as frw
    seen = []
    monkeypatch.setattr(frw, "spawn", lambda *a, **k: seen.append((a, k)) or {"id": "W1"})
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj, role="fixer", machine="box", remote_brief="/p/b.md")
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj, role="implementer", machine="box", task="T1")
    assert seen[0][1] == {"brief": "/p/b.md"} and seen[1][1] == {"task": "T1", "plan": str(world.plan)}


def test_cli_machine_fixer_brief_reaches_remote_spawn(world, monkeypatch):
    import fleet_remote_worker as frw
    import fleet_io as fio
    fleet.main(["on"]); seen, sent = [], []
    brief = world.proj / "b.md"; brief.write_text("fix")
    monkeypatch.setattr(frw, "spawn", lambda *a, **k: seen.append((a, k)) or {"id": "W1"})
    monkeypatch.setattr(fio, "send_brief", lambda sd, wid, b, label="", **k: sent.append((wid, b)) or label)
    assert fleet.main(["spawn", "--role", "fixer", "--brief", str(brief), "--machine", "box"]) == 0
    assert seen[0][0][1] == "fixer" and seen[0][1]["brief"] == str(brief) and sent == [("W1", str(brief))]


def test_for_review_machine_spawns_remote_reviewer(world, monkeypatch, capsys):
    import fleet_remote_worker as frw
    import fleet_io as fio
    plan = world.proj / "rp.md"; plan.write_text("# Plan\n\n### T1 first · Complexity 3 (O-1) · Est. context 40k\n**Owns:** src/a.py\n")
    fleet.main(["on"]); capsys.readouterr()
    (world.sd / "progress.md").write_text("- commit T1 abc1234 first\n")
    seen, sent = [], []
    monkeypatch.setattr(fio, "review_brief", lambda *a, **k: "BRIEF\n")
    monkeypatch.setattr(frw, "spawn", lambda *a, **k: seen.append((a, k)) or {"id": "W1"})
    monkeypatch.setattr(fio, "send_brief", lambda sd, wid, b, label="", **k: sent.append((wid, b)) or label)
    d = fleet.fs.load(world.sd); d["workers"]["W1"] = {"state": "ready", "role": "package-reviewer", "machine": "box"}; fleet.fs.save(world.sd, d)
    assert fleet.main(["spawn", "--for-review", "T1", "--machine", "box", "--plan", str(plan)]) == 0
    assert seen[0][0][1] == "package-reviewer" and seen[0][0][4] == "box" and seen[0][1]["brief"].endswith("review-T1.md") and sent[0][0] == "W1"


def test_for_dispatch_machine_poll_line_gets_fresh_workers(rdisp, capsys):
    rdisp.lines = [("T1,T2", "poll W7,W8 tier=sonnet")]
    assert fleet.main(["spawn", "--for-dispatch", "--machine", "box", "--plan", str(rdisp.plan2)]) == 0
    assert capsys.readouterr().out.splitlines()[:2] == ["W1 T1 sent machine=box", "W2 T2 sent machine=box"]
    assert [x[3] for x in rdisp.spawns] == ["T1", "T2"]


def test_for_dispatch_machine_wave0_says_run_without_machine(rdisp, capsys):
    rdisp.lines = [("T0", "wave0 tier=haiku")]
    assert fleet.main(["spawn", "--for-dispatch", "--machine", "box", "--plan", str(rdisp.plan2)]) == 3
    assert "run Wave 0 without --machine" in capsys.readouterr().out and rdisp.spawns == []
