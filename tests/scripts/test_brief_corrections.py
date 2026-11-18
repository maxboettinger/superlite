"""Project corrections reach the review brief and the review packet (CR3)."""
from __future__ import annotations

import sys

import pytest

from test_fleet import world  # noqa: F401
from test_packet_inline import git, inline, repo, run  # noqa: F401
from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import corrections  # noqa: E402
import fleet_io as fio  # noqa: E402
import pt_review  # noqa: E402

HEAD = "## Corrections (binding, from the user)"
LINES = ["Use uv, never pip", "German UI strings"]


def put(root, lines=LINES):
    p = root / corrections.FILE
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text("# Corrections\n\n" + "".join(f"- {ln}\n" for ln in lines), encoding="utf-8")


def brief(world):
    (world.sd / "progress.md").write_text("- commit T1 abc1234 first\n")
    return fio.review_brief(world.sd, world.plan, ["T1"], "/x/sl", "/x")


def packet(repo, monkeypatch=None, *extra, fn=None):
    """Build an inline packet in-process (so corrections.section can be patched)."""
    if fn is not None:
        monkeypatch.setattr(corrections, "section", fn)
    base = git(repo, "rev-parse", "HEAD")
    out = repo / "packet.md"
    rc = pt_review.main(["packet", "--root", str(repo), "--out", str(out), "--wait-timeout", "1",
                         "--inline", "--spec", str(repo / "spec.md"), "--base", base, *extra])
    assert rc == 0
    return out.read_text(encoding="utf-8")


def test_review_brief_has_corrections(world):
    put(world.proj)
    text = brief(world)
    assert text.count(HEAD) == 1 and "- Use uv, never pip" in text and "- German UI strings" in text


def test_packet_head_has_corrections_after_the_standing_note(repo):
    import backlog_brief as bb
    d = repo / ".superlite" / "briefs"
    d.mkdir(parents=True)
    (d / "lead.md").write_text(f"# Lead\n{bb.NOTE_HEAD}\n    a rule\n", encoding="utf-8")
    put(repo)
    text = inline(repo)
    assert text.count(HEAD) == 1
    assert text.index("## Standing note") < text.index(HEAD) < text.index("## 4. Test summary")


def test_packet_corrections_survive_the_size_cap(repo):
    put(repo, [f"rule number {i} " + "x" * 80 for i in range(12)])
    text = inline(repo, "--max-tokens", "2000")
    assert text.count(HEAD) == 1
    assert all(f"- rule number {i} " in text for i in range(12))


def test_inline_packet_has_corrections(repo):
    put(repo)
    text = inline(repo)
    assert HEAD in text and "- Use uv, never pip" in text


def test_brief_and_packet_without_the_file_are_unchanged(world, repo, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(corrections, "section", lambda root: None)
        b_none = brief(world)
        p_none = packet(repo)
    assert HEAD not in b_none and HEAD not in p_none
    assert brief(world) == b_none and packet(repo) == p_none


def test_a_corrections_error_changes_nothing(world, repo, monkeypatch):
    with monkeypatch.context() as m:
        m.setattr(corrections, "section", lambda root: None)
        b_none, p_none = brief(world), packet(repo)

    def boom(root):
        raise RuntimeError("nope")
    monkeypatch.setattr(corrections, "section", boom)
    assert brief(world) == b_none
    assert packet(repo) == p_none
