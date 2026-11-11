"""#490, #445: the review packet lists render screenshots; the final reviewer opens them."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))

import pt_review  # noqa: E402

LEAD = "Open each image with Read and judge the rendered UI against the spec and the Review Focus:"


def test_render_section_lists_images(tmp_path):
    d = tmp_path / ".superlite" / "render"
    d.mkdir(parents=True)
    for n in ("b.png", "a.jpg", "c.jpeg", "notes.txt"):
        (d / n).write_bytes(b"x")
    text = pt_review.render_section(tmp_path)
    lines = text.strip().splitlines()
    assert lines[0] == "## Render evidence"
    assert lines[1] == LEAD
    assert lines[2:] == [f"- {(d / n).resolve().as_posix()}" for n in ("a.jpg", "b.png", "c.jpeg")]


def test_render_section_caps_at_20(tmp_path):
    d = tmp_path / ".superlite" / "render"
    d.mkdir(parents=True)
    for i in range(25):
        (d / f"s{i:02d}.png").write_bytes(b"x")
    lines = pt_review.render_section(tmp_path).strip().splitlines()
    assert len(lines) == 2 + 20 + 1 and lines[-1] == "- (+5 more not listed)"


def test_render_section_empty(tmp_path):
    assert pt_review.render_section(tmp_path) == ""
    (tmp_path / ".superlite" / "render").mkdir(parents=True)
    (tmp_path / ".superlite" / "render" / "x.txt").write_text("x")
    assert pt_review.render_section(tmp_path) == ""


def test_final_reviewer_names_render_and_import():
    text = (ROOT / "agents" / "final-reviewer.md").read_text(encoding="utf-8")
    for need in ("## Render evidence", "also on the fast path", "import-linter", "package.json"):
        assert need in text, need
    assert "SwiftPM target its `Package.swift` does not list) is not in the packet" not in text
