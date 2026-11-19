"""The research role runs a read-only Bash allowlist under dontAsk (#809)."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "skills" / "subagent-driven-development" / "scripts"))
import fleet_roles as fr  # noqa: E402

ALLOW = ["Bash(git log *)", "Bash(git show *)", "Bash(git diff *)", "Bash(git status *)", "Bash(git blame *)",
         "Bash(git ls-files *)", "Bash(git rev-parse *)", "Bash(git merge-base *)", "Bash(git cat-file *)",
         "Bash(git worktree list *)", "Bash(git apply --check *)", "Bash(ls *)", "Bash(xcrun simctl list *)"]
DENY = ["Bash(git * --output*)", "Bash(git apply * --apply*)"]


def test_research_bash_allowlist_exact():
    assert list(fr.RESEARCH_BASH) == ALLOW and list(fr.RESEARCH_DENY) == DENY


def test_research_argv_runs_dont_ask_with_the_allowlist():
    argv = fr.launch("research", None, {})["argv"]
    assert argv == ["--agent", "superlite:researcher", "--model", "sonnet", "--effort", "low",
                    "--permission-mode", "dontAsk", "--allowedTools", "Read", "Grep", "Glob", *ALLOW,
                    "--disallowedTools", "AskUserQuestion", *fr.GIT_DENY, *DENY, "Edit", "Write", "NotebookEdit"]
    assert "Bash" not in argv


def test_other_roles_keep_their_tail():
    assert fr.launch("final-reviewer", None, {})["argv"][-len(fr.TAIL):] == fr.TAIL
    assert "dontAsk" not in fr.launch("fixer", None, {})["argv"]


def test_researcher_agent_lists_bash_and_the_allowlist():
    text = (ROOT / "agents" / "researcher.md").read_text(encoding="utf-8")
    assert "tools: Read, Grep, Glob, Bash\n" in text.split("---")[1]
    for cmd in ("`git log`", "`git show`", "`git diff`", "`git status`", "`git blame`", "`git ls-files`", "`git rev-parse`",
                "`git merge-base`", "`git cat-file`", "`git worktree list`", "`git apply --check`", "`ls`",
                "`xcrun simctl list`", "`--output`", "refused command is an answer", "fleet off"):
        assert cmd in text, cmd
