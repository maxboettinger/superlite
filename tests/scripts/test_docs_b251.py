# tests/scripts/test_docs_b251.py: the reviewer rule and fleet.md lines for unrun checks and resume (#807, #808)
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RULE = ("- Checks your brief names (a running-app check on a simulator or the Mac, a launch, a named command) are part of "
        "the review: run each one. A check you did not run (no simulator, not reachable, skipped) gets one line "
        "`Not run: <check> - <why>` in your report, and your status is then DONE_WITH_CONCERNS, never DONE; "
        "`fleet wait` shows such a report with ` not_run=N`.")
NOT_RUN = ("- ` not_run=N` (after `findings=` and ` concerns=`): the report names N checks it did not run "
           "(`Not run: <check> - <why>` lines); `fleet wait` turns its DONE into DONE_WITH_CONCERNS and its APPROVED "
           "into ` partial` (#807). Send the worker back with `\"$SL\" fleet_resume Wn --text \"run <check>\" --plan $PLAN`, "
           "or rule the check out.")
RESUME = (" A stopped one-turn worker (a reviewer, fixer, research, writer or checker on this machine) continues its own session instead: "
          "`\"$SL\" fleet_resume Wn --text \"...\" --plan $PLAN` opens a fresh pane, starts its agent with "
          "`--resume <session>` and sends the text with its report contract; wait for it as for a send, and "
          "`fleet wait` stops it again after its report (#808).")
SEND = "`fleet send` to a stopped or dead worker exits 2 with that spawn line."
RESEARCH = "- `findings=N` of a research or writer worker is its answer, not a failure: `--wave` keeps waiting (#903)."


def test_reviewer_rule_is_last_rules_bullet():
    lines = (ROOT / "agents" / "package-reviewer.md").read_text(encoding="utf-8").splitlines()
    i = lines.index(RULE)
    assert lines.count(RULE) == 1 and lines[i - 1].startswith("- If something spans tasks")
    assert lines[i + 1] == "" and lines[i + 2].startswith("Report in at most 300 words")


def test_fleet_md_names_not_run_and_resume():
    text = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
    lines = text.splitlines()
    assert lines.count(NOT_RUN) == 1 and lines[lines.index(NOT_RUN) - 1] == RESEARCH
    assert text.count(SEND + RESUME) == 1
