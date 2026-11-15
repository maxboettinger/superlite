"""The slim prime lists each stable task's title and Owns only; the standing note drops lines the constraints already print (#914)."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS
from test_slim_prime import make
from test_prime_standing_note_738 import lead

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import build_prime  # noqa: E402
import routing  # noqa: E402


def slim_text(plan, sd=None):
    return build_prime.build_slim(str(plan), sd).decode("utf-8")


def test_slim_prime_lists_title_and_owns_only(tmp_path):
    text = slim_text(make(tmp_path))
    tasks = text.split("## Stable tasks")[1]
    assert "### T1 " in tasks and tasks.count("Owns: ") == 3
    for bad in ("After: T1", "Produces: alpha.Parse", "Consumes: alpha.Parse"):
        assert bad not in tasks
    assert not [ln for ln in tasks.splitlines() if ln.startswith(("After:", "Produces:", "Consumes:"))]
    assert "### T4" not in tasks  # unstable task stays out


def test_slim_prime_points_at_sl_task(tmp_path):
    text = slim_text(make(tmp_path))
    assert "## Stable tasks: titles and files" in text
    assert "(any task id, not only yours)" in text
    assert "purpose, dependencies, interfaces" not in text
    assert "Code to the Consumes and Produces lines of your task (`sl task Tn` prints them)." in text
    assert "interfaces below" not in text


def test_slim_prime_is_smaller(tmp_path):
    plan = make(tmp_path)
    new = slim_text(plan)
    added = new + "After: T1, T2\nProduces: alpha.Parse(text string) (Doc, error)\nConsumes: alpha.Lex(text string) []Tok (T2)\n"
    assert len(new) < len(added)


def test_haiku_prime_keeps_interfaces(tmp_path):
    plan = make(tmp_path)
    old = routing.read_tiers
    routing.read_tiers = lambda _p: {t: "haiku" for t in ("T1", "T2", "T3", "T4")}
    try:
        text = build_prime.build_mini(str(plan), "haiku").decode("utf-8")
    finally:
        routing.read_tiers = old
    assert "Produces: alpha.Parse(text string) (Doc, error)" in text


def test_standing_note_not_printed_twice(tmp_path):
    plan = make(tmp_path)
    sd = lead(tmp_path, f"# Lead\n{bb.NOTE_HEAD}\n    - Never import across packages.\n")
    text = slim_text(plan, sd)
    assert text.count("Never import across packages.") == 1
    assert "- Never import across packages." in text.split("## Global constraints")[1]
    assert "## Standing note" in text and bb.NOTE_HEAD in text
    assert build_prime.note_section(sd, skip=(bb.NOTE_HEAD, "- Never import across packages.")) == ""


def test_standing_note_other_lines_stay(tmp_path):
    plan = make(tmp_path)
    sd = lead(tmp_path, f"# Lead\n{bb.NOTE_HEAD}\n    unrelated rule of main\n")
    text = slim_text(plan, sd)
    assert "## Standing note" in text and "unrelated rule of main" in text
