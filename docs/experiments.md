# Experiments: comparing run configs

A run config (see [config.md](config.md)) fixes the lead model, effort, window, denied tools, MCP servers and worker models. An experiment compares two or more of them on real work and says, with an interval, whether a cheaper one costs quality.

## A first experiment, end to end

1. Define the arm in the project's `.superlite/run-configs.json`, next to the built-in `default`, for example a `cheap` config with a smaller lead model. Check it with `python skills/subagent-driven-development/scripts/run_config.py show --config cheap`.
2. Declare the experiment: `sl experiment set --id cheap-vs-default --arms default,cheap --batches 10`. Optional: `--margin 10` (points of quality you accept losing), `--min-per-arm 5`, `--seed N`, `--force` (allow arms that differ in more than one factor). State lives in `.superlite/experiments.json`.
3. Per backlog batch: `sl experiment next --batch B` assigns an arm (from an order fixed at `set`) and prints it, then `sl backlog start B --config <arm>`. The assignment is stored, so asking again for the same batch returns the same arm.
4. Each batch's cost row in `.superlite/batch-costs.jsonl` carries `config`, `experiment` and `arm`; the run's history rows carry `run_config`.
5. `sl experiment report cheap-vs-default` prints per arm the batches, cost and quality with bootstrap intervals, the difference against the first arm, and a verdict (`--json` for the data, `--margin` and `--min` to override the stored values).

Quality is `100 - 10 x grade points` of the batch. That mapping is an assumption, not a measurement.

## Offline replay

Replay runs recorded cases through each arm without touching the backlog, and writes rows of the same shape as the cost rows.

Cases file: a JSON list; each case has `id`, `repo` (a local repository), `base` (the commit to start from), `title`, `body`, `test_cmd` (the repository's own tests) and optionally `hidden_test` (`{"path": ..., "source": ...}`: the hidden test file, copied from `source` next to the cases file to `path` in the clone after the agent has finished; `hidden_cmd` overrides the command that runs it).

    python bench/mechanical_ab.py replay cases.json --arms default,cheap --n 3 --seed 1 --experiment cheap-vs-default

- `--n` trials per case and arm (at least 3); the order is shuffled by `--seed`.
- `--cost-cap` (default 10 USD) stops spending; the remaining trials are written as `skipped`.
- `--dry-run` prints the planned order and the resolved config ids without running anything.
- `--agent-cmd` and `--judge-cmd` replace the agent and the judge; the agent command may use `{prompt_file} {model} {effort} {budget} {arm} {workdir}`, the judge `{diff_file} {title}`. The tests use a fake agent and a fake judge (`tests/bench/fixtures/replay/`), never a live agent.
- Output: `replay.jsonl` in `--out` (default under the bench results folder). Read it with `sl experiment report <id> --rows <that file>`.

## What a sound comparison needs

- The same task for every arm (replay), or randomised batches (online).
- Repeated trials: 3 or more per task and arm in replay, 5 or more batches per arm online.
- One factor per experiment: two configs that differ in model and effort and window tell you nothing about which one mattered. `sl experiment set` refuses arms that differ in more than one factor unless you pass `--force`, and prints the factor.

## Noise

Quality gaps under about 3 points, and cost intervals that cross zero, are noise. The verdict only calls an arm cheaper or no worse when the interval says so against the margin; with too few batches it says so and decides nothing.

## What `claude plugin eval` covers, and what it does not

It covers prompt-level cases with graders, several runs per case, a baseline with and without the plugin, and one `--model` for all cases.

It cannot compare two run configs of the same plugin, run a fleet over several sessions, start from a repository state at a base commit with hidden tests, or produce batch cost rows. Those are what the arms above and the replay are for.
