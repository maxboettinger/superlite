# tests/regression/test_fleet_roles_final_b.py
import sys
sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parents[1] / "scripts"))
from test_plan_tools import ROOT, SCRIPTS
sys.path.insert(0, str(SCRIPTS))
import fleet_roles as fr  # noqa: E402
import routing  # noqa: E402

CFG = routing.load_cfg()
WRITERS = ["Edit", "Write", "NotebookEdit", "Bash"]


def _disallowed(argv):
    return argv[argv.index("--disallowedTools") + 1:]


def test_research_launch_disallows_every_writing_tool():
    for tier in (None, "sonnet"):
        assert _disallowed(fr.launch("research", tier, CFG)["argv"]) == ["AskUserQuestion"] + WRITERS


def test_other_roles_keep_their_disallowed_tools():
    for role in ("implementer", "fixer", "package-reviewer", "final-reviewer"):
        assert _disallowed(fr.launch(role, None, CFG)["argv"]) == ["AskUserQuestion"]


def test_researcher_agent_file_has_no_writing_tool():
    text = (ROOT / "agents" / "researcher.md").read_text(encoding="utf-8")
    tools = [l for l in text.split("---")[1].splitlines() if l.startswith("tools:")][0].split(":", 1)[1]
    assert [t.strip() for t in tools.split(",")] == ["Read", "Grep", "Glob"]
    assert "git log" not in text and "Bash is for" not in text
