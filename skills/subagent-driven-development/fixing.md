# Fixing: routing, escalation, contract

The coordinator never edits source or tests and never runs raw `pytest`. Every fix goes to a fix-only agent.

| Tier | Agent | Use when |
|---|---|---|
| 1 | `superlite:fixer-sonnet` (sonnet, medium) | Cause known, including a fully specified change (exact `file:line`); fix confined to one module, plus a regression test. |
| 2 | `superlite:fixer-sonnet-high` (sonnet, high) | Cause known, but the fix spans modules or a seam, or a known probe class (deep recursion, huge input, protocol edge). |
| 3 | `superlite:fixer-opus` (opus, high) | Cause unknown and needs diagnosis, or a lower tier failed 2 rounds. |

Haiku never fixes: a fix keeps a decision. Haiku stays only as `implementer-haiku` on `Kind: mechanical` tasks.

**Fleet on:** final-review and package-review findings go through `"$SL" findings route --plan PLAN <report json>...`, which writes one brief per owning task and prints `fixer tier=T brief=P files=F task=Tn`; each line is a fresh fixer worker: `"$SL" fleet spawn --role fixer --tier T --plan PLAN`, then `"$SL" fleet send Wn --brief P --plan PLAN`. Escalation sends the same brief to `--tier` one up. A file the fix needs outside its findings goes in with `--also F` (the call writes one brief) or `--also Tn=F` (that task's brief): the brief lists it with its claim line, so the fixer's commit takes it; a ruling that lets a fixer touch another file goes this way, never as text. Every brief copies the standing note of `.superlite/briefs/lead.md` and, in a superlite worktree, names the worktree's `sl` for the tools it touches.

A brief you write by hand goes to `.superlite/briefs/fix-<id>.md`, never `.superlite/fixes/`: that folder holds the fixers' notes, and a fixer rewrites its note there every round, so a brief in it is lost.

A file no task owns goes to the closest committed task that is not in progress; a `task=coordinator` line (every owner, or every committed task, in progress) is a brief whose fixer does not commit (`commit: held for the coordinator`): once those tasks are done, commit an owned file with its owner's `commit_task Tn` and an unowned one with `commit_task Tn --also F --ruling "final-review fix outside every Owns"` for a committed task.

- **Escalation:** after 2 failed rounds at a tier, move up one. Log each failed round with `incident`.
- **Outside Owns:** a fixer touching a file outside its task's Owns runs `commit_task Tn --claim F --ruling "..."` first. A claim only records the ruling and prints `next: commit_task Tn`; that later `commit_task Tn` commits F with the task. To commit F with Tn now: `commit_task Tn --also F --ruling "..."`.
- **Owner reuse** (fleet off only): if the task's own implementer is idle, within reuse limits (`max_tasks` of `config/routing.json`, <=40k context for fix work, <=50 min idle) and its model matches the tier, send it a fix-only brief instead of a fresh fixer. Over 40k context, start a fresh fixer instead.

Safe edits (agents/fixer-*.md, agents/package-reviewer.md): exact-match `Edit` only, a `grep` with zero matches proves a wording fix, waits by completion notice or PID (never a self-matching `pgrep -f`), experiments in a throwaway worktree or reverted with `git apply -R` of an own patch, never `git checkout --` in the shared tree; each fix brief's `Reviewed version:` line names the checkpoint of the reviewed files.

**After the run:** after `sl finish`, a fix in a fresh worktree runs `"$SL" fleet spawn --role fixer --tier T --brief <abs brief> --wait --plan <worktree>/.superlite` (fleet on: the session's fleet follows there; fleet off: the fixer Agent as usual); the fixer commits with a plain git commit, no commit_task.

## Fix notes: compaction in a file

Subagents can't compact themselves, so the working state of a fix lives in `.superlite/fixes/<id>.md`, not in a long session. Give each finding an id in the brief (`F-<Tn>-<n>`). Every fixer round ends by rewriting that note, cumulatively, in at most 1,500 chars:

```
# F-T4-2 · tier 1 · round 1 · NOT_FIXED
Goal: <the finding and what done looks like, one line>
Where: <file:line-range for each relevant span>
Changed: <file:lines - what - why>, or "nothing kept"
Tried and failed: <attempt - failure - reason>, newest first
Evidence: <failing test or probe id - one-line error>
Next: <best next hypothesis, and which spans to read first>
```

- **A later round never resumes the old session.** Start a fresh agent (round 2 at the same tier, or the next tier on escalation) whose brief is only `$SL`, `Tn`, the finding id and "read `.superlite/fixes/<id>.md` first". Paste no transcript or report into it.
- This keeps each round's context to the note plus the spans it names, roughly 10-20k instead of a reused 60-100k session. Escalation needs it anyway, since a different model shares no cache.
- `.superlite/` is never committed. Notes still marked NOT_FIXED after the last tier become a `Ruling:` and go in the closing message.
- **Package reviewers** still fix what they find, but must close every finding, including ones sent later, and report a closed list.
- **Final reviewer** only reports findings. They go to fixers, routed by tier and split by file.
- **Probe failures:** a failure ruled no defect: `"$SL" probe_run --dismiss ID --plan PLAN` (ID: generated test name, group id or probe id); it deletes the generated test and closes its incident, and later runs list it under `results["dismissed"]`. `lint` prints `ADAPTER:` when it rebuilt the probe adapter and `RUN:` when you must (`plan_tools adapter`). `commit_task` prints `Tn: probe files committed: ...` when a checkpoint took generated probe files.
- **Fixer contract:** fix only the named findings; one regression test per fix that fails without it, except a doc- or comment-only fix (docs, comments or prompt wording, no code a test runs): it gets a check only when one fails without the fix, never a test that passes either way, and its report line ends `no test: doc-only`; run each regression test red before its fix (a fix already in place is taken out by hand for that run) and end its `FIXED` line `- red: <that run's summary line>`; run `"$SL" run_tests --fast PATHS --background` on the touched files, then run the printed `wait:` line (`run_tests --wait <path>`) in the foreground (never as a background command) and end the turn only after it reports; `commit_task <Tn>`; report a closed list. With autocommit off, a dirty `git status` after `commit_task` is normal: it stores a hidden checkpoint under `refs/superlite/`, not a commit on the branch. Format only the files you changed (their paths to the project's format command), never the whole tree; a format command that takes no paths is the coordinator's, once at the final-review gate. A report with `commit: denied` means the harness refused the fixer's commit: run `commit_task Tn` yourself, and tell the user `/superlite:setup` offers the allow rule (`docs/config.md`, Permissions). Never refactor, never touch files outside the finding.
- Never pass `model` to an agent call (it overrides the agent file). Never dispatch an extra or ad-hoc reviewer, and never `general-purpose` for build, review or fix work. An inadequate review gets a `Ruling:`.
- **Mechanical misses:** when an `implementer-haiku` task ends NEEDS_CONTEXT, BLOCKED or red, route it to tier 1 (`fixer-sonnet`) with a fix note, and run `sl routing miss --task Tn --plan PLAN` (logs `kind-miss Tn`; the task is never retried on Haiku) so the first-time pass rate of mechanical tasks can be measured.
