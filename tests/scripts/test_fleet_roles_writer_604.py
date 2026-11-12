"""#604: the writer fleet role may write only the one file its brief's Output: line names."""
import sys
from pathlib import Path
import pytest
from test_plan_tools import SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_roles as fr  # noqa: E402
import routing  # noqa: E402

CFG = routing.load_cfg()
ROOT = Path(__file__).resolve().parents[2]


def test_writer_argv_limits_writes_to_output():
    assert fr.launch("writer", None, CFG, output="/r/docs/plans/x.md") == {
        "role": "writer", "agent": "superlite:writer", "model": "sonnet", "effort": "medium",
        "argv": ["--agent", "superlite:writer", "--model", "sonnet", "--effort", "medium", "--permission-mode", "default",
                 "--allowedTools", "Edit(//r/docs/plans/x.md)", "--disallowedTools", "AskUserQuestion", "Bash", "NotebookEdit"],
        "prime": False, "pool": False, "one_turn": True}


def test_writer_tier_pins_model():
    assert fr.launch("writer", "opus", CFG, output="/r/a.md")["argv"][:4] == ["--agent", "superlite:writer", "--model", "opus"]


def test_writer_without_output_or_bad_tier_is_value_error():
    with pytest.raises(ValueError, match=r"writer needs an output file \(the brief's Output: line\)"):
        fr.launch("writer", None, CFG)
    with pytest.raises(ValueError, match="writer tier must be sonnet, opus or haiku"):
        fr.launch("writer", "2", CFG, output="/r/a.md")


def test_other_roles_ignore_output():
    assert fr.launch("fixer", "1", CFG, output="/r/a.md") == fr.launch("fixer", "1", CFG)


def test_roles_tuple_ends_with_writer():
    assert fr.ROLES == ("implementer", "fixer", "package-reviewer", "final-reviewer", "research", "checker", "writer")


def test_writer_agent_file():
    text = (ROOT / "agents" / "writer.md").read_text(encoding="utf-8")
    head, body = text.split("---\n", 2)[1:]
    lines = head.splitlines()
    for line in ("name: writer", "model: sonnet", "effort: medium", "tools: Read, Grep, Glob, Write, Edit"):
        assert line in lines
    for s in ("Output:", "absolute `sl` path", "no shell", "every other write is refused"):
        assert s in body
    assert "$SL" not in text


def test_skills_and_agents_lists_writer():
    lines = (ROOT / "docs" / "skills-and-agents.md").read_text(encoding="utf-8").splitlines()
    assert any(x.startswith("- `writer` (sonnet, medium)") for x in lines)
