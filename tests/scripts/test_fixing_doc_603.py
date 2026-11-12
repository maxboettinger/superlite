"""#603 #596: fixing.md says where briefs and notes live, names route --also and the claim's next step, the format and checkpoint rules."""
from pathlib import Path

TEXT = (Path(__file__).resolve().parents[2] / "skills" / "subagent-driven-development" / "fixing.md").read_text(encoding="utf-8")


def test_fixing_md_holds_the_four_insertions():
    for s in ("or `--also Tn=F` (that task's brief): the brief lists it with its claim line", "goes this way, never as text",
              "copies the standing note of `.superlite/briefs/lead.md`",
              "A brief you write by hand goes to `.superlite/briefs/fix-<id>.md`, never `.superlite/fixes/`",
              "A claim only records the ruling and prints `next: commit_task Tn`",
              "With autocommit off, a dirty `git status` after `commit_task` is normal: it stores a hidden checkpoint under `refs/superlite/`",
              "a format command that takes no paths is the coordinator's, once at the final-review gate"):
        assert TEXT.count(s) == 1, s
    assert TEXT.index("A brief you write by hand") > TEXT.index("**Fleet on:**")
    assert TEXT.index("A brief you write by hand") < TEXT.index("A file no task owns goes to the closest committed task")
    assert TEXT.index("A claim only records") > TEXT.index("- **Outside Owns:**")
    assert TEXT.index("With autocommit off, a dirty `git status`") > TEXT.index("`commit_task <Tn>`; report a closed list.")
