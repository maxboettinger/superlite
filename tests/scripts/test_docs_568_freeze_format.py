"""#568, coordinator side: workers skip a format command that takes no paths, so the coordinator formats once at the final-review gate."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
SKILL = ROOT / "skills" / "subagent-driven-development" / "SKILL.md"
GATE = ("1. Gate: all tasks and reviews committed, all seams `verified`. Then run the project's format command once: over the run's "
        "changed files, or the whole tree when it takes no paths (workers skip that one); `commit_task Tn` per owning task for what "
        "it changed.")
WORKER = "A format command that takes no paths: skip it; the coordinator formats once at freeze."


def test_the_gate_step_formats_once_and_commits_the_result():
    lines = SKILL.read_text(encoding="utf-8").split("\n")
    assert lines.count(GATE) == 1
    assert sum(1 for line in lines if "format command once" in line) == 1


def test_format_runs_before_the_full_run_and_the_packet():
    lines = SKILL.read_text(encoding="utf-8").split("\n")
    at = lines.index(GATE)
    assert lines[at + 1].startswith("2. `run_tests --full --background`")
    assert GATE.index("format command once") < GATE.index("commit_task Tn")


def test_worker_rule_still_points_at_the_coordinator():
    assert WORKER in (ROOT / "agents" / "implementer.md").read_text(encoding="utf-8")
