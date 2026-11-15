"""#851: review-plan.md allows one `## Key code changes` section (1 to 4 snippets of at most 15 lines), and its own example passes review-plan lint."""
import re
import subprocess
import sys
from pathlib import Path

from test_plan_tools import SCRIPTS

ROOT = Path(__file__).resolve().parents[2]
DOC = ROOT / "skills" / "writing-plans" / "review-plan.md"


def doc():
    return DOC.read_text(encoding="utf-8")


def example():
    m = re.search(r"^````markdown\n(.*?)^````$", doc(), re.S | re.M)
    assert m, "review-plan.md lost its ````markdown example"
    return m.group(1)


def test_required_sections_name_key_code_changes_with_caps():
    text = doc()
    item = re.search(r"^5\. `## Key code changes`.*$", text, re.M)
    assert item, "no item 5 `## Key code changes` in Required sections"
    assert "1 to 4" in item.group(0) and "15 lines" in item.group(0)
    assert text.index("`## How it fits together`") < item.start() < text.index("`## How it gets built`")


def test_do_not_list_keeps_code_out_elsewhere():
    rule = next(l for l in doc().splitlines() if l.startswith("- No ") and "taskgraph" in l)
    assert rule.startswith("- No code outside `## Key code changes`"), rule


def test_step_one_names_the_lint_command():
    assert "run `sl plan_tools lint --plan <path>`" in doc()


def test_example_has_a_snippet_and_passes_review_lint(tmp_path):
    ex = example()
    assert "## Key code changes" in ex and "```python" in ex
    p = tmp_path / "2026-11-15-word-counter.review.md"
    p.write_text(ex, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "plan_tools.py"), "lint", "--plan", str(p)],
                       capture_output=True, text=True, cwd=tmp_path)
    assert r.returncode == 0 and r.stdout.strip().splitlines()[-1] == "lint: ok", r.stdout + r.stderr


def test_tools_doc_names_review_lint():
    tools = (ROOT / "docs" / "tools.md").read_text(encoding="utf-8")
    row = next(l for l in tools.splitlines() if l.startswith("| `plan_tools` |"))
    assert ".review.md" in row and "Key code changes" in row and "ISSUE: REVIEW:" in row
