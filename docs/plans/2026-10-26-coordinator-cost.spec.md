# Coordinator cost: bookkeeping and false refusals the coordinator pays for

Origin: the superlite 1.2.1 build on 2026-10-26 (docs/plans/2026-10-26-session-friction.report.md). Agents cost
$2.08, the coordinator $4.05: about half of its 27 Bash turns were pool.json edits, guessed `context_k`, and
hand-made commits after `commit_task` and `autocommit apply` refused. Issues #13, #14, #17, #18.

## 1. Per-caller test wait (#14)

- `run_tests --background` writes one `test-summary.latest` pointer per `.superlite`; `--wait` reads it. Two
  implementers running fast tests at once can wait on each other's run and call a red task green.
- Wanted: `--wait PATH` waits on exactly that run's summary file (the `summary: <path>` line `--background`
  prints), exit 0 green, 1 red, 2 timeout or missing. Bare `--wait` keeps today's shared pointer for the
  coordinator's single full-suite wait. `--background` prints a second line `wait: bash "$SL" run_tests --wait <path>`
  so an agent copies it verbatim. Agent prompts and the skill text say `--wait <path>`.

## 2. Pool bookkeeping by script (#13)

- The coordinator hand-edits `.superlite/pool.json` (busy, current, context_k) with Python heredocs; `context_k`
  is guessed, so `dispatch` evicts agents at "context over 80k" that are nowhere near it, and a fresh implementer
  re-reads the prime.
- Wanted: `sl pool` with `add ID --tier T [--current Tn]`, `busy ID Tn`, `free ID`, `list`, `sync`. `sync` fills,
  per agent, `context_k` from the agent transcript's last assistant message usage (input + cache read + cache
  write tokens, in thousands; the stop hook already records the transcript path in `.superlite/metrics.jsonl`),
  `idle_min` from its latest stop record, and clears `busy` when a stop record is newer than the `busy` call.
  `dispatch` and `commit_task --dispatch` run `sync` first, so the coordinator never edits pool.json and
  `context_k` is real. An agent with no transcript keeps its current value (`DEFAULT_CONTEXT_K` on `add`).
  Every subcommand writes atomically and prints one line.

## 3. Plan folder never blocks a checkpoint (#18)

- `commit_task` printed `out-of-scope docs/plans/<topic>.spec.md` for the plan's own sibling spec and committed
  nothing; the plan file itself is tolerated, a sibling is not.
- Wanted: any changed or untracked file under the plan's own folder (the directory of `--plan`) is treated like
  `.superlite/`: never staged, never an `out-of-scope` block. A task that `Owns` a path under that folder still
  commits it.

## 4. autocommit apply on a moved HEAD (#17)

- `autocommit apply` refused with `HEAD moved since the run started` after any manual commit on the branch,
  and the coordinator recreated the commits by hand.
- Wanted: when HEAD moved but the commits between the recorded start and HEAD touch none of the checkpointed
  files, `apply` replays each checkpoint onto the current HEAD, in order, taking each checkpoint's version of
  its own files (the files it listed, including deletions); same one-commit-per-task output as today. When
  one of those commits touched a checkpointed file, `apply` still refuses and names the file(s). The branch
  check and the `unrelated changes` check stay.

## Validation

- Script tests under tests/scripts cover each wanted behaviour and the refusals that stay.
- Full suite green (`sl run_tests --full`), version bump to 1.2.2 with `scripts/bump-version.sh`.

## Out of scope

- Issues #8, #10, #11, #12, #15, #16, #19.
- Changing the 80k context ceiling or the scoring in assign.
