"""#753: implementer and TDD texts tell a test that spawns git in a temporary repository to drop git's exported variables."""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
GITENV = ("- A test that spawns git in a temporary repository removes `GIT_DIR`, `GIT_INDEX_FILE` and `GIT_WORK_TREE` from "
          "the child's environment: git exports them to its hooks, so a test run from a hook (a pre-commit suite run) that "
          "keeps them acts on the real repository.")
ANCHORS = {
    "agents/implementer.md": "- For each producer your task consumes, test against a fake.",
    "skills/test-driven-development/SKILL.md": "- Cover the contract's edge cases: empty input, errors, boundaries.",
}


def test_both_texts_hold_the_git_env_rule():
    for rel, anchor in ANCHORS.items():
        lines = (ROOT / rel).read_text(encoding="utf-8").split("\n")
        assert lines.count(GITENV) == 1, rel
        at = lines.index(GITENV)
        assert lines[at - 1].startswith(anchor), rel


def test_tdd_rule_sits_in_good_tests():
    text = (ROOT / "skills/test-driven-development/SKILL.md").read_text(encoding="utf-8")
    good = text.split("## Good tests\n")[1].split("\n## ")[0]
    assert GITENV in good.split("\n")


def test_rule_names_the_three_variables_and_the_cause():
    for s in ("`GIT_DIR`", "`GIT_INDEX_FILE`", "`GIT_WORK_TREE`", "temporary repository", "exports them to its hooks",
              "acts on the real repository"):
        assert s in GITENV, s
