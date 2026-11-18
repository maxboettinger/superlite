from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")


def _has(rel, phrase):
    assert _read(rel).count(phrase) == 1, (rel, phrase)


def test_review_rules_941():
    _has("agents/package-reviewer.md", "count only once the diff or a run shows them")
    _has("agents/final-reviewer.md", "recheck every earlier finding against its fix")
    _has("agents/final-reviewer.md", "0b: N rechecked")
    for f in ("fixer-sonnet", "fixer-sonnet-high", "fixer-opus"):
        _has(f"agents/{f}.md", "Check each finding against the code before you edit")
