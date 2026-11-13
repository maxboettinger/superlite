"""The final-review packet carries the standing note of briefs/lead.md, never cut by the token cap (#738)."""
from __future__ import annotations

import sys

from test_packet_inline import git, inline, repo, run  # noqa: F401
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import backlog_brief as bb  # noqa: E402

L1, L2 = "    first rule of main", "    second rule of main"


def lead(repo):
    d = repo / ".superlite" / "briefs"
    d.mkdir(parents=True, exist_ok=True)
    (d / "lead.md").write_text(f"# Lead\n{bb.NOTE_HEAD}\n{L1}\n{L2}\nother\n", encoding="utf-8")


def test_packet_carries_standing_note(repo):
    lead(repo)
    text = inline(repo)
    assert text.count("## Standing note") == 1
    assert text.count(L1) == 1 and text.count(L2) == 1
    assert text.index("# Review packet") < text.index("## Standing note") < text.index("## 4. Test summary")


def test_packet_note_survives_token_cap(repo):
    lead(repo)
    text = inline(repo, "--max-tokens", "300")
    assert text.count("## Standing note") == 1 and L1 in text and L2 in text


def test_packet_without_note_unchanged(repo):
    plain = inline(repo)
    (repo / ".superlite" / "briefs").mkdir(parents=True)
    (repo / ".superlite" / "briefs" / "lead.md").write_text("# Lead\nno note\n", encoding="utf-8")
    again = inline(repo)
    assert "Standing note" not in plain and again == plain
