"""#851: plan lint on a review plan (*.review.md) checks `## Key code changes`: 1 to 4 fenced snippets of at most 15 lines, no code block elsewhere."""
import subprocess
import sys

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import plan_tools as ptm  # noqa: E402

NAME = "2026-11-15-tool.review.md"
FIG = "```mermaid\nflowchart LR\n  A[You] --> B[Tool]\n```\n"


def snippet(n_lines=3, fence="```", lang="python"):
    body = "\n".join(f"x{i} = {i}" for i in range(n_lines))
    return f"Why it matters.\n\n{fence}{lang}\n{body}\n{fence}\n"


def review(snippets=None, extra=""):
    text = "# Tool: review plan\n\n## Summary\nA small tool.\n\n## How it fits together\n" + FIG
    if snippets is not None:
        text += "\n## Key code changes\n" + "\n".join(snippets)
    return text + "\n## How we will know it works\n- It prints the count.\n" + extra


def line_of(text, ln, nth=0):
    return [i + 1 for i, l in enumerate(text.split("\n")) if l == ln][nth]


def lint(tmp_path, text, name=NAME):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    return ptm.lint_review_plan(ptm.Plan.load(str(p)))


def run_cli(tmp_path, text, name=NAME):
    p = tmp_path / name
    p.write_text(text, encoding="utf-8")
    r = subprocess.run([sys.executable, str(SCRIPTS / "plan_tools.py"), "lint", "--plan", str(p)],
                       capture_output=True, text=True, cwd=tmp_path)
    return r.returncode, r.stdout


def test_is_review_plan_by_name():
    assert ptm.is_review_plan("docs/plans/2026-11-15-x.review.md")
    assert ptm.is_review_plan("X.REVIEW.MD")
    assert not ptm.is_review_plan("docs/plans/2026-11-15-x.md")
    assert not ptm.is_review_plan(None)


def test_four_snippets_of_15_lines_pass(tmp_path):
    assert lint(tmp_path, review([snippet(15)] * 4)) == ([], [])


def test_no_section_passes(tmp_path):
    assert lint(tmp_path, review()) == ([], [])


def test_fifth_snippet_is_an_issue(tmp_path):
    text = review([snippet()] * 5)
    issues, _ = lint(tmp_path, text)
    starts = ", ".join(str(line_of(text, "```python", k)) for k in range(5))
    assert issues == [f"REVIEW: ## Key code changes holds 5 snippets; the cap is 4 (snippets at lines {starts})"]


def test_snippet_over_15_lines_is_an_issue(tmp_path):
    text = review([snippet(3), snippet(16)])
    issues, _ = lint(tmp_path, text)
    start = line_of(text, "```python", 1)
    assert issues == [f"REVIEW: snippet at line {start} in ## Key code changes has 16 lines; the cap is 15"]


def test_blank_lines_count(tmp_path):
    text = review(["```python\n" + "x = 1\n\n" * 8 + "```\n"])
    issues, _ = lint(tmp_path, text)
    assert issues == [f"REVIEW: snippet at line {line_of(text, '```python')} in ## Key code changes has 16 lines; the cap is 15"]


def test_empty_section_is_an_issue(tmp_path):
    text = review([])
    issues, _ = lint(tmp_path, text)
    head = line_of(text, "## Key code changes")
    assert issues == [f"REVIEW: ## Key code changes (line {head}) holds no snippet; add 1 to 4 fenced snippets or drop the section"]


def test_code_outside_the_section_is_an_issue(tmp_path):
    text = review([snippet()], extra="\n```bash\nwordcount sample.txt\n```\n")
    issues, _ = lint(tmp_path, text)
    assert issues == [f"REVIEW: code block at line {line_of(text, '```bash')} is outside ## Key code changes; "
                      "a review plan holds code only there"]


def test_code_without_the_section_is_an_issue(tmp_path):
    text = review(None, extra="\n```\nplain fence\n```\n")
    issues, _ = lint(tmp_path, text)
    assert len(issues) == 1 and "is outside ## Key code changes" in issues[0], issues


def test_mermaid_is_never_a_snippet(tmp_path):
    assert lint(tmp_path, review([snippet()] * 4 + [FIG])) == ([], [])


def test_heading_inside_a_snippet_does_not_end_the_section(tmp_path):
    text = review(["```markdown\n## Not a heading\n```\n", snippet()])
    assert lint(tmp_path, text) == ([], [])


def test_tilde_fence_counts(tmp_path):
    issues, _ = lint(tmp_path, review([snippet(fence="~~~")] * 5))
    assert len(issues) == 1 and "holds 5 snippets; the cap is 4" in issues[0], issues


def test_numbered_heading_counts(tmp_path):
    text = review([snippet()] * 5).replace("## Key code changes", "## 5. Key code changes:")
    issues, _ = lint(tmp_path, text)
    assert len(issues) == 1 and issues[0].startswith("REVIEW: ## Key code changes holds 5 snippets; the cap is 4"), issues


def test_two_sections_are_an_issue_and_count_together(tmp_path):
    text = review([snippet()] * 3, extra="\n## Key code changes\n" + snippet() + snippet())
    issues, _ = lint(tmp_path, text)
    a, b = line_of(text, "## Key code changes"), line_of(text, "## Key code changes", 1)
    assert issues[0] == f"REVIEW: ## Key code changes appears 2 times (lines {a}, {b}); keep one section"
    assert len(issues) == 2 and "holds 5 snippets; the cap is 4" in issues[1], issues


def test_unclosed_fence_is_an_issue(tmp_path):
    text = review([snippet()]) + "\n```python\nx = 1\n"
    issues, _ = lint(tmp_path, text)
    assert issues == [f"REVIEW: code fence at line {line_of(text, '```python', 1)} is never closed"]


def test_cli_ok_and_issue_exit_codes(tmp_path):
    code, out = run_cli(tmp_path, review([snippet(15)] * 4))
    assert code == 0 and out.strip().splitlines()[-1] == "lint: ok", out
    code, out = run_cli(tmp_path, review([snippet()] * 5))
    assert code == 1, out
    assert "ISSUE: REVIEW: ## Key code changes holds 5 snippets; the cap is 4" in out
    assert out.strip().splitlines()[-1] == "lint: 1 issue(s)"
    assert "no task headings" not in out and "taskgraph" not in out and "Coverage" not in out


def test_machine_plan_lint_is_unchanged(tmp_path):
    code, out = run_cli(tmp_path, review([snippet()] * 5), name="2026-11-15-tool.md")
    assert code == 1 and "no task headings" in out and "REVIEW:" not in out, out
