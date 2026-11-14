"""#784: every fleet worker role is denied git checkout, git restore and git stash in the shared tree."""
import sys

import pytest

from test_plan_tools import SCRIPTS

sys.path.insert(0, str(SCRIPTS))
import fleet  # noqa: E402
import fleet_roles as fr  # noqa: E402
import routing  # noqa: E402

CFG = routing.load_cfg()
DENY = ["Bash(git checkout *)", "Bash(git restore *)", "Bash(git stash)", "Bash(git stash *)"]


def test_git_deny_constant():
    assert list(fr.GIT_DENY) == DENY
    assert fr.TAIL == ["--disallowedTools", "AskUserQuestion", *DENY]


@pytest.mark.parametrize("role,tier", [("implementer", "sonnet"), ("implementer", "haiku"), ("fixer", "2"),
                                       ("package-reviewer", None), ("final-reviewer", None), ("checker", None),
                                       ("research", None)])
def test_every_worker_role_denies_git_tree_commands(role, tier):
    argv = fr.launch(role, tier, CFG)["argv"]
    i = argv.index("--disallowedTools")
    assert argv[i + 1] == "AskUserQuestion"
    assert all(d in argv[i + 1:] for d in DENY)
    assert argv.count("--disallowedTools") == 1


def test_writer_keeps_its_own_deny_list(tmp_path):
    argv = fr.launch("writer", None, CFG, output=str(tmp_path / "x.md"))["argv"]
    assert argv[-4:] == ["--disallowedTools", "AskUserQuestion", "Bash", "NotebookEdit"]
    assert argv.count("--disallowedTools") == 1


def test_lean_argv_keeps_each_deny_name_once():
    argv = fleet.lean_argv(fr.launch("implementer", "sonnet", CFG)["argv"], None, ["Bash(git stash)"])
    assert all(argv.count(d) == 1 for d in DENY)
