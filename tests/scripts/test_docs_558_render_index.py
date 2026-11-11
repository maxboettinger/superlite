"""#558: docs/tools.md names the optional .superlite/render/index.md."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
TOOLS = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
NEW = ("with an optional `<run root>/.superlite/render/index.md` that names at least one image there (one line per "
       "current image: an optional list marker, the file name, optionally in backticks, then nothing or `:`, ` - ` or "
       "` — ` and its caption; other lines are ignored) it lists only those images in index order as "
       "`- <path>: <caption>` (first mention wins, a caption over 200 characters cut to 197 plus `...`), then "
       "`- (N other images not named in index.md, not listed)`")
OLD = "image under `<run root>/.superlite/render/` (sorted by name, at most 20, then `- (+N more not listed)`) after the line"


def test_pt_review_row_names_render_index():
    row = next(ln for ln in TOOLS.splitlines() if ln.startswith("| `pt_review` |"))
    assert NEW in row
    assert "`- (index.md names files not found: <names>)`" in row
    assert OLD not in row
