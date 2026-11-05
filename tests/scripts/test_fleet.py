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
        self.HerdrError = type("HerdrError", (Exception,), {"__init__": lambda s, code, message="": (setattr(s, "code", code), setattr(s, "message", message), None)[-1]})
    def create_workspace(self, label, cwd, env_vars):
        if self.create_error: raise self.HerdrError(self.create_error, "missing")
        self.calls.append(("create_workspace", label, env_vars)); return ("w6", "w6:p1")
    def split_pane(self, pane_id, direction, cwd, env_vars):
        self.calls.append(("split_pane", pane_id, direction))
        if self.split_error: e, self.split_error = self.split_error, None; raise self.HerdrError(e, "pane gone")
        return f"w6:p{len(self.calls) + 1}"
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
    def exit_agent(self, name): self.calls.append(("exit_agent", name))
    def close_pane(self, pane_id): self.calls.append(("close_pane", pane_id))
    def close_workspace(self, ws): self.calls.append(("close_workspace", ws))

@pytest.fixture
def world(tmp_path, monkeypatch):
    proj = tmp_path / "proj"; (proj / ".superlite").mkdir(parents=True); sd = proj / ".superlite"
    monkeypatch.delenv("SUPERLITE_STATE_DIR", raising=False)
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
    assert ("send_keys", "sl-proj-w1", ["Down", "Enter"]) in world.fh.calls

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
    assert e.value.code == 3 and "BLOCKED: W1" in capsys.readouterr().out and ("close_pane", "w6:p1") in world.fh.calls
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
    assert {c[1] for c in world.fh.calls if c[0] in by_name} == {"sl-proj-w1"}
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["name"] == "sl-proj-w1"

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
    assert fleet.stop(world.sd, all_=True) == ["W1"] and ("exit_agent", "sl-proj-w1") in world.fh.calls


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
    monkeypatch.setattr(fleet.ac, "pick_account", lambda usage, allowed, running=None, tier=None: (seen.append((dict(running or {}), tier)), real(usage, allowed, running, tier))[1])
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
