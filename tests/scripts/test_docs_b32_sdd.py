"""SDD SKILL.md steps 1, 3 and 4, the fixer contract and mvp-flow step 1 name the 1.5.25-1.5.34 changes (#310)."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def step(n):
    return next(ln for ln in read("skills/subagent-driven-development/SKILL.md").splitlines() if ln.startswith(f"{n}. "))


def test_step2_names_the_unstable_line_and_the_fix_task_lapse():
    s = step(2)
    assert "`unstable=Tn <reason>; rerun sl lint --stable`" in s
    assert "`depends on unstable <ids>`" in s and "once those ids are committed" in s


def test_step3_runs_the_wait_line_in_the_foreground():
    s = step(3)
    assert ("then run the printed `wait:` line in the foreground (never as a background command) "
            "and end the turn only after it reports)") in s
    assert "then the printed `wait:` line)" not in s


def test_step4_names_the_three_commit_task_lines():
    assert ("prints `Tn <sha>`, `Tn FAILED` or "
            "`Tn: no change since its last checkpoint <sha>` (one task: the SHA)") in step(4)


def test_fixer_contract_runs_the_wait_line_in_the_foreground():
    text = read("skills/subagent-driven-development/fixing.md")
    line = next(ln for ln in text.splitlines() if ln.startswith("- **Fixer contract:**"))
    assert ("then run the printed `wait:` line (`run_tests --wait <path>`) in the foreground "
            "(never as a background command) and end the turn only after it reports;") in line
    assert "wait with the printed" not in line


def test_mvp_flow_step1_routes_through_brainstorming():
    line = next(ln for ln in read("docs/mvp-flow.md").splitlines() if ln.startswith("1. "))
    for s in ("`superlite:brainstorming`", "`/superlite:feature`", "never trivial", "orchestrator choice",
              "`sl orchestrator set`", "AskUserQuestion withheld", "`Ruling:`",
              "Steps 2 to 6 replace brainstorming's design and approval steps"):
        assert s in line, s
    assert "asked once with the other questions" not in line


def test_trim_kept_the_coordinator_rules():
    text = read("skills/subagent-driven-development/SKILL.md")
    for s in ("Start all.", "Act on `next:` lines.", "The tree stays frozen.", "nothing more",
              "Only you run it.", "Wave 0 is not yours"):
        assert s in text, s
