# tests/scripts/test_fleet_roles_docs.py
from test_plan_tools import ROOT

def read(rel):
    return (ROOT / rel).read_text(encoding="utf-8")

def test_fixing_md_routes_fleet_fixes():
    t = read("skills/subagent-driven-development/fixing.md")
    for s in ('"$SL" findings route', "fleet spawn --role fixer --tier", "fleet send Wn --brief", "(fleet off only)", "fresh fixer worker"):
        assert s in t, s
    assert 'bash "$SL"' not in t

def test_docs_fleet_md_covers_roles():
    t = read("docs/fleet.md")
    for s in ("--role", "fixer", "package-reviewer", "final-reviewer", "research", "--effort", ".superlite/briefs/",
              "auto mode", "CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=0", "findings=", "findings route", "fleet run --layer",
              "APPROVED", "CHANGES_REQUESTED", "fleet off", "agents/researcher.md"):
        assert s in t, s
    assert "Reviewers, fixers and the final reviewer stay in-process" not in t
    assert "only implementer tasks of a taskgraph plan run in panes" not in t

def test_docs_fleet_md_keeps_earlier_contract_words():
    t = read("docs/fleet.md")
    for s in ("before the first dispatch", "sl-<repo>-<worktree>-w", "implementer", "in-process", "report BLOCKED",
              "never fall back to in-process", "4 panes", "20 rows", "fleet/agents"):
        assert s in t, s

SAFE_AGENTS = ("agents/fixer-opus.md", "agents/fixer-sonnet-high.md", "agents/fixer-sonnet.md", "agents/package-reviewer.md")
SAFE_EDITS = [
    "- Edits: change source files with exact-match `Edit` calls only and re-read the changed lines after each edit; never a bulk regex, `sed -i` or script rewrite of a source file (a broad pattern can match an earlier, similar string and delete code). A `Reviewed version:` line in the brief names the checkpoint holding the reviewed files: `git show <sha>:<path>` prints a file as reviewed.",
    "- Wording or rename fix: prove it with a `grep` that shows zero matches of the old text and say so on its report line (`- grep: 0 matches`). A `run_tests --fast` run over docs-only files that matched no test is no pass; never report it as one.",
    "- Waiting: wait for a background command through its completion notice or by its PID (`wait <pid>` in the shell that started it), never with `pgrep -f` on a string the waiting command line itself contains: the pattern matches the waiting shell, so the wait never ends.",
    "- Experiments: run a diagnosis experiment in a throwaway worktree (`git worktree add --detach <dir under .build/> <sha>`, then `git worktree remove` it), or save the experiment's own diff as a patch under `.superlite/` and revert it with `git apply -R` of that patch; never `git checkout --`, `git restore` or `git stash` in the shared tree, where other workers have uncommitted edits. Before your report, `git diff` of the files you touched holds only your fix; the report says `shared tree: only the fix`.",
]
OUTSIDE_RUN = "- Outside a run (the brief names no task id `Tn` and no plan, or says outside a run): commit only the files you changed (your fixes and their regression tests) with plain `git add <files>` and `git commit` in the brief's folder once their focused tests pass; leave every other file as it is, and a fix that needs a file outside the brief's folder or scope stays open (`out of scope: ...`). Inside a run every rule above stays; this rule is the one exception to the `git add` and `commit` ban."
FIXING_LINE = "Safe edits (agents/fixer-*.md, agents/package-reviewer.md): exact-match `Edit` only, a `grep` with zero matches proves a wording fix, waits by completion notice or PID (never a self-matching `pgrep -f`), experiments in a throwaway worktree or reverted with `git apply -R` of an own patch, never `git checkout --` in the shared tree; each fix brief's `Reviewed version:` line names the checkpoint of the reviewed files."

def test_safe_edit_block_in_fixers_and_reviewer():
    for f in SAFE_AGENTS:
        lines = read(f).splitlines()
        for b in SAFE_EDITS:
            assert lines.count(b) == 1, (f, b[:30])
        i = next(n for n, l in enumerate(lines) if l.startswith("- Format only the files you changed"))
        assert lines[i + 1:i + 5] == SAFE_EDITS, f

def test_safe_edit_rules_name_the_hazards():
    for f in SAFE_AGENTS:
        t = read(f)
        for s in ("exact-match `Edit`", "re-read the changed lines", "zero matches", "`pgrep -f`", "`git apply -R`",
                  "throwaway worktree", "never `git checkout --`", "shared tree: only the fix"):
            assert s in t, (f, s)

def test_package_reviewer_commits_outside_a_run():
    t = read("agents/package-reviewer.md")
    assert OUTSIDE_RUN in t.splitlines()
    desc = next(l for l in t.splitlines() if l.startswith("description:"))
    assert "outside a run" in desc.lower()
    never = next(l for l in t.splitlines() if l.startswith("- Never run `git add`"))
    assert "The coordinator commits" in never

def test_fixing_md_names_safe_edits():
    t = read("skills/subagent-driven-development/fixing.md")
    assert FIXING_LINE in t.split("\n\n")
    assert t.index(FIXING_LINE) < t.index("**After the run:**")
