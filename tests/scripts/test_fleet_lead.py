# tests/scripts/test_fleet_lead.py
import json
from pathlib import Path
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import fleet_lead as fl  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="argv and env are read from the in-process fake")

def test_lead_argv_and_env(tmp_path):
    assert fl.lead_argv("/p/sl", "opus") == ["--model", "opus", "--permission-mode", "auto", "--allowedTools", "Bash(maxapp ship *)",
                                             "Bash(/p/sl backlog ship *)", "--disallowedTools", "AskUserQuestion"]
    m, l = tmp_path / "m" / ".superlite", tmp_path / "wt" / ".superlite"
    assert fl.lead_env(m, l, "W2", "/u/.claude-account3", {"HOME": "/u", "CLAUDE_CODE_PLUGIN_CACHE_DIR": "/c"}, ["claude1", "claude3"]) == {
        "SUPERLITE_FLEET_WORKER": "W2", "SUPERLITE_FLEET_AGENT": "lead", "SUPERLITE_FLEET_ROLE": "lead", "SUPERLITE_STATE_DIR": str(l.resolve()),
        "SUPERLITE_FLEET_PARENT_DIR": str(m.resolve()), "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION": "0", "SUPERLITE_FLEET_ACCOUNTS": "claude1,claude3",
        "CLAUDE_CONFIG_DIR": "/u/.claude-account3", "CLAUDE_CODE_PLUGIN_CACHE_DIR": "/c"}
    assert not {"SUPERLITE_FLEET_ACCOUNTS", "CLAUDE_CONFIG_DIR", "SUPERLITE_FINAL_REVIEW"} & set(fl.lead_env(m, l, "W2", "/u/.claude", {"HOME": "/u"}, []))

def test_spawn_lead_starts_in_the_worktree_without_prime(world, tmp_path, monkeypatch, capsys):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    wt = tmp_path / "wt"; wt.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    rc = fl.run_config.resolve()
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"}, rc=rc)
    lsd, name = str((wt / ".superlite").resolve()), fleet.fs.agent_name(world.sd, "W1", root=wt, ident="lead")
    assert r == {"id": "W1", "name": name, "account": "claude3", "pane_id": "w6:p1", "agent": "lead", "model": "opus", "role": "lead", "lead_sd": lsd, "config": rc["id"]}
    sl = str(Path(fl.__file__).resolve().parent / "sl")
    assert ("start_agent", name, fl.lead_argv(sl, "opus", 400000, "xhigh", list(rc["lead"]["deny"]))) in world.fh.calls and not any(c[0] == "prompt" for c in world.fh.calls)
    env = next(c for c in world.fh.calls if c[0] == "create_workspace")[2]
    assert (env["SUPERLITE_FLEET_ROLE"], env["SUPERLITE_STATE_DIR"], env["SUPERLITE_FLEET_PARENT_DIR"]) == ("lead", lsd, str(world.sd.resolve()))
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert (w["state"], w["role"], w["one_turn"], w["lead_sd"], w["worktree"]) == ("ready", "lead", False, lsd, str(wt.resolve()))
    assert not (world.sd / "pool.json").exists() or json.loads((world.sd / "pool.json").read_text())["agents"] == []
    assert "W1 account=claude3 pane=w6:p1 agent=lead role=lead" in capsys.readouterr().out
    assert json.loads((world.sd / "metrics.jsonl").read_text().splitlines()[0])["type"] == "fleet:lead"

