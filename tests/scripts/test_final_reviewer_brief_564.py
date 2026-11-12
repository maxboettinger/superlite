"""#564: a final reviewer whose brief names files to read or a search to run does it; the packet stays the default."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
REVIEWER = (ROOT / "agents" / "final-reviewer.md").read_text(encoding="utf-8")
AGENTS_DOC = (ROOT / "docs" / "skills-and-agents.md").read_text(encoding="utf-8")

R_BRIEF = ("- Your brief (the message, or the brief file sent as your packet) may name files to read or a search to run: "
           "read each named file, one Read each, and run each named search with Grep or Glob, also on the fast path, "
           "each with a `Checked:` line. A brief that names them overrides `nothing else` for exactly those; "
           "never answer that your role forbids them.")


def _frontmatter_description() -> str:
    head = REVIEWER.split("---", 2)[1]
    return next(ln for ln in head.splitlines() if ln.startswith("description:"))


def test_description_names_brief_files():
    desc = _frontmatter_description()
    assert "files its brief names" in desc
    assert "alone" not in desc


def test_brief_rule_follows_the_read_paragraph():
    lines = REVIEWER.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("Read `.superlite/review-packet.md` whole"))
    assert lines[i + 2] == R_BRIEF
    assert "no searching, no other reads" not in REVIEWER
    assert "Answer in one turn: no other searches or reads." in lines[i]


def test_checked_lines_cover_brief_files_and_searches():
    checked = next(ln for ln in REVIEWER.splitlines() if ln.startswith("After the findings, add `Checked:`"))
    assert "per brief file or search (`src/a.py: read`)" in checked


def test_contract_still_holds():
    assert "nothing else" in REVIEWER and "read <path> in full" in REVIEWER and "may read" in REVIEWER
    assert "tools: Read, Grep, Glob" in REVIEWER and "$SL" not in REVIEWER


def test_agents_doc_names_brief_files():
    line = next(ln for ln in AGENTS_DOC.splitlines() if ln.startswith("- `final-reviewer`"))
    assert "reads only the review packet" not in line
    assert "the review packet and any file or search its brief names" in line
