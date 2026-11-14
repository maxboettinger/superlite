"""#784: every prime kind says to edit only under Root and that a dirty git status is the run's normal state."""
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import build_prime as bp  # noqa: E402

OWNS = "- Build only what your task owns (its `Owns` files). Never edit other files."
FULL = [
    "- Edit only files under Root (above), by absolute paths that start with Root. A copy of the same file elsewhere "
    "(the main checkout, the folder that holds sl) is not yours, even when your shell's cwd is there.",
    "- `git status` showing files changed against HEAD is the run's normal state (other tasks' and the coordinator's "
    "uncommitted work), never stale files: never revert, restore or stash a file you did not change. `git checkout`, "
    "`git restore` and `git stash` are denied to workers; undo your own edit by editing it back.",
]
MINI = ("- Edit only files under Root, by absolute paths. A dirty `git status` is the run's normal state: never revert, "
        "restore or stash a file you did not change (`git checkout`, `git restore` and `git stash` are denied).")


@pytest.mark.parametrize("pre", [bp.PREAMBLE, bp.PREAMBLE_SLIM])
def test_full_and_slim_carry_both_rules_after_the_owns_rule(pre):
    lines = pre.splitlines()
    i = lines.index(OWNS)
    assert lines[i + 1:i + 3] == FULL


def test_mini_carries_the_short_rule_only():
    lines = bp.PREAMBLE_MINI.splitlines()
    i = lines.index(OWNS)
    assert lines[i + 1] == MINI
    assert FULL[0] not in lines and FULL[1] not in lines


@pytest.mark.parametrize("pre", [bp.PREAMBLE, bp.PREAMBLE_SLIM, bp.PREAMBLE_MINI])
def test_rules_sit_after_the_root_slot(pre):
    assert pre.index("\n\nRules:") < pre.index("Edit only files under Root")
