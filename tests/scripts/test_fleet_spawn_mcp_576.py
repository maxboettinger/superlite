# tests/scripts/test_fleet_spawn_mcp_576.py: fleet spawn passes the MCP servers a project names (#576)
import json
from pathlib import Path

import pytest
from test_fleet import REAL, fleet, world  # noqa: F401  (world is a fixture)

import fleet_mcp  # noqa: E402
import mcp_check  # noqa: E402

LEAN = ["--strict-mcp-config", "--no-chrome", "--disable-slash-commands"]
DENY = ["Artifact", "ArtifactComments", "ArtifactData", "ListAgents", "ReadNotifications", "ReportFindings"]
pytestmark = pytest.mark.skipif(REAL, reason="argv is read from the in-process fake")


def _argv(world, i=0):
    return [c for c in world.fh.calls if c[0] == "start_agent"][i][2]


def _docs_project(world):
    (world.sd / "test-cmd.json").write_text(json.dumps({"test": "pytest", "mcp": ["docs"]}))
    (world.proj / ".mcp.json").write_text(json.dumps({"mcpServers": {"docs": {"command": "npx", "args": ["-y", "docs-mcp"]}}}))


def test_lean_argv_mcp_config_and_deny():
    out = fleet.lean_argv(["--agent", "x", "--disallowedTools", "AskUserQuestion"], "/s/fleet/mcp-a.json", ["mcp__xcode__XcodeOpenWorkspace"])
    assert out == ["--agent", "x", "--strict-mcp-config", "--mcp-config", "/s/fleet/mcp-a.json", "--no-chrome", "--disable-slash-commands",
                   "--disallowedTools", "AskUserQuestion", *DENY, "mcp__xcode__XcodeOpenWorkspace"]


def test_lean_argv_without_mcp_is_as_today():
    assert fleet.lean_argv(["--agent", "x"]) == ["--agent", "x", *LEAN, "--disallowedTools", *DENY]


def test_lean_argv_mcp_idempotent():
    a, p, d = ["--agent", "x", "--disallowedTools", "AskUserQuestion"], "/s/fleet/mcp-a.json", ["mcp__xcode__XcodeOpenWorkspace", "mcp__xcode__XcodeCloseWorkspace"]
    once = fleet.lean_argv(a, p, d)
    assert fleet.lean_argv(once, p, d) == once
    assert once.count("--mcp-config") == 1 and once.count("mcp__xcode__XcodeOpenWorkspace") == 1


def test_claude_json():
    assert fleet.claude_json("/u/.claude-account3", {"HOME": "/u"}) == Path("/u/.claude-account3/.claude.json")
    assert fleet.claude_json("/u/.claude", {"HOME": "/u"}) == Path("/u/.claude.json")


def test_implementer_gets_the_file(world, capsys):
    _docs_project(world)
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    argv = _argv(world)
    assert argv.count("--mcp-config") == 1
    path = Path(argv[argv.index("--mcp-config") + 1])
    assert path.parent == world.sd / "fleet" and path.name.startswith("mcp-")
    assert list(json.loads(path.read_text())["mcpServers"]) == ["docs"]
    assert any(l.endswith(" mcp=docs") for l in capsys.readouterr().out.splitlines())


def test_research_spawn_stays_lean(world):
    _docs_project(world)
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, None, world.proj, role="research")
    argv = _argv(world)
    assert "--mcp-config" not in argv and "--append-system-prompt" not in argv
    assert [a for a in argv if a in LEAN] == LEAN


def test_failed_check_left_out(world, monkeypatch, capsys):
    _docs_project(world)
    monkeypatch.setattr(mcp_check, "check", lambda *a, **k: "did not answer tools/list in 15 s")
    fleet.main(["on"])
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert r["id"] == "W1"
    assert "W1 mcp: docs left out: did not answer tools/list in 15 s" in capsys.readouterr().err
    assert "--mcp-config" not in _argv(world)


def test_lookup_error_keeps_worker_lean(world, monkeypatch, capsys):
    def boom(*a, **k):
        raise RuntimeError("bad")
    monkeypatch.setattr(fleet_mcp, "servers", boom)
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert "W1 mcp: none: bad" in capsys.readouterr().err
    assert "--mcp-config" not in _argv(world)


def test_xcode_kept_adds_deny_and_note(world, monkeypatch):
    monkeypatch.setattr(fleet_mcp, "servers", lambda *a, **k: ({"xcode": fleet_mcp.XCODE}, []))
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    argv = _argv(world)
    for n in fleet_mcp.XCODE_DENY:
        assert n in argv[argv.index("--disallowedTools"):]
    assert argv[argv.index("--append-system-prompt") + 1] == fleet_mcp.XCODE_NOTE


def test_lean_project_argv_unchanged(world, capsys):
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    argv = _argv(world)
    assert "--mcp-config" not in argv and "--append-system-prompt" not in argv
    assert " mcp=" not in capsys.readouterr().out


def test_restore_replays_the_file(world):
    _docs_project(world)
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    rec = json.loads((world.sd / "fleet.json").read_text())["workers"]["W1"]
    argv = rec["launch"]["argv"]
    assert argv == _argv(world)
    assert Path(argv[argv.index("--mcp-config") + 1]).is_file()
    assert rec["mcp"] == ["docs"]


def test_write_config_error_keeps_worker_lean(world, monkeypatch, capsys):
    _docs_project(world)

    def boom(*a, **k):
        raise OSError("disk full")
    monkeypatch.setattr(fleet_mcp, "write_config", boom)
    fleet.main(["on"])
    r = fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    assert r["id"] == "W1"
    assert "W1 mcp: none: disk full" in capsys.readouterr().err
    argv = _argv(world)
    assert "--mcp-config" not in argv and "--append-system-prompt" not in argv
