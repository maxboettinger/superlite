# tests/scripts/test_backlog_brief_lean_683.py
import subprocess
import sys

import pytest
from test_plan_tools import SCRIPTS, pt
sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import run_config  # noqa: E402

CTX = {"sl": "/x/sl", "repo": "o/r", "backlog_md": "/x/backlog.md", "titles": {"7": "Seven", "8": "Eight"}, "summaries": [],
       "approved": {"by": "AskUserQuestion", "time": "t"}}
ONE = {"id": "B1", "topic": "t", "issues": [7], "files": ["a.py"], "decisions": []}
TAIL = "superlite:subagent-driven-development with fleet on"
OLD_HEAD = "Build: superlite:brainstorming"


def brief(batch=ONE, text="lean", **kw):
    return bb.lead_brief(batch, {**CTX, "text": text, **kw})


def test_variants_accept_lean():
    cfg = run_config.load_text('{"configs": {"x": {"lead": {"text": "lean"}}}}')
    assert cfg["configs"]["x"]["lead"]["text"] == "lean"
    with pytest.raises(run_config.ConfigError, match="short is not one of default, lean"):
        run_config.load_text('{"configs": {"x": {"lead": {"text": "short"}}}}')


def test_lead_variant_examples():
    assert bb.lead_variant(ONE, {"text": "lean"}) == "lean"
    assert bb.lead_variant({**ONE, "issues": [7, 8]}, {"text": "lean"}) == "default"
    assert bb.lead_variant(ONE, {"text": "default"}) == "default"


def test_lean_one_issue():
    t = brief()
    assert bb.LEAN_BUILD.format(sl='/x/sl') in t and OLD_HEAD not in t


def test_lean_two_issues_full():
    t = brief({**ONE, "issues": [7, 8]})
    assert OLD_HEAD in t and bb.LEAN_BUILD.format(sl='/x/sl') not in t


def test_lean_decisions_full():
    t = brief({**ONE, "decisions": [{"questions": ["q?"]}]})
    assert OLD_HEAD in t and bb.LEAN_BUILD.format(sl='/x/sl') not in t


def test_default_byte_identical_tail():
    lean, full = brief(), brief(text="default")
    assert lean != full
    assert lean.split(TAIL, 1)[1] == full.split(TAIL, 1)[1]
    assert lean.split(TAIL, 1)[0] != full.split(TAIL, 1)[0]


@pytest.mark.parametrize("text", ["lean", "default"])
def test_both_variants_code_rule(text):
    t = brief(text=text)
    lines = t.splitlines()
    i = next(n for n, ln in enumerate(lines) if ln.startswith("First:"))
    assert lines[i + 1] == bb.CODE_RULE.format(sl='/x/sl')
    assert "verify" not in bb.CODE_RULE.lower()


@pytest.mark.parametrize("text", ["lean", "default"])
def test_wave_wait_line(text):
    t = brief(text=text)
    assert "fleet wait --wave --timeout 540000 --plan .superlite" in t
    assert "--tests <summary path>" in t
    assert "(`sleep`, `until grep`) is a defect" in t
    assert "Never end your turn while your workers run" in t


def test_layered_default_picks_lean(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "run-configs.json").write_text('{"default": "l", "configs": {"l": {"lead": {"text": "lean"}}}}', encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    wt = tmp_path / ".claude" / "worktrees" / "b1-x"
    wt.mkdir(parents=True)
    ctx = {k: v for k, v in CTX.items()}
    assert bb.lead_variant(ONE, {**ctx, "worktree": str(wt)}) == "lean"
    assert bb.lead_variant(ONE, ctx) == "lean"


def test_bad_machine_file_is_default(tmp_path, monkeypatch):
    home = tmp_path / "home"
    home.mkdir()
    (home / "run-configs.json").write_text("[1]", encoding="utf-8")
    monkeypatch.setenv("SUPERLITE_HOME", str(home))
    assert bb.lead_variant(ONE, dict(CTX)) == "default"


def test_lean_plan_fields_lint(tmp_path):
    subprocess.run(["git", "init", "-q", str(tmp_path)], check=True)
    plan = tmp_path / "plan.md"
    plan.write_text("\n".join([
        "# Lean plan", "**Goal:** fix it.", "**Tech stack:** Python", f"**Spec:** {tmp_path / 'plan.md'}",
        "**Wave0:** none", "**Worktree:** none", "**Coverage:** off", "",
        "```mermaid", "%% taskgraph", "flowchart LR", "  T1", "```", "",
        "### T1 fix a · Complexity 2 (O-1) · Est. context 20k",
        "**Owns:** pkg/a.py, tests/test_a.py", "**Components:** 1", "**LOC owned:** 30", "**Tests:** fast",
        "**Kind:** mechanical", "**Model:** haiku", "",
        "test_a: a(1) == 2.", ""]), encoding="utf-8")
    cp = pt("lint", "--plan", plan, "--spec", plan, "--stable", cwd=tmp_path)
    assert "DISPATCH NOW: T1" in cp.out, cp.both
