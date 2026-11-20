"""Docs and quoted texts for per-task tracker keys and the commit subject template (#911)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"


def read(p):
    return Path(p).read_text(encoding="utf-8")


def test_docs_911_clauses_once():
    tools = read(ROOT / "docs" / "tools.md")
    tpl = read(ROOT / "skills" / "writing-plans" / "task-template.md")
    assert tools.count("(the task's own, else the plan header's) prefixes messages `KEY Tn: title`, or the subject template sets them (#911)") == 1
    assert "a `**Ticket:** KEY` plan header prefixes messages" not in tools
    assert tools.count('`"commit_subject"`') == 1
    assert tools.count("`WARNING: TICKET:`") == 1 and tools.count("`WARNING: COMMIT:`") == 1
    assert tpl.count("| `Ticket` |") == 1
    assert tpl.index("| `Ticket` |") > tpl.index("| `Also-touches` |")


def test_quoted_texts_match_code():
    plan_tools = read(SCRIPTS / "plan_tools.py")
    auto = read(SCRIPTS / "autocommit.py")
    assert "WARNING: TICKET:" in plan_tools and "WARNING: COMMIT:" in plan_tools
    assert 'DEFAULT_SUBJECT = "{ticket} {tid}: {title}"' in auto
    assert "commit_subject" in auto
