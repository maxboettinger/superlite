"""parse_plan and _field ignore headings and fields inside fenced code blocks (#263)."""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from test_run_scripts import SCRIPTS, ENV, git, make_repo, run, write  # noqa: E402

sys.path.insert(0, str(SCRIPTS))
import next_tasks as nt  # noqa: E402
import plan_tools  # noqa: E402

HEAD = "# Plan\n\n## 9. Implementation plan\n\n"


def plan_file(tmp_path, body):
    p = tmp_path / "plan.md"
    p.write_text(HEAD + body, encoding="utf-8")
    return p


def test_fenced_task_heading_keeps_real_task(tmp_path):
    p = plan_file(tmp_path, "### T1 · real · Est. time 1 min\n\n**Owns:** src/a.py\n\n"
                  "```markdown\n### T1 fake\n**Owns:** fake.py\n```\n")
    t = nt.parse_plan(p)["T1"]
    assert t["owns"] == ["src/a.py"]
    assert t["title"] == "real"


def test_fenced_owns_before_real_owns(tmp_path):
    p = plan_file(tmp_path, "### T1 · real\n\n```\n**Owns:** fake.py\n```\n**Owns:** src/a.py\n")
    assert nt.parse_plan(p)["T1"]["owns"] == ["src/a.py"]


def test_fenced_other_id_is_no_task(tmp_path):
    p = plan_file(tmp_path, "### T1 · real\n\n**Owns:** src/a.py\n\n```\n### T9 fake\n**Owns:** fake.py\n```\n")
    out = nt.parse_plan(p)
    assert "T9" not in out
    assert out["T1"]["owns"] == ["src/a.py"]


def test_fenced_comment_heading_does_not_end_task(tmp_path):
    p = plan_file(tmp_path, "### T1 · real\n\n```bash\n# setup\n## notes\n```\n**Owns:** src/a.py\n")
    assert nt.parse_plan(p)["T1"]["owns"] == ["src/a.py"]


def test_tilde_and_long_fences(tmp_path):
    p = plan_file(tmp_path, "### T1 · real\n\n~~~\n**Owns:** fake.py\n~~~\n"
                  "````\n```\n**Owns:** fake.py\n```\n````\n**Owns:** src/a.py\n")
    assert nt.parse_plan(p)["T1"]["owns"] == ["src/a.py"]


def test_est_time_ignores_fence(tmp_path):
    p = plan_file(tmp_path, "### T1 · real\n\n```\n**Est. time:** 9 min\n```\n"
                  "**Est. time:** 2.5 min\n**Owns:** src/a.py\n")
    assert nt.parse_plan(p)["T1"]["est_time"] == 2.5


def test_body_keeps_fenced_lines(tmp_path):
    p = plan_file(tmp_path, "### T1 · real\n\n**Owns:** src/a.py\n```\n### T1 fake\n```\n")
    assert "### T1 fake" in nt.parse_plan(p)["T1"]["body"]


def test_field_skips_fenced_lines():
    assert nt._field("```\n**Owns:** x.py\n```\n**Owns:** y.py", "Owns") == "y.py"
    assert nt._field("```\n**Owns:** x.py\n```", "Owns") == ""


def test_unterminated_fence_matches_plan_tools(tmp_path):
    p = plan_file(tmp_path, "### T1 · one\n\n**Owns:** a.py\n```\nopen\n\n### T2 · two\n\n**Owns:** b.py\n")
    assert set(nt.parse_plan(p)) == {t.id for t in plan_tools.Plan.load(p).tasks}


def test_commit_task_commits_real_owns(tmp_path):
    repo = make_repo(tmp_path)
    (repo / "plan.md").write_text(
        HEAD + "### T1 · real · Complexity 3 · Est. context 20k · Est. time 1 min\n\n"
        "**Owns:** `src/a.py`\n**Produces:** none\n\n"
        "```markdown\n### T1 fake\n**Owns:** fake.py\n```\n", encoding="utf-8")
    git(repo, "add", "-A")
    git(repo, "commit", "-q", "-m", "plan")
    write(repo, "src/a.py", "A = 1\n")
    r = run("commit_task", "T1", "--plan", "plan.md", cwd=repo, env={**ENV, "SUPERLITE_AUTOCOMMIT": "0"})
    assert r.returncode == 0, r.stdout + r.stderr
    cp = json.loads((repo / ".superlite" / "checkpoints.json").read_text(encoding="utf-8"))
    assert "src/a.py" in cp["entries"][-1]["files"]


def test_est_context_ignores_fence(tmp_path):
    p = plan_file(tmp_path, "### T1 · real\n\n```\n**Est. context:** 90k\n```\n"
                  "**Est. context:** 30k\n**Owns:** src/a.py\n")
    assert nt.parse_plan(p)["T1"]["est_context"] == 30


def test_fenced_owns_marker_does_not_make_non_t_task(tmp_path):
    p = plan_file(tmp_path, "### S3 storage\n\n```\n**Owns:** fake.py\n```\n\n"
                  "### S4 real\n\n**Owns:** src/b.py\n")
    out = nt.parse_plan(p)
    assert "S3" not in out
    assert out["S4"]["owns"] == ["src/b.py"]
