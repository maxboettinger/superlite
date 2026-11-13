# tests/scripts/test_fleet_lead_config_681.py: the lead starts from a run config (#681): lean argv, cache TTL, snapshot, MCP list
import json
import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)
import fleet_lead as fl  # noqa: E402
import fleet_mcp  # noqa: E402
import mcp_check  # noqa: E402

pytestmark = pytest.mark.skipif(REAL, reason="argv and env are read from the in-process fake")
ENV = {"HOME": "/u"}


def _start(world, tmp_path, monkeypatch, rc, env=ENV):
    monkeypatch.setenv("SUPERLITE_HOME", str(tmp_path / "home"))
    fleet.main(["on", "--accounts", "claude1,claude3"])
    wt = tmp_path / "wt"; wt.mkdir()
    r = fl.spawn_lead(world.sd, wt, None, env=env, rc=rc)
    argv = next(c for c in world.fh.calls if c[0] == "start_agent")[2]
    return wt, r, argv


def _cfg(**lead):
    rc = fl.run_config.resolve()
    rc["lead"] = {**rc["lead"], **lead}
    return rc


def test_old_argv_kept():
    assert fl.lead_argv("/p/sl", "opus") == ["--model", "opus", "--permission-mode", "auto", "--allowedTools", "Bash(maxapp ship *)",
                                             "Bash(/p/sl backlog ship *)", "--disallowedTools", "AskUserQuestion"]


def test_lead_argv_lean_forms():
    base = ["--allowedTools", "Bash(maxapp ship *)", "Bash(/p/sl backlog ship *)"]
    assert fl.lead_argv("/p/sl", "opus", 400000, "xhigh", ["Artifact"]) == [
        "--model", "opus", "--effort", "xhigh", "--permission-mode", "auto", *base, "--strict-mcp-config", "--no-chrome",
        "--disallowedTools", "AskUserQuestion", "Artifact", "--autocompact", "400k"]
    assert fl.lead_argv("/p/sl", "opus", None, "high", [], "/s/mcp.json") == [
        "--model", "opus", "--effort", "high", "--permission-mode", "auto", *base, "--strict-mcp-config", "--mcp-config", "/s/mcp.json",
        "--no-chrome", "--disallowedTools", "AskUserQuestion"]


def test_spawn_argv_from_config(world, tmp_path, monkeypatch):
    rc = fl.run_config.resolve()
    _, _, argv = _start(world, tmp_path, monkeypatch, rc)
    assert argv[argv.index("--effort") + 1] == "xhigh"
    assert argv.count("--strict-mcp-config") == 1 and argv.count("--no-chrome") == 1
    for d in rc["lead"]["deny"]:
        assert argv.count(d) == 1
    assert "--disable-slash-commands" not in argv


def test_spawn_ttl_env(world, tmp_path, monkeypatch):
    rc = fl.run_config.resolve()
    _, _, _ = _start(world, tmp_path, monkeypatch, rc)
    assert next(c for c in world.fh.calls if c[0] == "create_workspace")[2]["CLAUDE_CODE_PROMPT_CACHE_TTL"] == "1h"
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert w["launch"]["env"]["CLAUDE_CODE_PROMPT_CACHE_TTL"] == "1h"


def test_no_ttl_sets_no_key(world, tmp_path, monkeypatch):
    rc = fl.run_config.resolve()
    rc["cache_ttl"] = {**rc["cache_ttl"], "lead": None}
    _start(world, tmp_path, monkeypatch, rc)
    w = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    assert "CLAUDE_CODE_PROMPT_CACHE_TTL" not in w["launch"]["env"]


def test_config_window_beats_main_window(world, tmp_path, monkeypatch):
    _, _, argv = _start(world, tmp_path, monkeypatch, _cfg(autocompact=300000), env={"HOME": "/u", "CLAUDE_CODE_AUTO_COMPACT_WINDOW": "400000"})
    assert argv[argv.index("--autocompact") + 1] == "300k"


def test_snapshot_and_record(world, tmp_path, monkeypatch):
    rc = fl.run_config.resolve()
    wt, r, _ = _start(world, tmp_path, monkeypatch, rc)
    assert json.loads((wt / ".superlite" / "run-config.json").read_text()) == rc
    assert json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]["run_config"] == rc["id"] == r["config"]


def test_mcp_list_from_config(world, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mcp_check, "check", lambda n, d, sd, project: None)
    wt, _, argv = _start(world, tmp_path, monkeypatch, _cfg(mcp=["xcode"]))
    path = argv[argv.index("--mcp-config") + 1]
    assert path.startswith(str(wt.resolve() / ".superlite" / "fleet" / "mcp-")) or path.startswith(str(wt / ".superlite" / "fleet" / "mcp-"))
    assert "xcode" in json.loads(open(path).read())["mcpServers"]


def test_mcp_failing_check_left_out(world, tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(mcp_check, "check", lambda n, d, sd, project: "no desktop session")
    _, _, argv = _start(world, tmp_path, monkeypatch, _cfg(mcp=["xcode"]))
    assert "--mcp-config" not in argv and "--strict-mcp-config" in argv
    assert capsys.readouterr().err.count("mcp: xcode left out: no desktop session") == 1


def test_mcp_error_never_blocks(world, tmp_path, monkeypatch, capsys):
    def boom(*a, **k): raise RuntimeError("bad")
    monkeypatch.setattr(fleet_mcp, "named", boom)
    _, _, argv = _start(world, tmp_path, monkeypatch, _cfg(mcp=["xcode"]))
    assert "--mcp-config" not in argv and "--strict-mcp-config" in argv
    assert "mcp: none: bad" in capsys.readouterr().err


def test_named_list():
    P = "/nonexistent-project"
    assert fleet_mcp.named(["xcode"], P, None) == ({"xcode": fleet_mcp.XCODE}, [])
    kept, notes = fleet_mcp.named(["nope"], P, None)
    assert kept == {} and notes == [f"mcp: nope left out: no definition in {P}/.mcp.json, None or the built-in list"]
