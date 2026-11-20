"""fleet_mcp.usage_note leaves the RenderPreview sentence out in a linked worktree, where it cannot reach the run (#1021)."""
from __future__ import annotations

from pathlib import Path

import pytest

from test_fleet_mcp_worktree_910 import repos  # noqa: F401  (fixture: main checkout and a linked worktree)
from test_fleet_spawn_mcp_576 import _argv, fleet, world  # noqa: F401  (world is a fixture)
from test_fleet import REAL

import fleet_mcp  # noqa: E402
import state  # noqa: E402

OLD = ("Xcode MCP tools (mcp__xcode__...) are connected. After each edit of a Swift file run XcodeRefreshCodeIssuesInFile on it "
       "and fix what it reports. Render every Preview you add or change with RenderPreview before you report DONE, "
       "unless your checkout is a linked git worktree (its .git is a file): RenderPreview renders the workspace Xcode has open, "
       "the main checkout, so there skip it and never report a preview as unrendered. "
       "Look up Apple APIs with DocumentationSearch. Only the coordinator opens or closes an Xcode workspace; "
       "if none is open for this project, say so in your report instead of opening one.")
MAIN = fleet_mcp.XCODE_HEAD + fleet_mcp.XCODE_RENDER + fleet_mcp.XCODE_TAIL
WT = fleet_mcp.XCODE_HEAD + fleet_mcp.XCODE_TAIL


def test_note_without_project_is_unchanged():
    assert fleet_mcp.XCODE_NOTE == OLD
    assert fleet_mcp.usage_note(["xcode"]) == OLD


def test_main_checkout_keeps_plain_render_rule(repos):
    main, _ = repos
    note = fleet_mcp.usage_note(["docs", "xcode"], main)
    assert note == MAIN
    assert "Render every Preview you add or change with RenderPreview before you report DONE. Look up" in note
    assert "linked git worktree" not in note


def test_linked_worktree_leaves_render_rule_out(repos):
    _, wt = repos
    note = fleet_mcp.usage_note(["xcode"], wt)
    assert note == WT
    assert "RenderPreview" not in note and "Preview" not in note
    assert "XcodeRefreshCodeIssuesInFile" in note and "DocumentationSearch" in note


def test_str_project_works(repos):
    main, wt = repos
    assert fleet_mcp.usage_note(["xcode"], str(wt)) == WT
    assert fleet_mcp.usage_note(["xcode"], str(main)) == MAIN


def test_no_xcode_gives_empty(repos):
    main, wt = repos
    assert fleet_mcp.usage_note(["docs"], wt) == ""
    assert fleet_mcp.usage_note([], main) == ""
    assert fleet_mcp.usage_note([]) == ""


def test_detection_error_keeps_full_note(repos, monkeypatch):
    _, wt = repos
    monkeypatch.setattr(state, "linked_worktree", lambda p: (_ for _ in ()).throw(OSError("x")))
    assert fleet_mcp.usage_note(["xcode"], wt) == OLD


def test_variants_are_shell_safe():
    for note in (OLD, MAIN, WT):
        assert not any(c in note for c in "`'\"$!#\n")


@pytest.mark.skipif(REAL, reason="argv is read from the in-process fake")
def test_spawn_passes_project_to_usage_note(world, monkeypatch):
    seen = []
    monkeypatch.setattr(fleet_mcp, "servers", lambda *a, **k: ({"xcode": fleet_mcp.XCODE}, []))
    monkeypatch.setattr(fleet_mcp, "usage_note", lambda names, project=None: seen.append((list(names), project)) or "NOTE-1021")
    fleet.main(["on"])
    fleet.spawn(world.sd, world.plan, "sonnet", world.proj)
    argv = _argv(world)
    assert argv[argv.index("--append-system-prompt") + 1] == "NOTE-1021"
    assert seen == [(["xcode"], seen[0][1])] and Path(seen[0][1]).resolve() == Path(world.proj).resolve()
