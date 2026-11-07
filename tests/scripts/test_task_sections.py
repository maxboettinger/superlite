"""#268: `sl task Tn` prints the plan sections the task block names."""
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import task  # noqa: E402
import plan_tools as pt  # noqa: E402


def mk(sections: str, body: str = "", extra: str = "", tid: str = "T2") -> pt.Plan:
    return pt.Plan(
        f"# Plan\n\n{sections}\n\n## Package\n\n### T1 First\n**Owns:** a.py\n**Produces:** a.f() -> int\n\n"
        f"### {tid} Second\n**Owns:** b.py\n{extra}\n{body}\n"
    )


def secs(plan, tid="T2"):
    return task.referenced_sections(plan, plan.by_id[tid])


def test_multiword_heading_named():
    p = mk('## Shared helper\n`fmt_row(cells) -> str` joins with " | ".', "Use the shared helper fmt_row.")
    out = task.render(p, "T2")
    assert "## Plan sections this task names" in out
    assert '## Shared helper\n`fmt_row(cells) -> str` joins with " | ".' in out


def test_backticks_case_and_number():
    p = mk("### 2. The `fmt_row` Helper:\nbody", "Call the fmt_row helper.")
    assert secs(p) == ["### 2. The `fmt_row` Helper:\nbody"]


def test_plural_either_side():
    assert secs(mk("## Shared helpers\nx", "see shared helper")) == ["## Shared helpers\nx"]
    assert secs(mk("## Shared helper\nx", "see shared helpers")) == ["## Shared helper\nx"]


def test_one_word_needs_explicit_form():
    sec = "## Design\nbody"
    assert secs(mk(sec, extra="**Kind:** design")) == []
    for mention in ("see the Design section", "section Design", "§ Design", "read ## Design now"):
        assert secs(mk(sec, mention)) == [sec], mention


def test_unnamed_section_absent():
    p = mk("## Wire format\nx", "nothing here")
    assert secs(p) == []
    assert "## Plan sections" not in task.render(p, "T2")


def test_skeleton_headings_skipped():
    p = mk("## Review Focus\nrf\n\n## Coverage\ncov", "coverage table", extra="**Review Focus:** state: x")
    assert secs(p) == []


def test_section_ends_at_task_heading():
    p = pt.Plan("## Package A\nShared: X = 1\n\n### T1 One\n**Owns:** a.py\n\n### T2 Two\n**Owns:** b.py\nuse package a\n")
    assert secs(p) == ["## Package A\nShared: X = 1"]


def test_subsection_once_with_parent():
    sec = "## Notes\nintro\n### Retry policy\nthree tries"
    both = secs(mk(sec, "notes section and retry policy"))
    assert both == [sec]
    only = secs(mk(sec, "see retry policy"))
    assert only == ["### Retry policy\nthree tries"]


def test_empty_preamble_skipped():
    p = pt.Plan("## Package B\n### T3 Three\n**Owns:** c.py\nuse package b\n")
    assert secs(p, "T3") == []


def test_fenced_heading_and_mention_ignored():
    p = mk("```\n## Shared helper\nfake\n```", "use shared helper")
    assert secs(p) == []
    p2 = mk("## Shared helper\nreal", "```\nshared helper\n```")
    assert secs(p2) == []


def test_cli_prints_sections(tmp_path, capsys):
    f = tmp_path / "plan.md"
    f.write_text(mk("## Shared helper\nreal text", "uses the shared helper").text)
    assert task.main(["T2", "--plan", str(f)]) == 0
    assert capsys.readouterr().out.endswith("## Shared helper\nreal text\n")


def test_consumed_interfaces_kept():
    p = mk("## Shared helper\nx", "uses the shared helper", extra="**Consumes:** a.f() -> int")
    out = task.render(p, "T2")
    assert out.index("## Consumed interfaces") < out.index("## Plan sections this task names")


def test_section_ends_at_same_or_higher_heading():
    p = mk("## Shared helper\nx\n### Sub\ny\n## Other\nz", "use shared helper")
    assert secs(p) == ["## Shared helper\nx\n### Sub\ny"]
    p = mk("## Top\n### Shared helper\nx\n## Next\nz", "use shared helper")
    assert secs(p) == ["### Shared helper\nx"]


def test_section_runs_to_end_of_plan():
    p = pt.Plan("### T1 One\n**Owns:** a.py\nuse tail notes\n\n## Tail notes\nlast line\n\n")
    assert secs(p, "T1") == ["## Tail notes\nlast line"]
