"""fleet_mcp: servers a fleet worker keeps and the generated config (#576)."""
from __future__ import annotations

import json
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_mcp  # noqa: E402

DOCS = {"command": "npx", "args": ["-y", "docs-mcp"]}


@pytest.fixture(autouse=True)
def private_home(tmp_path, monkeypatch):
    monkeypatch.setenv("SUPERLITE_USER_TEST_CMD", str(tmp_path / "no-user-cfg.json"))


def project(tmp_path, cfg=None, mcp=None):
    p = tmp_path / "proj"
    (p / ".superlite").mkdir(parents=True)
    if cfg is not None:
        (p / ".superlite" / "test-cmd.json").write_text(json.dumps(cfg))
    if mcp is not None:
        (p / ".mcp.json").write_text(mcp if isinstance(mcp, str) else json.dumps(mcp))
    return p


def test_research_gets_nothing(tmp_path):
    p = project(tmp_path, {"test": "pytest", "mcp": ["docs"]}, {"mcpServers": {"docs": DOCS}})
    assert fleet_mcp.servers("research", p, tmp_path / "j.json") == ({}, [])


def test_named_server_from_project_file(tmp_path):
    p = project(tmp_path, {"test": "pytest", "mcp": ["docs"]}, {"mcpServers": {"docs": DOCS, "other": {"command": "x"}}})
    assert fleet_mcp.servers("implementer", p, tmp_path / "j.json") == ({"docs": DOCS}, [])


@pytest.mark.skipif(sys.platform != "darwin", reason="xcode default is macOS only")
def test_xcode_default(tmp_path):
    p = project(tmp_path)
    (p / "App.xcodeproj").mkdir()
    assert fleet_mcp.servers("fixer", p, tmp_path / "missing.json") == (
        {"xcode": {"type": "stdio", "command": "xcrun", "args": ["mcpbridge"]}}, [])


def test_no_default_off_macos(tmp_path, monkeypatch):
    monkeypatch.setattr(sys, "platform", "linux")
    p = project(tmp_path)
    (p / "App.xcodeproj").mkdir()
    assert fleet_mcp.servers("fixer", p, None) == ({}, [])


def test_local_scope_beats_project_file(tmp_path):
    p = project(tmp_path, {"test": "t", "mcp": ["docs"]}, {"mcpServers": {"docs": {"command": "proj"}}})
    j = tmp_path / "j.json"
    j.write_text(json.dumps({"projects": {str(p.resolve()): {"mcpServers": {"docs": {"command": "local"}}}}}))
    assert fleet_mcp.servers("implementer", p, j) == ({"docs": {"command": "local"}}, [])


def test_user_scope_used_last(tmp_path):
    p = project(tmp_path, {"test": "t", "mcp": ["docs"]})
    j = tmp_path / "j.json"
    j.write_text(json.dumps({"mcpServers": {"docs": DOCS}}))
    assert fleet_mcp.servers("package-reviewer", p, j) == ({"docs": DOCS}, [])


def test_malformed_files_count_as_empty(tmp_path):
    p = project(tmp_path, {"test": "t", "mcp": ["docs"]}, "{not json")
    j = tmp_path / "j.json"
    j.write_text("[]")
    got, notes = fleet_mcp.servers("implementer", p, j)
    assert got == {} and len(notes) == 1 and notes[0].startswith("mcp: docs left out: no definition")


def test_unknown_name_note(tmp_path):
    p = project(tmp_path, {"test": "t", "mcp": ["nope"]})
    j = tmp_path / "j.json"
    assert fleet_mcp.servers("implementer", p, j) == (
        {}, [f"mcp: nope left out: no definition in {p}/.mcp.json, {j} or the built-in list"])


@pytest.mark.skipif(sys.platform != "darwin", reason="xcode default is macOS only")
def test_bad_mcp_value_falls_back(tmp_path, capsys):
    p = project(tmp_path, {"test": "t", "mcp": "xcode"})
    (p / "App.xcodeproj").mkdir()
    got, notes = fleet_mcp.servers("implementer", p, None)
    assert list(got) == ["xcode"] and notes == []
    assert fleet_mcp.BAD_MCP in capsys.readouterr().err


def test_empty_list_turns_default_off(tmp_path):
    p = project(tmp_path, {"test": "t", "mcp": []})
    (p / "App.xcodeproj").mkdir()
    assert fleet_mcp.servers("implementer", p, None) == ({}, [])


def test_write_config_is_content_addressed(tmp_path):
    a = fleet_mcp.write_config(tmp_path, {"docs": DOCS})
    assert a.parent == tmp_path / "fleet" and a.name.startswith("mcp-") and a.suffix == ".json"
    assert len(a.stem) == len("mcp-") + 10
    assert json.loads(a.read_text()) == {"mcpServers": {"docs": DOCS}}
    assert fleet_mcp.write_config(tmp_path, {"docs": DOCS}) == a
    assert fleet_mcp.write_config(tmp_path, {"docs": {"command": "x"}}) != a
    assert fleet_mcp.write_config(tmp_path, {}) is None


def test_deny_and_note():
    assert fleet_mcp.deny(["docs", "xcode"]) == ["mcp__xcode__XcodeOpenWorkspace", "mcp__xcode__XcodeCloseWorkspace"]
    assert fleet_mcp.deny(["docs"]) == []
    assert fleet_mcp.usage_note(["xcode"]) == fleet_mcp.XCODE_NOTE
    assert fleet_mcp.usage_note(["docs"]) == ""
    assert not any(c in fleet_mcp.XCODE_NOTE for c in "`'\"$!#\n")


def test_write_config_replaces_atomically(tmp_path, monkeypatch):
    calls = []
    real = fleet_mcp.os.replace
    monkeypatch.setattr(fleet_mcp.os, "replace", lambda a, b: (calls.append(b), real(a, b))[1])
    a = fleet_mcp.write_config(tmp_path, {"docs": DOCS})
    assert calls == [a] and sorted(q.name for q in a.parent.iterdir()) == [a.name]


def test_write_config_takes_servers_keyword(tmp_path):
    assert fleet_mcp.write_config(tmp_path, servers={"docs": DOCS}) == fleet_mcp.write_config(tmp_path, {"docs": DOCS})


def test_signatures_match_the_plan():
    import typing

    assert typing.get_type_hints(fleet_mcp.servers)["return"] == tuple[dict, list[str]]
    assert typing.get_type_hints(fleet_mcp.deny) == {"names": list[str], "return": list[str]}
