"""#329: a sed `s` command's pattern and replacement end at their own delimiter; `/Spe` of a later command is no flag."""
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "scripts"))

import guard_files  # noqa: E402
from guard_judge import judge  # noqa: E402

PLAN_EDIT = ("s/^Spec: sections 1 and 3\\.$/Spec: section 1, section 3./; "
             "s/^Spec: sections 2 and 3\\.$/Spec: section 2, section 3./")


@pytest.mark.parametrize("words, want", [
    (["sed", "-i", "", PLAN_EDIT, ".superlite/plan.md"], [".superlite/plan.md"]),
    (["sed", "-i", "", "s/a/b/;s/c/Spe/", "a.md"], ["a.md"]),
    (["sed", "-n", "s/a/b/; s/c/w/p", "in.txt"], []),
])
def test_later_command_is_no_flag(words, want):
    assert guard_files.targets(words) == want


@pytest.mark.parametrize("words, want", [
    (["sed", "-i", "s/a/b/e", "f.txt"], ["?", "f.txt"]),
    (["sed", "s/a/b/w out.txt", "in.txt"], ["out.txt"]),
    (["sed", "s/a/b/gw out.txt", "in"], ["out.txt"]),
    (["sed", "s|a/b|c|w f.txt", "in"], ["f.txt"]),
    (["sed", "-i", "", "s/a\\/b/c/e", "a.md"], ["?", "a.md"]),
    (["sed", "s/[/]/x/w out.txt", "in"], ["out.txt"]),
    (["sed", "s/[/]/x/e", "in"], ["?"]),
    (["sed", "s/a/b/\ns/c/d/w out.txt", "in"], ["out.txt"]),
])
def test_real_flags_still_found(words, want):
    assert guard_files.targets(words) == want


def test_plan_edit_passes_the_judge(tmp_path):
    p = tmp_path / "p"
    (p / ".superlite").mkdir(parents=True)
    (p / ".superlite" / "plan.md").write_text("Spec: sections 1 and 3.\n")
    cmd = f"sed -i '' '{PLAN_EDIT}' .superlite/plan.md && grep -n \"^Spec:\" .superlite/plan.md"
    assert judge(cmd, str(p), str(p), "active") is None
