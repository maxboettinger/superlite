"""B255 (#951, #973): SDD Final review step 2 runs run_tests --base-skips after a full run that skipped tests, before the packet; backlog-main.md step 5 says main files follow-ups from the full notes text."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SDD = ROOT / "skills" / "subagent-driven-development"
SKILL = (SDD / "SKILL.md").read_text(encoding="utf-8")
MAIN = (SDD / "backlog-main.md").read_text(encoding="utf-8")
BASE = "then its `wait:` line, then `run_tests --base-skips` if it skipped tests."
NOTES = ("Main files each follow-up from the full text `\"$SL\" backlog ship B notes` prints, never from the cut text of a wait line; "
         "a lead never files one (#815).")
S5_END = "names the running leads in one `backlog:` line."


def _step(text, n):
    return next(line for line in text.splitlines() if line.startswith(f"{n}. "))


def test_step2_runs_base_skips_before_the_packet():
    final = SKILL.split("## Final review", 1)[1].split("## Measure and budget", 1)[0]
    step2 = _step(final, 2)
    assert step2.count(BASE) == 1
    assert step2.index("`wait:` line") < step2.index("--base-skips") < step2.index("plan_tools packet")
    assert len(SKILL) <= 13300


def test_trims_keep_the_pinned_phrases():
    assert "uses that run's summary, and writes `.superlite/review-packet.md`" in SKILL
    assert "the packet's `## Render evidence` section lists them." in SKILL
    assert "prints per ready task: `Tn agent=ID tier=T`" in SKILL


def test_base_skips_phrase_is_pinned_for_trims():
    orch = (ROOT / "tests" / "scripts" / "test_orchestrator.py").read_text(encoding="utf-8")
    assert '    # test_docs_b255_skill.py\n    "then `run_tests --base-skips` if it skipped tests.",\n)' in orch


def test_main_step5_names_the_notes_text():
    step5 = _step(MAIN.split("## Main", 1)[1].split("## Limits", 1)[0], 5)
    assert step5.count(S5_END + " " + NOTES + " ") == 1


def test_quoted_commands_exist():
    scripts = SDD / "scripts"
    assert "run_tests --base-skips, then rebuild the packet" in (scripts / "pt_review.py").read_text(encoding="utf-8")
    assert '"--base-skips"' in (scripts / "run_tests.py").read_text(encoding="utf-8")
    assert 'a.action == "notes"' in (scripts / "backlog_ship.py").read_text(encoding="utf-8")
