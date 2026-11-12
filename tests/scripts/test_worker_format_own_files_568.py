"""#568: implementer, reviewer and fixer briefs format only the files the worker changed, never the whole tree."""
from pathlib import Path

AGENTS = Path(__file__).resolve().parents[2] / "agents"
FORMAT = ("- Format only the files you changed: pass their paths to the project's format command (the one its AGENTS.md, CLAUDE.md "
          "or scripts name), never run it over the whole tree. A format command that takes no paths: skip it; the coordinator "
          "formats once at freeze.")
EDIT = "- Edit only the files you own."
FIX = "- Fix only the listed findings. No refactors. Touch no file outside the findings, except the test file for the regression test."
SCOPE = "- Out of scope: change only the files in scope"
ANCHORS = {
    "implementer.md": EDIT,
    "implementer-haiku.md": EDIT,
    "fixer-sonnet.md": FIX,
    "fixer-sonnet-high.md": FIX,
    "fixer-opus.md": FIX,
    "package-reviewer.md": SCOPE,
}


def test_every_worker_formats_only_its_own_files():
    for name, anchor in ANCHORS.items():
        lines = (AGENTS / name).read_text(encoding="utf-8").split("\n")
        assert lines.count(FORMAT) == 1, name
        at = lines.index(FORMAT)
        assert lines[at - 1].startswith(anchor), name


def test_format_rule_names_the_skip_and_the_freeze():
    for s in ("only the files you changed", "pass their paths", "never run it over the whole tree", "takes no paths: skip it",
              "the coordinator formats once at freeze"):
        assert s in FORMAT, s
