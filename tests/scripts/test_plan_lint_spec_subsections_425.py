"""Tests for spec coverage of unnumbered subsections and quoted Covers titles (#425)."""
from __future__ import annotations

import importlib.util
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
sys.path.insert(0, str(SCRIPTS))
_spec = importlib.util.spec_from_file_location("plan_tools", SCRIPTS / "plan_tools.py")
plan_tools = importlib.util.module_from_spec(_spec)
sys.modules["plan_tools"] = plan_tools
_spec.loader.exec_module(plan_tools)


def make_plan(covers=None, prose=""):
    cov = f"**Covers:** {covers}\n" if covers is not None else ""
    return plan_tools.Plan(
        "# Plan\n**Goal:** test.\n\n```mermaid\n%% taskgraph\nflowchart LR\n  T1\n```\n\n"
        f"### T1 build · Complexity 1 · Est. context 5k\n**Owns:** a.py\n{cov}**Tests:** fast\n{prose}\n")


def gaps(spec, covers=None, prose=""):
    return plan_tools.spec_gaps(spec, make_plan(covers, prose))


def test_covers_entries_values():
    assert plan_tools.covers_entries('8, "Auth, sessions and tokens" · `§ 2.1`; Parser') == [
        "8", "auth, sessions and tokens", "2.1", "parser"]
    assert plan_tools.covers_entries('"unterminated, x') == ["unterminated", "x"]
    assert plan_tools.covers_entries("") == []


def test_number_covers_unnumbered_child():
    spec = "## 8. Endpoints\n### B2. Optional header on three endpoints (R18)\n## 9. Limits\n"
    assert gaps(spec, "8") == ["9. Limits"]
    assert gaps(spec, "9") == ["8. Endpoints", "B2. Optional header on three endpoints (R18)"]


def test_cover_stops_at_same_level():
    spec = "## 8. A\n### X one\n## Zed part\n### Y two\n"
    assert gaps(spec, "8") == ["Zed part", "Y two"]


def test_title_covers_children():
    spec = "## Auth, sessions and tokens\n### Refresh flow\n"
    assert gaps(spec, '"Auth, sessions and tokens"') == []
    assert gaps(spec, "Auth, sessions and tokens") == ["Refresh flow"]


def test_covers_line_mention_covers_heading_only():
    assert gaps("## Parser\n### Lexer\n", "2.1 Parser") == ["Lexer"]
    assert gaps("## Parser\n", "§2.1 Parser") == []


def test_number_only_heading():
    spec = "## 8\n### Retry rules\n"
    assert gaps(spec, "8") == []
    assert gaps(spec) == ["8", "Retry rules"]


def test_h4_and_fences():
    spec = "## 8. Zebra\n#### deep\n```\n## 9. Fenced\n```\n"
    assert gaps(spec) == ["8. Zebra"]
    assert gaps("## 1. Top\n```\n## 2. Fenced\n```\n### Child\n", "1") == []


def test_old_forms_unchanged():
    spec = "## 2. Core\n### 2.1 Parse\n"
    assert gaps(spec, "2") == [] and gaps(spec, "2.1") == ["2. Core"]
    assert gaps("## Parser\n### Lexer\n", prose="We build the parser here.") == ["Lexer"]
    assert gaps("## 3. X\n", prose="see § 3") == []
    assert gaps("## Intent\n## Decisions (x)\n## Out of scope\n") == []


def test_lint_uses_spec_gaps(tmp_path):
    from test_plan_tools import run
    from test_shape import two
    p = two(tmp_path, eg=['lang.parse("1") -> Num(1)'])
    txt = p.read_text(encoding="utf-8")
    p.write_text(txt.replace("**Owns:**", "**Covers:** 8\n**Owns:**", 1), encoding="utf-8")
    s = tmp_path / "spec.md"
    s.write_text("## 8. Endpoints\n### B2. Optional header\n## 9. Limits\n", encoding="utf-8")
    out = run(SCRIPTS / "plan_tools.py", "lint", "--plan", p, "--spec", s).out
    assert "SPEC section '9. Limits' has no task" in out and "B2" not in out
