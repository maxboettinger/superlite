"""docs/hooks.md names #1070's known-variable log targets and the Logs bullet, and #1069's capture hint (#1087)."""
from __future__ import annotations

from pathlib import Path

DOC = Path(__file__).resolve().parents[2] / "docs" / "hooks.md"
BULLETS = [
    ("- `block-coordinator-edits`, session scripts and eval (#693):", "- `block-coordinator-edits`, known-variable log targets (#1070): a redirect target held in a variable with one known value (`LOG=.build/ios-test.log; cmd > \"$LOG\"`) gets the same git-ignored housekeeping check as a literal target; a name built from `$(...)` stays unknown. The code block's \"Logs and command output\" bullet names the scratch folder: redirect logs into `<state folder>/scratch/` or into a git-ignored folder no task Owns such as `.build/`, named literally or through a variable with one known value."),
    ("- `block-coordinator-edits`, unresolved words (#780, #781):", "- `block-coordinator-edits`, captured `sl` output (#1069): when a word the guard cannot resolve comes from a variable captured from `sl` output (followed back up to 4 assignments), the line before `Unresolved word:` (`guard_tools.capture_hint`) names the form that needs no capture: `sl run_tests --wait` with no path for `run_tests`, `sl findings route --send` for `findings route`, and copying the printed text for any other `sl` tool; verdicts and the block's last two lines are unchanged."),
]


def test_new_bullets_follow_their_anchor():
    lines = DOC.read_text(encoding="utf-8").splitlines()
    for anchor, bullet in BULLETS:
        assert lines.count(bullet) == 1, bullet[:60]
        first = next(i for i, ln in enumerate(lines) if ln.startswith(anchor))
        assert lines.index(bullet) > first, bullet[:60]
