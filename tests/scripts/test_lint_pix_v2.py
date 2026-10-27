"""Lint false positives from the piX reviewing-periods v2 run: placeholder markers, spec heading prefixes, frozen EXAMPLE hint."""
from __future__ import annotations

from test_plan_tools import SCRIPTS, run
from test_shape import two

TODO, TBD = "TO" + "DO", "T" + "BD"  # built apart so this file itself carries no marker


def lint(plan, *extra):
    return run(SCRIPTS / "plan_tools.py", "lint", "--plan", plan, *extra).out


def with_line(tmp_path, line, name="p.md"):
    p = two(tmp_path, eg=['lang.parse("1") -> Num(1)'], name=name)
    p.write_text(p.read_text(encoding="utf-8").replace("**Goal:** x.", f"**Goal:** x.\n{line}", 1), encoding="utf-8")
    return p


def test_obsidian_callout_not_placeholder(tmp_path):
    p = with_line(tmp_path, f"Global constraints: use the `[!{TODO.lower()}]` callout, never a {TODO.lower()} list as {TBD.lower()}.")
    assert "placeholder" not in lint(p)
    assert "placeholder" not in lint(with_line(tmp_path, f"Keep a {TODO.lower()} list in plain words.", "q.md"))
    assert "placeholder" not in lint(with_line(tmp_path, f"The callout [!{TODO.lower()}] is plain text.", "r.md"))


def test_uppercase_marker_still_flagged(tmp_path):
    assert f"placeholder {TODO}" in lint(with_line(tmp_path, f"{TODO}: fill this in"))


def test_backticked_marker_ignored(tmp_path):
    assert "placeholder" not in lint(with_line(tmp_path, f"Write `{TBD}` where unknown."))
    assert f"placeholder {TBD}" in lint(with_line(tmp_path, f"Details are {TBD}.", "q.md"))


def test_spec_heading_prefixes_exempt(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# S\n\n## Decisions (Max, 2026-10-27)\nx\n\n## Acceptance (countable, on the W44 transcript)\nx\n\n"
                    "## Open for Max\nx\n\n## Validation: manual\nx\n\n## Openers\nx\n", encoding="utf-8")
    out = lint(two(tmp_path, eg=['lang.parse("1") -> Num(1)']), "--spec", spec)
    assert "SPEC section 'Openers' has no task" in out
    assert "SPEC section 'Decisions" not in out and "SPEC section 'Acceptance" not in out
    assert "SPEC section 'Open for Max'" not in out and "SPEC section 'Validation: manual'" not in out


def test_prefix_only_for_process_headings(tmp_path):
    spec = tmp_path / "spec.md"
    spec.write_text("# S\n\n## Status bar\nx\n\n## Background sync\nx\n\n## Decisions (Max, 2026-10-27)\nx\n\n"
                    "## Acceptance (countable)\nx\n\n## Open for Max\nx\n\n## Validation: manual\nx\n", encoding="utf-8")
    out = lint(two(tmp_path, eg=['lang.parse("1") -> Num(1)']), "--spec", spec)
    assert "SPEC section 'Status bar' has no task" in out and "SPEC section 'Background sync' has no task" in out
    for n in ("Decisions", "Acceptance", "Open for Max", "Validation"):
        assert f"SPEC section '{n}" not in out


def test_example_hint_for_frozen_producer(tmp_path):
    p = two(tmp_path)
    assert "EXAMPLE: T2 consumes lang.parse but its Produces line has no e.g.\n" in lint(p) + "\n"
    assert "frozen" not in lint(p)
    sl = tmp_path / ".superlite"
    sl.mkdir()
    (sl / "progress.md").write_text("- unblocked: dispatched T1\n", encoding="utf-8")
    out = lint(p)
    assert ("EXAMPLE: T2 consumes lang.parse but its Produces line has no e.g. "
            "(producer T1 is dispatched and frozen: drop this Consumes entry or move it to a follow-up task)") in out
