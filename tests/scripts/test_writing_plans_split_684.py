"""The writing-plans split (#684): no rule sentence lost, a small core, stale lines fixed.

The fixture holds the sentences of the pre-split SKILL.md. It changes only for the
sentences the split rewrites: "Follow all six rules" (now seven, naming split.md),
the "Who decides sets the mode" link (now "Who orchestrates sets the mode"), and the
probe part's MCP sentence, and the moved review step 4 ("in the order of `SKILL.md`
Plan shape" instead of "in the order below").
"""
import re
from pathlib import Path

from _fixtures import FIXTURES  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]
WP = ROOT / "skills" / "writing-plans"
FIXTURE = FIXTURES / "rules_684" / "writing_plans.txt"
MARK = re.compile(r"^\s*(?:#+\s+|[-*]\s+|\d+[a-z]?\.\s+)")
SPLIT = re.compile(r"(?<=[.!?])\s+(?=[A-Z`\"(*\[])")


def rule_sentences(text):
    out = set()
    for line in text.splitlines():
        line = MARK.sub("", line)
        if not line.strip() or line.strip() == "---":
            continue
        for part in SPLIT.split(line):
            part = " ".join(part.split())
            if len(part) >= 12:
                out.add(part)
    return out


def read(name):
    return (WP / name).read_text()


def test_no_plan_rule_lost():
    want = {l for l in FIXTURE.read_text().splitlines() if l.strip()}
    have = set()
    for n in ("SKILL.md", "task-template.md", "probe-plan.md", "split.md", "review-plan.md"):
        have |= rule_sentences(read(n))
    assert not want - have, sorted(want - have)


def test_core_under_12_kb():
    assert len((WP / "SKILL.md").read_bytes()) < 12000


def test_core_names_each_side_file():
    core = read("SKILL.md")
    for n in ("task-template.md", "probe-plan.md", "split.md", "review-plan.md"):
        assert n in core


def test_side_files_hold_their_parts():
    assert "| `Owns` |" in read("task-template.md")
    assert "| App type | Generic categories |" in read("probe-plan.md")
    split = read("split.md")
    assert "**Interface stubs in Wave 0.**" in split
    assert "**Contract examples.**" in split
    assert "orchestrator approve --review" in read("review-plan.md")


def test_mcp_sentence_says_what_code_does():
    for p in list(WP.glob("*.md")) + [ROOT / "docs" / "simulator-limits.md"]:
        assert "fleet workers start without" not in p.read_text(), p
    probe = read("probe-plan.md")
    assert "implementer, fixer or package-reviewer" in probe
    assert "xcode" in probe


def test_review_plan_steps_unindented_and_step4_names_plan_shape():
    text = read("review-plan.md")
    assert not re.search(r"^ +\d\. ", text, re.M)
    assert "in the order below" not in text
    assert "in the order of `SKILL.md` Plan shape" in text


def test_moved_rule_pointers_name_probe_plan():
    """F-T3-2/F-T3-3: self-review 6 and the Review Focus row point at probe-plan.md.

    The fixture lines for both sentences follow the rewrite.
    """
    core = read("SKILL.md")
    assert "no runnable entry, see `probe-plan.md`)" in core
    assert "no runnable entry, see above" not in core
    tmpl = read("task-template.md")
    assert "(see `probe-plan.md`)" in tmpl
    assert "(see below)" not in tmpl
