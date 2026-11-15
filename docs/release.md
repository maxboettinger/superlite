# Releases

## Version rule

- A lead bumps the patch number at ship, and the merged version gets the annotated tag `v<version>`.
- Minor and major versions only through `sl release minor|major`, in the maintainer's own session, after his confirmation.
- An agent may propose a level with its reason. It never runs the command unasked.
- `sl release` refuses inside a lead or worker (`SUPERLITE_FLEET_WORKER` set) and refuses the level `patch`.
- A patch runs no golden batch.
- A minor release runs 2 golden batches (small, typical), a major release 3 (small, typical, large).
- GitHub release entries and the `stable` branch move only at minor and major.

## `sl release minor|major`

Flags: `--dry-run`, `--no-golden` (only with `--dry-run`), `--accept-flags`, `--root R`.

Steps:
1. Preflight: not in a lead or worker, on the default branch, clean tree, level with origin after `git fetch`, tag `v<next>` absent.
2. Scoreboard: flags stop the run until `--accept-flags`.
3. Golden batches for the level; results go to `.superlite/golden-results.jsonl`.
4. Bump with `scripts/bump-version.sh`, then `claude plugin validate --strict .` (skipped when `claude` is missing).
5. Commit `Release v<version>`, annotated tag, push branch and tag.
6. `gh release create` with generated notes, starting at the last `X.Y.0` tag.
7. Move `stable` to the tag. A failure here is only a warning.

The ship lock is held from the bump to the last push.

Exit codes:
- 0: released, or the dry run is fine
- 1: a golden batch is red
- 2: refused
- 3: a step failed after the bump; the command prints the undo line
- 4: scoreboard flags need `--accept-flags`

`--dry-run` runs the golden batches and prints `would release v<version> (tag v<version>, stable -> v<version>)`.

## Golden cases

A case is `bench/golden/<id>/case.json`: a base commit, frozen issue text, hidden tests taken from a merged pull request, and a baseline cost.

- Make: `sl golden_case make --pr N --id ID --size small|typical|large [--batch B]`
- Check: `sl golden_case verify [ID]` (hidden tests fail at the base commit, pass at the merge)
- List: `sl golden_case list`
- To replace a case: make the new one, verify it, then delete the old directory.

## Golden runs

- `sl golden run [--level minor|major | --ids a,b] [--no-rerun] [--timeout S]` runs cases in sealed copies; nothing is pushed and no pull request is opened.
- A case passes on facts of the run: the lead ended at the ship stop, the cost row has plan tasks, a final review round and a full suite run, and the last full suite run was green.
- The hidden tests are a score, not a gate: they are the original pull request's tests and check choices the issue does not state, so a correct but different solution fails some of them. The row stores `hidden` (counts) and `hidden_share`; a share below the case's earlier runs only warns.
- A case whose lead got no slot (machine busy) prints `NOT RUN`, is stored with `started` false and is not rerun.
- A red case is rerun once unless `--no-rerun`.
- Each attempt saves the lead's change as `.superlite/golden/<case>-<attempt>.patch` and, for red hidden tests, the end of their output in the row (`hidden_out`).
- `sl golden history [ID]` prints stored runs. Once a case has 5 runs it also prints the run-to-run noise.

## Scoreboard

`sl scoreboard [--root R] [--window N] [--json]` reads the shipped batch rows. It compares the last 15 rows with all rows before them.

- Lead cost, total cost, lead turns: medians; flagged above +30 %.
- Points and first-pass rate: means; flagged at +2.0 points or -0.10.
- It needs 15 rows in each part, else it reports not enough rows.

## Install the stable line

`/plugin marketplace add maxboettinger/superlite@stable` (valid from the first minor release)
