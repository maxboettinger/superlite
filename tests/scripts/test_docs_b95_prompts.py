"""B95 (#451): writing-plans, backlog and resume texts name 1.5.77 to 1.5.95."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
WP = "\n".join((ROOT / "skills" / "writing-plans" / n).read_text(encoding="utf-8") for n in ("SKILL.md", "task-template.md", "probe-plan.md", "split.md"))
CMD_BACKLOG = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")
SDD_BACKLOG = ((ROOT / "skills" / "subagent-driven-development" / "backlog-main.md").read_text(encoding="utf-8") + "\n" + (ROOT / "skills" / "subagent-driven-development" / "backlog.md").read_text(encoding="utf-8"))
RESUME = (ROOT / "commands" / "resume.md").read_text(encoding="utf-8")


def has(text, *tokens):
    missing = [t for t in tokens if t not in text]
    assert not missing, missing


def test_writing_plans_produces_and_probe():
    has(WP, "Name(Exception)", "raises=")
    assert "each probe call has a 10 s timeout" not in WP


def test_backlog_issues_and_carry_over():
    for text in (CMD_BACKLOG, SDD_BACKLOG):
        has(text, "GitHub numbers", "ranked first")


def test_resume_calls_orchestrator_resume():
    has(RESUME, "sl orchestrator resume", "sl status")
