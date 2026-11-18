from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _has(rel, phrase):
    text = (ROOT / rel).read_text(encoding="utf-8")
    assert text.count(phrase) == 1, (rel, phrase)


def test_implementer_rules_941():
    _has("agents/implementer.md", "the task needs an architecture choice the plan does not make")
    for f in ("implementer", "implementer-haiku"):
        _has(f"agents/{f}.md", "never split or restructure files on your own")
