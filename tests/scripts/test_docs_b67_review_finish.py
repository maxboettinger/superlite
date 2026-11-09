"""B67 (#401): SDD fleet.md names fleet report, finishing names orchestrator takeover, final-reviewer names the tests shard, OUTDATED lines and the IMPORT warning."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD_FLEET = (ROOT / "skills" / "subagent-driven-development" / "fleet.md").read_text(encoding="utf-8")
FINISH = (ROOT / "skills" / "finishing-a-development-branch" / "SKILL.md").read_text(encoding="utf-8")
REVIEWER = (ROOT / "agents" / "final-reviewer.md").read_text(encoding="utf-8")

UNKNOWN = '  - `UNKNOWN` (no parsable report): `"$SL" fleet report Wn --plan $PLAN` prints the saved `.superlite/fleet/reports/<id>.md` (read-only; a busy worker or one with no collected report exits 1); read it once, then decide.'
FINISH_TAKEOVER = "When `end` refuses because another session owns the run (this session took over a run whose first session ran out of usage or crashed; `finish` names it too), run `<skill-dir>/../subagent-driven-development/scripts/sl orchestrator takeover --plan <absolute plan path>` first, then `end` again."
R_OUTDATED = "- `OUTDATED:` and `OUTDATED incident:` lines in section 4 are failures whose code changed after that run; the full suite decides, so they are not open and not a finding on their own."
R_SHARD = "- A `Tests shard:` line in the packet head names `<packet stem>-tests.md`, the full diffs of every changed test file; it carries the truncated marker, so you may read it in full like any truncated file."
R_IMPORT = "- Plan lint's `WARNING: IMPORT:` (a Swift consumer target uses a type declared in a SwiftPM target its `Package.swift` does not list) is not in the packet: an excerpt that shows such a cross-target use is a finding, tier 2."


def test_sdd_fleet_unknown_uses_fleet_report():
    lines = SDD_FLEET.splitlines()
    assert UNKNOWN in lines
    assert sum("`UNKNOWN`" in ln for ln in lines) == 1


def test_finishing_names_takeover_in_cleanup():
    sec = FINISH.split("## 6. Worktree cleanup", 1)[1].split("\n## ", 1)[0]
    assert "the coordinator guard stops). " + FINISH_TAKEOVER in sec


def test_final_reviewer_bullets_follow_the_failing_test_rule():
    lines = REVIEWER.splitlines()
    i = next(k for k, ln in enumerate(lines) if ln.startswith("- A failing or skipped test"))
    assert lines[i + 1:i + 4] == [R_OUTDATED, R_SHARD, R_IMPORT]


def test_final_reviewer_keeps_its_contract():
    assert "read <path> in full" in REVIEWER and "may read" in REVIEWER and "nothing else" in REVIEWER
    assert "tools: Read, Grep, Glob" in REVIEWER and "$SL" not in REVIEWER
