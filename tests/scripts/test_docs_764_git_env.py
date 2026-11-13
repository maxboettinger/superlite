"""#764: the haiku implementer and the three fixers carry #753's git-variables rule for tests, word for word."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ANCHORS = {
    "agents/implementer-haiku.md": "- For each producer your task consumes, test against a fake.",
    "agents/fixer-sonnet.md": "- The `--background` run prints a `next:` cue",
    "agents/fixer-sonnet-high.md": "- The `--background` run prints a `next:` cue",
    "agents/fixer-opus.md": "- The `--background` run prints a `next:` cue",
}


def _rule():
    lines = (ROOT / "agents/implementer.md").read_text(encoding="utf-8").split("\n")
    found = [ln for ln in lines if "`GIT_INDEX_FILE`" in ln]
    assert len(found) == 1
    return found[0]


def test_rule_is_the_753_line():
    rule = _rule()
    assert rule.startswith("- A test that spawns git in a temporary repository removes `GIT_DIR`, `GIT_INDEX_FILE` and "
                           "`GIT_WORK_TREE`")


def test_four_workers_hold_the_rule_once_after_their_anchor():
    rule = _rule()
    for rel, anchor in ANCHORS.items():
        lines = (ROOT / rel).read_text(encoding="utf-8").split("\n")
        assert lines.count(rule) == 1, rel
        at = lines.index(rule)
        assert lines[at - 1].startswith(anchor), rel
        assert lines[at + 1].startswith("- "), rel
