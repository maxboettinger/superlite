"""#941: `sl task` stops when an unclosed code fence hides task headings."""
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import task  # noqa: E402
import plan_tools as pt  # noqa: E402

CLOSED = "# Plan\n\n### T1 a\n**Owns:** a.py\n```python\nx = 1\n```\n\n### T2 b\n**Owns:** b.py\n```python\ny = 2\n```\n"
OPEN = "# Plan\n\n### T1 a\n**Owns:** a.py\n```python\nx = 1\n\n### T2 b\n**Owns:** b.py\n\n### T3 c\n**Owns:** c.py\n"
NOHEAD = "# Plan\n\n### T1 a\n**Owns:** a.py\n\n### T2 b\n**Owns:** b.py\n```python\nx = 1\n"


def test_hidden_tasks_none_for_closed_plan():
    assert pt.hidden_tasks(pt.Plan(CLOSED)) is None


def test_hidden_tasks_names_fence_line_and_ids():
    assert pt.hidden_tasks(pt.Plan(OPEN)) == (5, ["T2", "T3"])


def test_unclosed_fence_without_headings_is_none():
    assert pt.hidden_tasks(pt.Plan(NOHEAD)) is None


def test_task_cli_exits_2_for_every_id(tmp_path, capsys):
    p = tmp_path / "plan.md"
    p.write_text(OPEN, encoding="utf-8")
    for tid in ("T1", "T2"):
        assert task.main([tid, "--plan", str(p)]) == 2
        cap = capsys.readouterr()
        assert cap.out == ""
        assert "line 5" in cap.err and "never closed" in cap.err and "T2, T3" in cap.err


def test_task_cli_prints_block_for_closed_plan(tmp_path, capsys):
    p = tmp_path / "plan.md"
    p.write_text(CLOSED, encoding="utf-8")
    assert task.main(["T1", "--plan", str(p)]) == 0
    assert capsys.readouterr().out.startswith("### T1")