def test_trust_dialog_and_stopping_a_lead_stops_its_fleet_first(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    fleet.main(["on"]); world.fh.start_error = "agent_not_ready"; world.fh.screen = "Quick safety check\n   Yes, I trust this folder\n"
    wt = tmp_path / "wt"; fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"})
    name = fleet.fs.agent_name(world.sd, "W1", root=wt, ident="lead")
    assert ("send_keys", name, ["Down", "Enter"]) in world.fh.calls
    lsd = wt / ".superlite"
    fleet.fs.save(lsd, {**fleet.fs.default(), "on": True, "workspace_id": "w9", "workers": {"W1": {"name": "sl-wt-ab12-w1", "pane_id": "w9:p1", "state": "busy"}}})
    fleet.stop(world.sd, ["W1"])
    assert [c[1] for c in world.fh.calls if c[0] == "exit_agent"] == ["sl-wt-ab12-w1", name]
    assert fleet.fs.load(lsd)["workers"]["W1"]["state"] == "stopped"


# (#1041)
SEALED = {"GH_TOKEN": "", "GITHUB_TOKEN": "", "GH_ENTERPRISE_TOKEN": "", "GITHUB_ENTERPRISE_TOKEN": ""}


def test_gh_seal_env_clears_the_tokens_the_spawner_lacks():
    assert fl.GH_TOKENS == ("GH_TOKEN", "GITHUB_TOKEN", "GH_ENTERPRISE_TOKEN", "GITHUB_ENTERPRISE_TOKEN")
    assert fl.gh_seal_env({"HOME": "/u"}) == {} and fl.gh_seal_env({"GH_CONFIG_DIR": "", "GH_TOKEN": ""}) == {}
    assert fl.gh_seal_env({"HOME": "/u", "GH_CONFIG_DIR": "/e"}) == {**SEALED, "GH_CONFIG_DIR": "/e"}
    kept = fl.gh_seal_env({"GH_CONFIG_DIR": "/e", "GH_TOKEN": "t", "GITHUB_TOKEN": ""})
    assert kept == {"GITHUB_TOKEN": "", "GH_ENTERPRISE_TOKEN": "", "GITHUB_ENTERPRISE_TOKEN": "", "GH_CONFIG_DIR": "/e"}
    assert "t" not in kept.values()


def test_write_gh_seal_writes_the_settings_file_only_when_sealed(tmp_path):
    assert fl.write_gh_seal(tmp_path, {"HOME": "/u"}) is None and not (tmp_path / fl.GH_SEAL_FILE).exists()
    p = fl.write_gh_seal(tmp_path, {"GH_CONFIG_DIR": "/e"})
    assert p == tmp_path / fl.GH_SEAL_FILE == tmp_path / "gh-seal-settings.json"
    assert json.loads(p.read_text(encoding="utf-8")) == {"env": {**SEALED, "GH_CONFIG_DIR": "/e"}}


def test_lead_argv_puts_settings_after_the_permission_mode():
    base = fl.lead_argv("/p/sl", "opus")
    assert fl.lead_argv("/p/sl", "opus", settings=None) == base and "--settings" not in base
    assert fl.lead_argv("/p/sl", "opus", settings="/w/s.json") == base[:4] + ["--settings", "/w/s.json"] + base[4:]


def test_sealed_lead_starts_with_the_gh_seal_settings(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    wt, gh = tmp_path / "wt", tmp_path / "gh"
    wt.mkdir(); gh.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u", "GH_CONFIG_DIR": str(gh)}, rc=fl.run_config.resolve())
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent" and c[1] == r["name"])
    f = (wt / ".superlite").resolve() / fl.GH_SEAL_FILE
    assert argv[argv.index("--settings") + 1] == str(f)
    assert json.loads(f.read_text(encoding="utf-8")) == {"env": {**SEALED, "GH_CONFIG_DIR": str(gh)}}
    env = next(c for c in world.fh.calls if c[0] == "create_workspace")[2]
    assert env["GH_CONFIG_DIR"] == str(gh) and not set(SEALED) & set(env)
    assert json.loads((world.sd / "fleet.json").read_text())["workers"][r["id"]]["launch"]["argv"] == argv


def test_unsealed_lead_starts_without_settings(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    wt = tmp_path / "wt"; wt.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u", "GH_TOKEN": "t"}, rc=fl.run_config.resolve())
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent" and c[1] == r["name"])
    assert "--settings" not in argv and not (wt / ".superlite" / fl.GH_SEAL_FILE).exists()


# (#1051)
def test_plugin_dir_is_the_checkout_with_a_plugin_manifest(tmp_path):
    assert fl.PLUGIN_ROOT == Path(fl.__file__).resolve().parents[3]
    assert (fl.PLUGIN_ROOT / ".claude-plugin" / "plugin.json").is_file() and fl.plugin_dir() == fl.PLUGIN_ROOT
    assert fl.plugin_dir(tmp_path) is None
    (tmp_path / ".claude-plugin").mkdir(); (tmp_path / ".claude-plugin" / "plugin.json").write_text("{}")
    assert fl.plugin_dir(tmp_path) == tmp_path


def test_lead_argv_puts_plugin_dir_after_the_settings():
    base = fl.lead_argv("/p/sl", "opus")
    assert fl.lead_argv("/p/sl", "opus", plugin_dir=None) == base and "--plugin-dir" not in base
    assert fl.lead_argv("/p/sl", "opus", settings="/w/s.json", plugin_dir="/src") == base[:4] + ["--settings", "/w/s.json", "--plugin-dir", "/src"] + base[4:]
    assert fl.lead_argv("/p/sl", "opus", plugin_dir=Path("/src")) == base[:4] + ["--plugin-dir", "/src"] + base[4:]


def test_sealed_lead_loads_the_plugin_of_its_scripts_checkout(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    wt, gh = tmp_path / "wt", tmp_path / "gh"
    wt.mkdir(); gh.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u", "GH_CONFIG_DIR": str(gh)}, rc=fl.run_config.resolve())
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent" and c[1] == r["name"])
    assert argv.count("--plugin-dir") == 1 and argv[argv.index("--plugin-dir") + 1] == str(fl.PLUGIN_ROOT)
    assert argv.index("--plugin-dir") == argv.index("--settings") + 2
    assert json.loads((world.sd / "fleet.json").read_text())["workers"][r["id"]]["launch"]["argv"] == argv


def test_unsealed_lead_loads_the_installed_plugin(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    wt = tmp_path / "wt"; wt.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u"}, rc=fl.run_config.resolve())
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent" and c[1] == r["name"])
    assert "--plugin-dir" not in argv


def test_sealed_lead_without_a_plugin_manifest_loads_the_installed_plugin(world, tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    monkeypatch.setattr(fleet, "PLUGIN_ROOT", tmp_path / "bare")
    wt, gh = tmp_path / "wt", tmp_path / "gh"
    wt.mkdir(); gh.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fl.spawn_lead(world.sd, wt, "opus", env={"HOME": "/u", "GH_CONFIG_DIR": str(gh)}, rc=fl.run_config.resolve())
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent" and c[1] == r["name"])
    assert "--settings" in argv and "--plugin-dir" not in argv


# (#1049)
def test_gh_seal_lives_in_fleet_beside_pass_through():
    assert fl.gh_seal_env is fleet.gh_seal_env and fl.write_gh_seal is fleet.write_gh_seal and fl.plugin_dir is fleet.plugin_dir
    assert (fl.GH_TOKENS, fl.GH_SEAL_FILE, fl.PLUGIN_ROOT) == (fleet.GH_TOKENS, fleet.GH_SEAL_FILE, fleet.PLUGIN_ROOT)
    assert fleet.gh_seal_env({"GH_CONFIG_DIR": "/e", "GH_TOKEN": "t"}, gh_dir="/r/gh") == {
        "GITHUB_TOKEN": "", "GH_ENTERPRISE_TOKEN": "", "GITHUB_ENTERPRISE_TOKEN": "", "GH_CONFIG_DIR": "/r/gh"}
    assert fleet.gh_seal_env({"HOME": "/u"}, gh_dir="/r/gh") == {}


def test_sealed_lead_worker_starts_with_the_gh_seal_settings(world, tmp_path):
    gh = tmp_path / "gh"; gh.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env={"HOME": "/u", "GH_CONFIG_DIR": str(gh), **SEALED})
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent")
    f = world.sd.resolve() / fleet.GH_SEAL_FILE
    assert argv[argv.index("--settings") + 1] == str(f)
    assert json.loads(f.read_text(encoding="utf-8")) == {"env": {**SEALED, "GH_CONFIG_DIR": str(gh)}}
    assert not list(world.sd.glob(fleet.GH_SEAL_FILE + ".*"))
    assert json.loads((world.sd / "fleet.json").read_text())["workers"][r["id"]]["launch"]["argv"] == argv


def test_sealed_lead_worker_loads_the_plugin_of_its_scripts_checkout(world, tmp_path):
    gh = tmp_path / "gh"; gh.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env={"HOME": "/u", "GH_CONFIG_DIR": str(gh)})
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent")
    assert argv.count("--plugin-dir") == 1 and argv[argv.index("--plugin-dir") + 1] == str(fleet.PLUGIN_ROOT)
    assert argv.index("--plugin-dir") == argv.index("--settings") + 2


def test_unsealed_worker_starts_without_settings_or_plugin_dir(world):
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env={"HOME": "/u", "GH_TOKEN": "t"})
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent")
    assert "--settings" not in argv and "--plugin-dir" not in argv and not (world.sd / fleet.GH_SEAL_FILE).exists()


def test_sealed_worker_without_a_plugin_manifest_loads_the_installed_plugin(world, tmp_path, monkeypatch):
    monkeypatch.setattr(fleet, "PLUGIN_ROOT", tmp_path / "bare")
    gh = tmp_path / "gh"; gh.mkdir()
    fleet.main(["on", "--accounts", "claude1,claude3"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj, env={"HOME": "/u", "GH_CONFIG_DIR": str(gh)})
    argv = next(c[2] for c in world.fh.calls if c[0] == "start_agent")
    assert "--settings" in argv and "--plugin-dir" not in argv
