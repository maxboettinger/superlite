"""docs/fleet.md: the "Leads outside backlog mode" section (B273, #906)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SCRIPTS = ROOT / "skills" / "subagent-driven-development" / "scripts"
DOC = ROOT / "docs" / "fleet.md"

BULLETS = [
    "- The lead is its own Claude session: its `sl orchestrator set ai --plan .superlite` and `sl fleet on --plan .superlite` give it its own run binding and its own session fleet; main's binding stays.",
    "- Without `--brief`, spawn writes `<worktree>/.superlite/briefs/lead.md` (`fleet_lead.plan_brief`): build the plan with its own fleet, the final review, the test layers, commits on the worktree's branch; never push, merge, open a pull request or ship (main decides the integration). With `--brief F` it sends F unchanged. A plan lead starts without the ship allow rules.",
    "- Admission: the disk gate and the machine gate as for `backlog start` (`BLOCKED: lead for <worktree> not started: <why>`, exit 3). Refused with exit 2 before any pane: P not found, P outside a git checkout, P in this run's own worktree, a live lead of this fleet already in that worktree (`Wn already leads <worktree>; stop it first: sl fleet stop Wn`), a path that is no plan without `--brief` (`pass a plan file, or --brief F`), and `--tier`, `--machine`, `--for-dispatch`, `--for-review`, `--package` or `--note`.",
    "- The report label defaults to `lead-<worktree folder>`. Spawn prints `Wn lead <worktree>: progress: sl fleet status; run state: sl status --plan <worktree>/.superlite; wait: sl fleet wait Wn (returns at DONE, NEEDS_DECISION or BLOCKED); answer: sl fleet send Wn --text T`.",
    "- Progress without stopping the lead: `sl fleet status` prints one `lead Wn <worktree>: ...` line per live lead (`status.lead_progress`, batch leads too): its plan and task count, the task groups (checkpointed, running, held, open), its busy workers, and `question: open <path>` while a question.json newer than the last message waits.",
    "- Decisions: `NEEDS_DECISION` is a report status; every lead's brief line lists it, and `fleet wait` ends the lead's line with ` question=<worktree>/.superlite/question.json` when that file exists. It is no wave-OK status, so `fleet wait --wave` and `--any` return on it. Main asks the user and answers with `sl fleet send Wn --text \"<answer>\"`.",
    "- `fleet stop Wn` stops the lead's own workers first, then the lead; `fleet restore` resumes it like any lead.",
]


def test_docs_b273_section():
    text = DOC.read_text(encoding="utf-8")
    head = "## Leads outside backlog mode"
    assert head in text
    assert text.index(head) < text.index("## Batch leads (backlog mode)")
    for b in BULLETS:
        assert b in text, b[:60]


def test_docs_b273_messages_match_code():
    lead = (SCRIPTS / "fleet_lead.py").read_text(encoding="utf-8")
    for s in ("already leads", "not started:", "progress: sl fleet status", "pass a plan file, or --brief F"):
        assert s in lead, s
    assert "question=" in (SCRIPTS / "fleet_io.py").read_text(encoding="utf-8")
    assert "NEEDS_DECISION" in (SCRIPTS / "fleet_report.py").read_text(encoding="utf-8")
    assert "lead_progress" in (SCRIPTS / "fleet.py").read_text(encoding="utf-8")
