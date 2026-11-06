"""Docs checks for the B1 fleet dispatch round changes."""
from pathlib import Path  # O(1)

ROOT = Path(__file__).resolve().parents[2]  # O(1)
SKILL = ROOT / "skills" / "subagent-driven-development" / "fleet.md"  # O(1)
DOC = ROOT / "docs" / "fleet.md"  # O(1)


def test_fleet_md_wait_any_background():  # O(1)
    text = SKILL.read_text(encoding="utf-8")  # O(n)
    for needle in ("fleet wait --any", "background", "BUSY Wn"):  # O(1)
        assert needle in text, needle  # O(n)


def test_fleet_md_names_stopped_line():  # O(1)
    text = SKILL.read_text(encoding="utf-8")  # O(n)
    for needle in ("stopped Wn", "build_prime"):  # O(1)
        assert needle in text, needle  # O(n)


def test_docs_fleet_lists_new_output():  # O(1)
    text = DOC.read_text(encoding="utf-8")  # O(n)
    needles = ("--any", "BUSY", "stopped W", "baseline_k=",
               "reported, waiting for coordinator",
               "run build_prime --plan PLAN first")  # O(1)
    for needle in needles:  # O(1)
        assert needle in text, needle  # O(n)
