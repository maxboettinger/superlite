import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))

import next_tasks  # noqa: E402
import plan_tools as pt  # noqa: E402
import task  # noqa: E402

HEAD = "# Plan\n**Tech stack:** Python\n\nGlobal constraints:\n- stdlib only.\n- No version edits.\n\n## Design\nbody\n\n## Package\n\n"
TASKS = (
    "### T1 First\n**Owns:** a.py\n**Produces:** a.f() -> int\n\n"
    "### T2 Second\n**Owns:** b.py\n**Consumes:** a.f() -> int (T1)\nsee the Design section\n"
)


def test_constraints_appended_always():
    out = task.render(pt.Plan(HEAD + TASKS), "T1")
    assert out.endswith(
        "## Global constraints\n\n**Tech stack:** Python\nGlobal constraints:\n- stdlib only.\n- No version edits.\n"
    )


def test_order_of_parts():
    out = task.render(pt.Plan(HEAD + TASKS), "T2")
    a, b, c = (out.index(x) for x in ("## Consumed interfaces", "## Plan sections this task names", "## Global constraints"))
    assert a < b < c


def test_constraints_section_form():
    text = "# Plan\n\n## Global constraints\n- Numbers are float64.\n\n### T1 First\n**Owns:** a.py\nobey the global constraints\n"
    p = pt.Plan(text)
    out = task.render(p, "T1")
    assert out.count("## Global constraints\n\n- Numbers are float64.\n") == 1
    assert task.referenced_sections(p, p.by_id["T1"]) == []


def test_no_constraints_no_block():
    p = pt.Plan("# Plan\n\n### T1 First\n**Owns:** a.py\n")
    assert "## Global constraints" not in task.render(p, "T1")


def test_ref_line_names_section_once():
    text = HEAD + "### T1 First\n**Owns:** a.py\n\n### T2 Second\n**Owns:** b.py\n## Design\n**Steps:** x\n"
    p = pt.Plan(text)
    assert "**Steps:** x" in task.render(p, "T2")
    assert task.referenced_sections(p, p.by_id["T2"]) == ["## Design\nbody"]


def test_next_tasks_keeps_fields_after_ref(tmp_path):
    f = tmp_path / "plan.md"
    f.write_text("# P\n\n## Design\nbody\n\n### T1 First\n**Owns:** a.py\n\n### T2 Second\n**Kind:** design\n## Design\n**Owns:** b.py\n")
    assert next_tasks.parse_plan(f)["T2"]["owns"] == ["b.py"]
    assert pt.Plan.load(str(f)).by_id["T2"].owns == ["b.py"]


def test_next_tasks_plain_plan_unchanged(tmp_path):
    f = tmp_path / "plan.md"
    f.write_text(HEAD + TASKS)
    got = next_tasks.parse_plan(f)
    assert list(got) == ["T1", "T2"]
    assert got["T1"]["owns"] == ["a.py"] and got["T2"]["owns"] == ["b.py"]


def test_docs_name_the_block():
    sk = (ROOT / "skills" / "writing-plans" / "SKILL.md").read_text()
    assert "`sl task` appends them" in sk and "Task briefs point here" not in sk
    row = [ln for ln in (ROOT / "docs" / "tools.md").read_text().split("\n") if ln.startswith("| `task`")][0]
    assert "Global constraints" in row
