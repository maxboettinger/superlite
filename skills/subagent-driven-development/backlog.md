# Backlog mode: batch leads

`/superlite:backlog` works an issue backlog. Main plans and decides; one lead per batch builds, reviews and ships in its own worktree. `SL` = `<plugin root>/skills/subagent-driven-development/scripts/sl`.

## Main

Main keeps a lean context: never read issue bodies, lead transcripts, panes or reports.
Start main in a fresh session: one that already loaded another superlite skill or command (start, brainstorming, writing-plans, subagent-driven-development, finishing) tells the user to run `/clear` and `/superlite:backlog` again, and ends its turn.
1. `"$SL" backlog status` first and after any compaction. Columns: batch, state (planned, running, needs_decision, parked, shipped), topic, issues, PR.
2. `"$SL" backlog plan` as a background command (`--tier sonnet`, `--timeout-min 60`, `--reset`). Over-long question texts are cut, not refused: a header to 12, an option label to 60 and an option description to 200 characters (a ` (Recommended)` suffix kept), each cut named in a `shortened: "<question>" <field>: N -> M characters` line (at most 5, then `shortened: K more`); a question over 300 characters still fails the plan.
3. `"$SL" backlog decide --print`, ask with AskUserQuestion (at most 4 per call), answers file `.superlite/backlog-answers.json`, `"$SL" backlog decide --file F`. One ship approval covers all batches.
4. `"$SL" backlog start [B ...] [--cap 2] [--model opus]`. Several ids (`start B7 B10`) are checked one by one: each refused batch prints its `BLOCKED:` reason first, the others still start, and the exit is 2 when any was refused. Exit 3 (Herdr missing) is BLOCKED.
5. `"$SL" backlog wait` as a background command: one line per lead that ends (shipped, parked, needs_decision, BLOCKED). On needs_decision: ask, write the answers file, `"$SL" backlog answer B --file F`. A `B OPEN #N` line names an issue the merge left open; `status` shows it too. A lead that stops without a Status line gets one re-prompt (no wait line); its next such stop parks the batch with `no status in stop text: <text>`, and `start` or `answer` resets the count. A stop whose transcript lags (blank, or without the status its cut `last` line holds) is re-read for 10 s from the stop; after that a cut line with a status parks the batch with `<cut line> (transcript unread)`, one without gets the re-prompt.
6. A batch whose lead could not merge (its merge step was denied, so the lead ended BLOCKED and `wait` parked it) is main's to ship with one command: `"$SL" backlog ship B merge --from-main` (main only, refused in any fleet worker; it needs the ship approval, a parked batch and its bumped version). It takes the ship lock as main, rebases the worktree onto the default branch, bumps the version again when the default branch already has it, runs `maxapp ship`, then marks the batch shipped, records its PR and version, writes its summary, releases the ship lock and stops its lead. exit 4 is WAIT or RERUN: run it again. A CONFLICT (5), RED (6) or BLOCKED (3) releases the lock and keeps the batch parked with the reason; `"$SL" backlog start B` resumes its lead to fix a conflict or a red check. A batch main shipped by hand (`maxapp ship -C <worktree>`) is recorded with `"$SL" backlog ship B done --pr N [--version X]` (main only; `gh pr view N` must read MERGED).
7. Hold work: `"$SL" backlog skip <issue>` drops an issue from its batch (a batch left empty is dropped) and keeps it out of every later plan; skip umbrella and tracking issues. `"$SL" backlog park B --reason R` holds a planned batch: plain `start` skips it, `status` shows the reason, and only `start B` starts it.

## Lead

You are a lead: a fleet worker of main's run for one batch, in your own worktree, with its own run and fleet. Read your brief at `.superlite/briefs/lead.md`.
- Write a plan with `--plan` (superlite plan flow), build it with your own fleet, review it, then ship.
- Never end your turn while your workers run: wait with `fleet wait`.
- Never ask the user. A question for the human goes to `.superlite/question.json` (`{"questions": [...]}`, AskUserQuestion shape), then end with `Status: NEEDS_DECISION`. Main answers into `.superlite/answer-<n>.json`; you are resumed with it. `backlog wait` checks that file strictly and never cuts it: 1 to 4 distinct questions, each question 1 to 300 characters, a header of 1 to 12, 2 to 4 options with distinct labels of 1 to 60 and descriptions up to 200; an invalid file parks the batch with `invalid question.json: <errors>`.
- Test layers: a plan with `LAYERS:` runs via `fleet run --layer`; fix RED before shipping.
- Keep your notes in `.superlite/notes.md`, each follow-up one self-contained line, and the PR text in `.superlite/pr-body.md` with one `Closes #N` line per issue (`Fixes #1, #2` closes only #1). `merge` adds a missing line and prints `OPEN #N` for an issue still open after the merge.
- Ship in four steps, each one bare command `"$SL" backlog ship B ...` (`--plan .superlite` is accepted): no `cd` (you start in your worktree), no pipe, no `echo`, no `&&` chain, since the allow rules match only a command that starts with `"$SL" backlog ship` or `maxapp ship`:
  1. `"$SL" backlog ship B lock [--wait 500]`: take the machine-wide ship lock. exit 4 means wait and rerun.
  2. `bump [--version X]`: bump the version on your branch. exit 5 is a CONFLICT: rebase and rerun.
  3. `merge [--title T] [--body-file F]`: run `maxapp ship`; give the Bash call a timeout of 600000 ms. exit 6 is RED: fix the checks, rerun. A denied merge (the permission check or the auto-mode classifier refuses the Bash call, no exit code) is not retried: run no `release` and end with `Status: BLOCKED merge denied: main runs sl backlog ship B merge --from-main`.
  4. `release`: free the lock. `release --park R` frees it and parks the batch with reason R.
- Exit codes: 0 done, 2 refused, 3 BLOCKED, 4 WAIT/RERUN, 5 CONFLICT, 6 RED.

## Permissions

A lead runs with `--permission-mode auto`, allowed tools `Bash(maxapp ship *)` and `Bash(<abs sl> backlog ship *)`, and AskUserQuestion disallowed (spike S3). Every other permission dialog in a fleet pane is answered no by the `PermissionRequest` hook (`hooks/deny-worker-permission`); the worker ends BLOCKED or NEEDS_DECISION instead of retrying.

## Limits

`maxapp ship` fast-forwards the main checkout: keep it on its default branch and clean while leads ship.
