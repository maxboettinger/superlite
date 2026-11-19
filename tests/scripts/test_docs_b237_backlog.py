from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
DOC = (ROOT / "commands" / "backlog.md").read_text(encoding="utf-8")
CODE = (ROOT / "skills" / "subagent-driven-development" / "scripts" / "backlog.py").read_text(encoding="utf-8")


def test_by_required_not_default():
    assert "the default is `user`" not in DOC
    assert '"by"` is required' in DOC
    for t in ('"user"', '"main"', '{"<question>": "user"|"main"}'):
        assert t in DOC


def test_decide_print_line_quoted():
    assert "answers file:" in DOC and "answers file:" in CODE


def test_github_not_found_line():
    assert "not found: #N (not in the open-issue list; read by number:" in DOC
    assert "read by number" in DOC
    assert "not found: #{n} (not in the open-issue list; read by number:" in CODE
