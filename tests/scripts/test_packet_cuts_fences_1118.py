"""Review packet: every cut carries a marker, every fence outlasts the fences inside it (#1118)."""
import sys
import types
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))
import fleet  # noqa: E402
import fleet_roles  # noqa: E402
import plan_tools  # noqa: E402
import pt_review as pt  # noqa: E402

M = "…"


def mark(n):
    return f"[{M} {n} chars cut {M}]"


def test_cut_mark_and_clip_text():
    assert pt.cut_mark(812) == mark(812)
    s = "abc"
    assert pt.clip_text(s, 3) is s
    assert pt.clip_text("abcdef", 3) == "abc" + mark(3)
    assert pt.clip_text("", 3) == ""


def test_long_changed_span_keeps_head_and_tail_with_a_marker():
    head, tail = "h" * 50, "t" * 50
    old = "-" + head + "A" * 300 + "MIDDLE-OLD" + "B" * 300 + tail
    new = "+" + head + "C" * 300 + "MIDDLE-NEW" + "D" * 300 + tail
    a, b = pt.clip_diff_lines([old, new])
    note = " [line of 710 chars, changed at col 51; read the file for the rest]"
    assert a == "-" + head + "A" * 200 + mark(210) + "B" * 200 + tail + note
    assert b == "+" + head + "C" * 200 + mark(210) + "D" * 200 + tail + note


def test_markers_only_where_text_was_cut():
    a, b = pt.clip_diff_lines(["-" + "x" * 500, "+" + "x" * 500 + "tail"])
    assert a == "-" + mark(380) + "x" * 120 + " [line of 500 chars, changed at col 501; read the file for the rest]"
    assert b == "+" + mark(380) + "x" * 120 + "tail" + " [line of 504 chars, changed at col 501; read the file for the rest]"


def test_tail_marker_counts_the_chars_after_the_context():
    a, b = pt.clip_diff_lines(["-" + "a" * 10 + "OLD" + "z" * 500, "+" + "a" * 10 + "NEW" + "z" * 500])
    note = " [line of 513 chars, changed at col 11; read the file for the rest]"
    assert a == "-" + "a" * 10 + "OLD" + "z" * 120 + mark(380) + note
    assert b == "+" + "a" * 10 + "NEW" + "z" * 120 + mark(380) + note


def test_excerpt_marks_a_cut_row(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\n" + "y" * 200 + "\n", encoding="utf-8")
    rows = pt.excerpt(tmp_path, "a.py", 2).splitlines()
    assert rows[0] == "    1 | x = 1"
    assert rows[1] == ">   2 | " + "y" * 160 + mark(40)


def test_fence_outlasts_inner_fences():
    assert pt.fence("+a") == "```\n+a\n```"
    assert pt.fence("+a", "diff") == "```diff\n+a\n```"
    body = " ```bash\n+ls x\n ```"
    assert pt.fence(body, "diff") == "````diff\n" + body + "\n````"
    assert pt.fence("+a", "diff", 5) == "`````diff\n+a\n`````"
    assert pt.fence_width(["a", "b``c"]) == 3
    assert pt.fence_width(["+ use ```x``` here", " ````"]) == 5
    assert pt.fence_width([]) == 3


@pytest.fixture
def roots(tmp_path, monkeypatch):
    proj = tmp_path / "proj"; sd = proj / ".superlite"; sd.mkdir(parents=True)
    skills = tmp_path / "plug" / "skills"; skills.mkdir(parents=True)
    other = tmp_path / "other"; other.mkdir(); (other / "spec.md").write_text("spec")
    monkeypatch.setattr(fleet_roles, "SKILLS", skills)
    return types.SimpleNamespace(proj=proj, sd=sd, other=other)


def test_readme_diff_with_fences_stays_fenced(roots):
    o = roots.other
    lines = ["--- a/README.md", "+++ b/README.md", "@@ -1,4 +1,4 @@", " ```bash",
             f"-cat {o}/old.md", f"+cat {o}/spec.md", " ```", f" see {o}/spec.md"]
    text = pt.render_excerpts(["README.md"], [("README.md", lines)])
    assert text == "### README.md\n````diff\n" + "\n".join(lines) + "\n````"
    assert fleet.outside_paths("Packet:\n" + text + "\nEnd of packet\n", roots.proj, roots.sd) == []
    flags, _ = plan_tools.scan_fences(text.splitlines())
    assert flags == [False] + [True] * (len(lines) + 2)


def test_overhead_charges_the_wider_fence():
    plain = pt.excerpt_need([("R.md", [" ...."])])
    wide = pt.excerpt_need([("R.md", [" ````"])])
    assert wide - plain == 4


def test_budgeted_excerpts_with_inner_fences_fit():
    diffs = [(f"d{i}.md", [" ```bash", "+x" * 40, " ```"] * 6) for i in range(4)]
    changed = [f for f, _ in diffs]
    for budget in (300, 700, 2000):
        out = pt.render_excerpts(changed, diffs, budget=budget)
        assert len(out) <= budget, budget


def test_item_excerpt_uses_fence(tmp_path):
    (tmp_path / "R.md").write_text("````\nx\n````\n", encoding="utf-8")
    it = pt.Item("incidents", (0,), "R.md:2 x", "", "R.md", 2, "", False)
    out = pt.render_item(tmp_path, it, set(), "1.1")
    assert "\n`````\n" in out and out.rstrip().endswith("`````")
