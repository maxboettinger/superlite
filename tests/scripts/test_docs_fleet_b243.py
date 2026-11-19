"""B243 (#902, #909, #903): fleet.md names the gate refusal, the bounded override, the usage fallback, the unsent brief, the waits-on suffix."""
from pathlib import Path

FLEET = (Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "fleet.md").read_text()


def test_fleet_md_names_b243_rules():
    for phrase in ("--over-limit --max-workers N --min-swap-free-mb M", "gave up after", "a waiting review spawn", "accounts skipped:",
                   "using its reading from", "BLOCKED: Wn L not sent (brief not taken after one resend)", " waits on <command>",
                   "`findings=N` of a research or writer worker is its answer"):
        assert phrase in FLEET, phrase
