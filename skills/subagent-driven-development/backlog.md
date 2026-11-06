# Backlog mode: batch leads

`/superlite:backlog` works an issue backlog. Main plans and decides; one lead per batch builds, reviews and ships in its own worktree. `SL` = `<plugin root>/skills/subagent-driven-development/scripts/sl`.

## Main

Main keeps a lean context: never read issue bodies, lead transcripts, panes or reports.
1. `"$SL" backlog status` first and after any compaction. Columns: batch, state (planned, running, needs_decision, parked, shipped), topic, issues, PR.
2. `"$SL" backlog plan` as a background command (`--tier sonnet`, `--timeout-min 60`, `--reset`).
3. `"$SL" backlog decide --print`, ask with AskUserQuestion (at most 4 per call), answers file `.superlite/backlog-answers.json`, `"$SL" backlog decide --file F`. One ship approval covers all batches.
4. `"$SL" backlog start [B] [--cap 2] [--model opus]`. Exit 3 (Herdr missing) is BLOCKED.
5. `"$SL" backlog wait` as a background command: one line per lead that ends (shipped, parked, needs_decision, BLOCKED). On needs_decision: ask, write the answers file, `"$SL" backlog answer B --file F`. A `B OPEN #N` line names an issue the merge left open; `status` shows it too.
6. Hold work: `"$SL" backlog skip <issue>` drops an issue from its batch (a batch left empty is dropped) and keeps it out of every later plan; skip umbrella and tracking issues. `"$SL" backlog park B --reason R` holds a planned batch: plain `start` skips it, `status` shows the reason, and only `start B` starts it.

## Lead

You are a lead: a fleet worker of main's run for one batch, in your own worktree, with its own run and fleet. Read your brief at `.superlite/briefs/lead.md`.
- Write a plan with `--plan` (superlite plan flow), build it with your own fleet, review it, then ship.
- Never end your turn while your workers run: wait with `fleet wait`.
- Never ask the user. A question for the human goes to `.superlite/question.json` (`{"questions": [...]}`, AskUserQuestion shape), then end with `Status: NEEDS_DECISION`. Main answers into `.superlite/answer-<n>.json`; you are resumed with it.
- Test layers: a plan with `LAYERS:` runs via `fleet run --layer`; fix RED before shipping.
- Keep your notes in `.superlite/notes.md`, each follow-up one self-contained line, and the PR text in `.superlite/pr-body.md` with one `Closes #N` line per issue (`Fixes #1, #2` closes only #1). `merge` adds a missing line and prints `OPEN #N` for an issue still open after the merge.
- Ship in four steps, each one bare command `"$SL" backlog ship B ...` (`--plan .superlite` is accepted): no `cd` (you start in your worktree), no pipe, no `echo`, no `&&` chain, since the allow rules match only a command that starts with `"$SL" backlog ship` or `maxapp ship`:
  1. `"$SL" backlog ship B lock [--wait 500]`: take the machine-wide ship lock. exit 4 means wait and rerun.
  2. `bump [--version X]`: bump the version on your branch. exit 5 is a CONFLICT: rebase and rerun.
  3. `merge [--title T] [--body-file F]`: run `maxapp ship`; give the Bash call a timeout of 600000 ms. exit 6 is RED: fix the checks, rerun.
  4. `release`: free the lock. `release --park R` frees it and parks the batch with reason R.
- Exit codes: 0 done, 2 refused, 3 BLOCKED, 4 WAIT/RERUN, 5 CONFLICT, 6 RED.

## Permissions

A lead runs with `--permission-mode auto`, allowed tools `Bash(maxapp ship *)` and `Bash(<abs sl> backlog ship *)`, and AskUserQuestion disallowed (spike S3). Every other permission dialog in a fleet pane is answered no by the `PermissionRequest` hook (`hooks/deny-worker-permission`); the worker ends BLOCKED or NEEDS_DECISION instead of retrying.

## Limits

`maxapp ship` fast-forwards the main checkout: keep it on its default branch and clean while leads ship.
