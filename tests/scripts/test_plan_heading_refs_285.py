import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import plan_tools as pt  # noqa: E402

PLAN = (
    "# Plan\n\n## Design\nUse X = 1.\n\n## Package\n\n### T1 First\n**Owns:** a.py\nFollow\n"
    "## Design\n**Steps:** do it\n**Produces:** a.f() -> int\n\n### T2 Second\n**Owns:** b.py\n"
)


def test_ref_line_keeps_task_fields():
    p = pt.Plan(PLAN)
    assert p.refs == {10}
    t1, t2 = p.by_id["T1"], p.by_id["T2"]
    assert t1.fields["owns"] == ["a.py"]
    assert t1.fields["produces"] == ["a.f() -> int"]
    assert "## Design" in t1.text and "**Steps:** do it" in t1.text
    assert t2.fields["owns"] == ["b.py"]


def test_ref_to_later_section():
    text = (
        "# P\n\n### T1 First\n**Owns:** a.py\n## Wire format\n**Steps:** s\n\n### T2 Second\n**Owns:** b.py\n\n"
        "## Wire format\nbytes\n"
    )
    p = pt.Plan(text)
    assert "**Steps:** s" in p.by_id["T1"].text
    assert p.lines.index("## Wire format", 6) not in p.refs
    assert p.refs == {4}


def test_heading_phrase_normalizes():
    assert pt.heading_phrase("2. The `fmt_row` Helper:") == "the fmt_row helper"
    assert pt.heading_phrase("**Design**") == "design"
    assert pt.heading_phrase("1.2 Wire  format") == "wire format"
    assert pt.ref_headings(["## Design", "x", "### T1 A", "**Owns:** a.py", "## Design", "**Steps:** s"], [False] * 6) == {4}
    text = "### 3. Design:\nx\n\n### T1 A\n**Owns:** a.py\n## design\n**Steps:** s\n"
    p = pt.Plan(text)
    assert 5 in p.refs


def test_unrepeated_heading_ends_task():
    p = pt.Plan("### T1 A\n**Owns:** a.py\n### Task 5: c\n**Owns:** c.py\n")
    assert p.refs == set()
    assert p.by_id["T1"].fields["owns"] == ["a.py"]


def test_repeat_without_task_field_ends_task():
    text = (
        "## Parser\nx\n\n### T1 First\n**Owns:** a.py\n\n## Parser\nParser package.\n**Probe entry:** call=x.parse\n\n"
        "### T2 Second\n**Owns:** b.py\n"
    )
    p = pt.Plan(text)
    assert 6 not in p.refs
    t1 = p.by_id["T1"]
    assert "Parser package." not in t1.text
    assert "probe entry" not in t1.fields


def test_fenced_lines_ignored():
    base = "## Design\nx\n\n### T1 A\n**Owns:** a.py\n## Design\n```\n**Steps:** s\n```\n### T2 B\n**Owns:** b.py\n"
    assert pt.Plan(base).refs == set()
    ok = base.replace("```\n### T2", "```\n**Steps:** s\n### T2")
    assert pt.Plan(ok).refs == {5}
    fenced = "## Design\nx\n\n### T1 A\n**Owns:** a.py\n```\n## Design\n**Steps:** s\n```\n"
    assert pt.Plan(fenced).refs == set()


def test_consecutive_refs():
    text = (
        "## Design\nx\n\n## Wire format\ny\n\n### T1 A\n**Owns:** a.py\n## Design\n## Wire format\n**Steps:** s\n"
    )
    p = pt.Plan(text)
    assert {8, 9} <= p.refs
    assert "**Steps:** s" in p.by_id["T1"].text


def test_level_one_and_four_unchanged():
    text = "# Design\n\n#### Design\n\n### T1 A\n**Owns:** a.py\n# Design\n#### Design\n**Steps:** s\n"
    p = pt.Plan(text)
    assert p.refs == set()
    assert "**Steps:** s" not in p.by_id["T1"].text


def test_plain_plan_unchanged():
    p = pt.Plan(PLAN.replace("Follow\n## Design\n", ""))
    assert p.refs == set()
    assert [t.id for t in p.tasks] == ["T1", "T2"]
    assert p.by_id["T1"].fields["owns"] == ["a.py"]
    assert p.by_id["T1"].fields["produces"] == ["a.f() -> int"]
    assert p.by_id["T1"].text == "### T1 First\n**Owns:** a.py\n**Steps:** do it\n**Produces:** a.f() -> int\n"
    assert p.by_id["T2"].text == "### T2 Second\n**Owns:** b.py\n"


def test_pt_review_parse_keeps_fields_after_ref(tmp_path):
    import pt_review

    f = tmp_path / "p.md"
    f.write_text(PLAN, encoding="utf-8")
    t1 = pt_review.parse_plan(f).tasks["T1"]
    assert t1.fields["owns"] == ["a.py"]
    assert t1.fields["produces"] == ["a.f() -> int"]
