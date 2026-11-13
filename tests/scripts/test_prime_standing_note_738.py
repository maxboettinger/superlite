"""Every prime kind carries the standing note of briefs/lead.md once (#738)."""
from __future__ import annotations

import sys

from test_plan_tools import SCRIPTS
from test_slim_prime import make

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402
import build_prime  # noqa: E402
import routing  # noqa: E402

L1, L2 = "    first rule of main", "    second rule of main"


def lead(root, text):
    (root / ".superlite" / "briefs").mkdir(parents=True, exist_ok=True)
    (root / ".superlite" / "briefs" / "lead.md").write_text(text, encoding="utf-8")
    return root / ".superlite"


def kinds(plan, sd):
    old = routing.read_tiers
    routing.read_tiers = lambda _p: {t: "haiku" for t in ("T1", "T2", "T3", "T4")}
    try:
        return [build_prime.build_slim(str(plan), sd), build_prime.build(str(plan), None, [], sd), build_prime.build_mini(str(plan), "haiku", sd)]
    finally:
        routing.read_tiers = old


def test_slim_full_mini_carry_the_note(tmp_path):
    plan = make(tmp_path)
    sd = lead(tmp_path, f"# Lead\n{bb.NOTE_HEAD}\n{L1}\n{L2}\nother\n")
    for data in kinds(plan, sd):
        text = data.decode("utf-8")
        assert text.count("## Standing note") == 1
        assert text.count(L1) == 1 and text.count(L2) == 1
        assert text.index("Rules:") < text.index("## Standing note")


def test_no_lead_md_prime_unchanged(tmp_path):
    plan = make(tmp_path)
    sd = tmp_path / ".superlite"
    without = kinds(plan, sd)
    lead(tmp_path, "# Lead\nno note line here\n")
    assert kinds(plan, sd) == without
    assert all(b"Standing note" not in x for x in without)


def test_note_section_text(tmp_path):
    sd = lead(tmp_path, f"{bb.NOTE_HEAD}\n{L1}\n")
    assert build_prime.note_section(sd) == f"## Standing note\n\n{bb.NOTE_HEAD}\n{L1}"
    assert build_prime.note_section(tmp_path / "none") == ""
