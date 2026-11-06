"""parse_plan must ignore task headings and field lines inside code fences:
a verbatim test embedding a mini plan must not replace the real task (#263)."""
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import next_tasks  # noqa: E402


def plan(tmp_path, text):
    p = tmp_path / "plan.md"
    p.write_text(text, encoding="utf-8")
    return p


MINI_PLAN = """### T1 parser
**Owns:** src/a.py
Est. time: 2 min
Verbatim test embedding a mini plan:
```
### T1 fake
**Owns:** other/fake.py
Est. time: 9 min
```
"""


def test_fenced_heading_and_field_do_not_replace_the_task(tmp_path):
    info = next_tasks.parse_plan(plan(tmp_path, MINI_PLAN))
    assert list(info) == ["T1"]
    assert info["T1"]["title"] == "parser"
    assert info["T1"]["owns"] == ["src/a.py"]
    assert info["T1"]["est_time"] == 2.0


def test_fenced_ownsn_does_not_make_prose_a_task(tmp_path):
    text = "### S3 storage\n\nExample block:\n```\n**Owns:** x.py\n```\n"
    assert next_tasks.parse_plan(plan(tmp_path, text)) == {}


def test_fields_outside_fences_still_parse(tmp_path):
    text = "### T1 parser\n**Owns:** src/a.py\n\n```\nplain notes\n```\n**Est. time:** 3 min\n"
    info = next_tasks.parse_plan(plan(tmp_path, text))
    assert info["T1"]["owns"] == ["src/a.py"]
    assert info["T1"]["est_time"] == 3.0
