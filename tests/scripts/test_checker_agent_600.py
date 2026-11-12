"""#600: the checker agent carries the standing rules for running-app checks."""
from pathlib import Path

TEXT = (Path(__file__).resolve().parents[2] / "agents" / "checker.md").read_text(encoding="utf-8")


def test_checker_frontmatter():
    fm = TEXT.split("---")[1]
    for s in ("\nname: checker\n", "\nmodel: sonnet\n", "\neffort: high\n", "disallowedTools: Agent, Task, Workflow, AskUserQuestion,"):
        assert s in fm, s


def test_checker_standing_rules():
    for s in ("absolute `sl` path", "PASS, FAIL or NOT REACHABLE", "none is skipped", "at most 5 minutes",
              "you never fix", "`sl-check-<basename of ROOT>`", "`xcrun simctl create <name> <device type> <runtime>`",
              "Never boot, shut down, erase, install on or delete a simulator with another name",
              "`xcrun simctl shutdown all`", "One simulator of yours booted at a time", "`Simulators:` line",
              "-derivedDataPath <ROOT>/.build/CheckDerivedData", "never `<ROOT>/.build/DerivedData`",
              "`screencapture -x`", "Screen Recording permission", "render_edit start <file> --plan PLAN",
              "render_edit restore --plan PLAN", "<ROOT>/.superlite/render/index.md", "docs/simulator-limits.md",
              "`C<n> PASS|FAIL|NOT REACHABLE - ", "Simulators: none", "BLOCKED when none could run"):
        assert s in TEXT, s
    assert "$SL" not in TEXT and "$SUPERLITE" not in TEXT
