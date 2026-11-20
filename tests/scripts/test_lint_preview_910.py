"""#910: lint warns on a task step that renders a preview when the run is a linked worktree."""
import os
import subprocess
import sys
from pathlib import Path

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet_mcp  # noqa: E402
import plan_tools as ptm  # noqa: E402

PLAN_TOOLS = SCRIPTS / "plan_tools.py"
FENCE = "```"
GRAPH = f"""{FENCE}mermaid
flowchart LR
  T1[one]
  T2[two]
  T3[three]
  %% taskgraph
  T1 --> T2
{FENCE}
"""
STEP = "**Steps:** 4 render BadgeView previews with RenderPreview"


def plan_text(t2_lines=(STEP,), t3_lines=("**Steps:** 1 write it",), head2="### T2 badge · Complexity 2 · Est. context 30k"):
    t2 = "\n".join(t2_lines)
    t3 = "\n".join(t3_lines)
    return (f"# Plan\n**Goal:** x.\n\n{GRAPH}\n### T1 one · Complexity 2 · Est. context 30k\n**Owns:** a.py\n\n"
            f"{head2}\n**Owns:** b.py\n{t2}\n\n### T3 three · Complexity 2 · Est. context 30k\n**Owns:** c.py\n{t3}\n")


def W(tid, snip):
    return (f'WARNING: PREVIEW: {tid} names a preview render as a step ("{snip}"), but this run is a linked worktree: '
            "RenderPreview renders the workspace Xcode has open, the main checkout /w/main; drop the step and list the view under "
            "## Running-app checks as - C<n>: <view>; reach: preview <name>; see: <what must show>, which the checker renders "
            "into .superlite/render/")


@pytest.fixture(autouse=True)
def fake(monkeypatch):
    monkeypatch.setattr(fleet_mcp, "worktree_previews", lambda p: Path("/w/main"))


def warns(text, root=Path("/w/wt")):
    return ptm.preview_warnings(ptm.Plan(text), root)


def test_step_warns_in_worktree():
    assert warns(plan_text()) == [W("T2", STEP)]


def test_renderpreview_word_alone_warns():
    got = warns(plan_text(("**Notes:** check it in RenderPreview",)))
    assert got == [W("T2", "**Notes:** check it in RenderPreview")]


def test_main_checkout_quiet(monkeypatch):
    monkeypatch.setattr(fleet_mcp, "worktree_previews", lambda p: None)
    assert warns(plan_text()) == []
    assert ptm.preview_warnings(ptm.Plan(plan_text()), None) == []


def test_draft_task_quiet():
    assert warns(plan_text((STEP, "**Status:** draft"))) == []


def test_fenced_line_quiet():
    assert warns(plan_text((f"{FENCE}", "render the previews", f"{FENCE}"))) == []


def test_owns_line_quiet():
    text = plan_text(("**Owns:** Sources/Previews/render.swift", "**Also-touches:** Previews/render.swift"),
                     head2="### T2 render previews · Complexity 2 · Est. context 30k")
    assert warns(text) == []


def test_checker_pointer_quiet():
    assert warns(plan_text(("**Notes:** previews are rendered by the checker (C2)",))) == []


def test_one_warning_per_task():
    got = warns(plan_text((STEP, "**Notes:** RenderPreview again"), ("**Notes:** RenderPreview here",)))
    assert got == [W("T2", STEP), W("T3", "**Notes:** RenderPreview here")]


def test_long_snippet_cut():
    line = "**Notes:** render previews " + "x" * 63
    assert len(line) == 90
    assert warns(plan_text((line,))) == [W("T2", line[:57] + "...")]


def test_detector_error_quiet(monkeypatch):
    def boom(p):
        raise RuntimeError("x")
    monkeypatch.setattr(fleet_mcp, "worktree_previews", boom)
    assert warns(plan_text()) == []


def test_lint_prints_preview_warning(tmp_path):
    proj = tmp_path / "proj"
    (proj / ".superlite").mkdir(parents=True)
    (proj / ".git").mkdir()
    p = proj / "plan.md"
    p.write_text(plan_text(), encoding="utf-8")
    boot = tmp_path / "boot.py"
    boot.write_text("import sys, runpy\nsys.path.insert(0, %r)\nimport fleet_mcp\nfrom pathlib import Path\n"
                    "fleet_mcp.worktree_previews = lambda p: Path('/w/main')\n"
                    "sys.argv = [%r, 'lint', '--plan', %r]\nrunpy.run_path(%r, run_name='__main__')\n"
                    % (str(SCRIPTS), str(PLAN_TOOLS), str(p), str(PLAN_TOOLS)), encoding="utf-8")
    env = dict(os.environ, PYTHONIOENCODING="utf-8", SUPERLITE_HOME=str(tmp_path / "home"))
    out = subprocess.run([sys.executable, str(boot)], capture_output=True, text=True, cwd=proj, env=env, timeout=120).stdout
    assert W("T2", STEP) in out
