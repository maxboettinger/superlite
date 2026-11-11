"""B98 (#460): SDD Final review builds the review packet after the full run, never before it."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = (ROOT / "skills" / "subagent-driven-development" / "SKILL.md").read_text(encoding="utf-8")
FINAL = SKILL.split("## Final review", 1)[1].split("## Measure and budget", 1)[0]


def test_full_run_waits_before_the_packet():
    step2 = next(line for line in FINAL.splitlines() if line.startswith("2. "))
    assert (step2.index("run_tests --full --background") < step2.index("`wait:` line")
            < step2.index("plan_tools packet"))
    assert "uses that run's summary" in step2
    assert "no wait" not in FINAL and "Same message" not in FINAL


def test_diagram_runs_the_suite_before_the_packet():
    assert "  G[all tasks reviewed + committed] --> ST[run_tests --full, wait]\n  ST --> PK[packet from its summary]\n" in FINAL
    assert "G --> ST" not in FINAL and "ST --> V" not in FINAL


def test_batching_names_both_waits_and_cap_holds():
    assert "- Every test run is `run_tests ... --background`; wait in Final review 2 and 5." in SKILL
    assert "wait once (Final review 5)" not in SKILL
    assert len(SKILL) <= 11700
