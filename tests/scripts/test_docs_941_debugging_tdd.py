from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _has(rel, phrase):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert text.count(phrase) == 1, (rel, phrase)


def test_debugging_rules_941():
    f = "skills/systematic-debugging/SKILL.md"
    _has(f, "bisect the test files for the one that leaves state behind")
    _has(f, "never a sleep or a longer timeout")


def test_tdd_rules_941():
    f = "skills/test-driven-development/SKILL.md"
    _has(f, "Name the production change that would make the test fail")
    _has(f, "never from the code under test")
    _has(f, "never assert what the mock itself does")
    _has(f, "For each realistic break")
