from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

def norm(rel):
    return " ".join((ROOT / rel).read_text().split())

SDD = [
    "For a Jira key the ship step itself comments the PR link on the issue and moves it to Done, so `B OPEN KEY` means that failed; `status` re-reads every OPEN marker from GitHub or Jira and drops the closed ones.",
    "`--reset` also removes each dropped batch's worktree: it stops its lead, runs the project cleanup command, then `git worktree remove` (a worktree with uncommitted changes stays) and `git branch -d` (a branch with unmerged commits stays); each prints one line.",
    "For a Jira key `merge` adds no `Closes` line; after the merge it comments `Shipped in <PR URL> (superlite batch B, version V).` on the issue and moves it to Done through `acli`, and prints `OPEN KEY` and a `jira KEY: <step> failed: <error>` line only when that failed.",
    "Resources named after a worktree (simulators, build folders): the main checkout's `.superlite/cleanup-cmd.json`, `{\"cleanup\": \"<shell command>\"}`, runs in the worktree right before `maxapp ship` removes it (`merge`, `ship B done`, `plan --reset`); `{worktree}` and `{branch}` expand shell-quoted, and `SUPERLITE_WORKTREE`, `SUPERLITE_BRANCH` and `SUPERLITE_BATCH` are set; a failure prints one `B project cleanup: ...` line and never stops the ship.",
]
CMD = [
    "`--reset` also removes each dropped batch's worktree (its lead stopped and the project cleanup command run first); a worktree with uncommitted changes and a branch with unmerged commits stay, each named in one line.",
    "A `B OPEN #N` (Jira: `B OPEN KEY`) line names an issue the merge could not close: for Jira the ship step already commented the PR link and moved the issue to Done, so OPEN means that failed; `status` re-reads every OPEN marker and drops it once the issue is closed.",
    "Simulators, build folders and other resources named after a lead's worktree: put a cleanup command into `.superlite/cleanup-cmd.json` as `{\"cleanup\": \"<shell command>\"}` (`{worktree}` and `{branch}` expand shell-quoted); it runs before each worktree goes.",
]

def test_sdd_backlog_doc_names_jira_close_status_reread_and_cleanup():
    t = norm("skills/subagent-driven-development/backlog-main.md") + " " + norm("skills/subagent-driven-development/backlog.md")
    for x in SDD:
        assert x in t
    assert "A `B OPEN #N` line names an issue the merge left open" in t and "its worktree kept" in t

def test_backlog_command_names_reset_removal_open_reread_and_cleanup():
    t = norm("commands/backlog.md")
    for x in CMD:
        assert x in t
    assert "B OPEN #N" in t and "its worktree kept" in t
