"""#558: the packet's Render evidence reads .superlite/render/index.md and lists only the current images."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))

import pt_review  # noqa: E402

LEAD = "Open each image with Read and judge the rendered UI against the spec and the Review Focus:"


def shots(tmp_path, *names):
    d = tmp_path / ".superlite" / "render"
    d.mkdir(parents=True)
    for n in names:
        (d / n).write_bytes(b"x")
    return d


def p(d, n):
    return (d / n).resolve().as_posix()


def body(tmp_path):
    return pt_review.render_section(tmp_path).strip().splitlines()


def test_read_render_index_examples(tmp_path):
    (tmp_path / "index.md").write_text("# Shots\n- `b.png` - after fix\n1. a.png\n", encoding="utf-8")
    assert pt_review.read_render_index(tmp_path) == [("b.png", "after fix"), ("a.png", "")]
    assert pt_review.read_render_index(tmp_path / "nowhere") == []


def test_index_lists_only_named_images_in_index_order_with_captions(tmp_path):
    d = shots(tmp_path, "a-before.png", "b-after.png", "c-detail.jpg")
    (d / "index.md").write_text("# Current shots\n\nSome prose.\n- c-detail.jpg: settings sheet at 390pt\n"
                                "- `b-after.png` - login after the fix\n", encoding="utf-8")
    assert body(tmp_path) == ["## Render evidence", LEAD,
                              f"- {p(d, 'c-detail.jpg')}: settings sheet at 390pt",
                              f"- {p(d, 'b-after.png')}: login after the fix",
                              "- (1 other image not named in index.md, not listed)"]


def test_index_entry_without_caption_and_duplicates(tmp_path):
    d = shots(tmp_path, "a.png", "b.png")
    (d / "index.md").write_text("a.png\n* a.png: second mention ignored\n1. b.png — dark mode\n", encoding="utf-8")
    assert body(tmp_path)[2:] == [f"- {p(d, 'a.png')}", f"- {p(d, 'b.png')}: dark mode"]


def test_index_name_with_spaces(tmp_path):
    d = shots(tmp_path, "Screen Shot 1.PNG", "old.png")
    (d / "index.md").write_text("+ Screen Shot 1.PNG: home tab\n", encoding="utf-8")
    assert body(tmp_path)[2:] == [f"- {p(d, 'Screen Shot 1.PNG')}: home tab",
                                  "- (1 other image not named in index.md, not listed)"]


def test_index_names_missing_file(tmp_path):
    d = shots(tmp_path, "a.png")
    (d / "index.md").write_text("- a.png: home\n- gone.png: deleted shot\n", encoding="utf-8")
    assert body(tmp_path)[2:] == [f"- {p(d, 'a.png')}: home", "- (index.md names files not found: gone.png)"]


def test_index_without_existing_image_falls_back_to_all(tmp_path):
    d = shots(tmp_path, "b.png", "a.png")
    (d / "index.md").write_text("Notes only, no file names here.\n- gone.png: old\n- sub/a.png: nested\n", encoding="utf-8")
    assert body(tmp_path)[2:] == [f"- {p(d, 'a.png')}", f"- {p(d, 'b.png')}",
                                  "- (index.md names files not found: gone.png)"]


def test_index_caps_at_20(tmp_path):
    names = [f"s{i:02d}.png" for i in range(23)]
    d = shots(tmp_path, *names, "old.png")
    (d / "index.md").write_text("".join(f"- {n}: shot {n}\n" for n in names), encoding="utf-8")
    lines = body(tmp_path)
    assert len(lines) == 2 + 20 + 2
    assert lines[21] == f"- {p(d, 's19.png')}: shot s19.png"
    assert lines[-2:] == ["- (+3 more not listed)", "- (1 other image not named in index.md, not listed)"]


def test_index_caption_cut_at_200(tmp_path):
    d = shots(tmp_path, "a.png", "b.png")
    (d / "index.md").write_text("- a.png: " + "x" * 300 + "\n- b.png: " + "y" * 200 + "\n", encoding="utf-8")
    assert body(tmp_path)[2:] == [f"- {p(d, 'a.png')}: " + "x" * 197 + "...", f"- {p(d, 'b.png')}: " + "y" * 200]


def test_index_counts_other_images_plural(tmp_path):
    shots(tmp_path, "a.png", "b.png", "c.png")
    (tmp_path / ".superlite" / "render" / "index.md").write_text("- c.png: final\n", encoding="utf-8")
    assert body(tmp_path)[-1] == "- (2 other images not named in index.md, not listed)"


def test_index_only_no_images_gives_empty(tmp_path):
    d = tmp_path / ".superlite" / "render"
    d.mkdir(parents=True)
    (d / "index.md").write_text("- a.png: gone\n", encoding="utf-8")
    assert pt_review.render_section(tmp_path) == ""


def test_index_bad_bytes_and_directory(tmp_path):
    d = shots(tmp_path, "a.png", "b.png")
    (d / "index.md").write_bytes(b"- b.png: caf\xe9\n")
    assert body(tmp_path)[2:] == [f"- {p(d, 'b.png')}: caf�",
                                  "- (1 other image not named in index.md, not listed)"]
    (d / "index.md").unlink()
    (d / "index.md").mkdir()
    assert body(tmp_path)[2:] == [f"- {p(d, 'a.png')}", f"- {p(d, 'b.png')}"]
