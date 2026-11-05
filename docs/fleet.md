# Fleet mode

## What it is

With fleet mode on, a superlite run executes its implementer tasks in real Claude Code sessions that live in Herdr panes: one worker per pane (`W1`, `W2`, ...), each started under the subscription account with the most headroom. The coordinator keeps the same loop (dispatch, task message, report, `commit_task`, reviews). You can watch and steer every worker in Herdr: worker `W1` appears there as the agent `sl-<run folder>-w1` (lowercase, at most 32 characters). Herdr keeps agent names unique per server, so two runs at the same time need run folders with different names.

Turn it on by asking the coordinator to "use fleet": it runs `sl fleet on` before the first dispatch. Without that every agent stays in-process and Herdr shows only the coordinator. Fleet covers the implementer tasks of a plan with a taskgraph. Reviewers, fixers and the final reviewer stay in-process and get no pane (an in-process subagent has no terminal for Herdr to show); an inline build without a taskgraph starts no worker.

## Prerequisites

- A running Herdr server and `herdr` on PATH (or `SUPERLITE_HERDR_BIN`).
- Each account's `CLAUDE_CONFIG_DIR` logged in once (run `claude` in it). The default account (`~/.claude`) is started with the variable unset: set to that path, Claude Code starts its first-run setup.
- Account names need `claude-profile` (it maps a name to its config dir and ranks accounts by usage). Config dir paths (an entry with a slash or starting with `~`, e.g. `--accounts ~/.claude-account1`; the account name is its basename) work without it, and `current` always works. Without `claude-profile`, a bare name fails at spawn with `BLOCKED: no config dir for account <name> (claude-profile list unavailable; pass a config dir path instead)` and `fleet on` prints a warning; the first allowed account is used. Without any account list, the single account `current` (the coordinator's own config dir) is used.

## Commands

Run as `"$SL" fleet ...`. All take `--plan PLAN` to find the run.

- `fleet on [--accounts claude1,claude3]` turns fleet mode on (default order: the `--accounts` flag, then `SUPERLITE_FLEET_ACCOUNTS`, then every account `claude-profile list --json` returns, then `current`).
- `fleet spawn --tier sonnet` starts a worker and primes it; prints `W1 account=claude1 pane=w6:p1 agent=superlite:implementer`. Exit 3 with `BLOCKED: ...` when no account has headroom or startup fails.
- `fleet send W1 T3 --plan PLAN` sends a task (`W1 T3 T4` for a batch); prints `W1 T3 sent`, or `W1 T3,T4 sent` for a batch. `fleet send W1 --text "use the v2 API"` sends free text, for example an answer to NEEDS_CONTEXT.
- `fleet wait [--timeout 540000] [W1 ...]` waits for busy workers. Prints `W1 T3 DONE <report path>` (reports are in `.superlite/fleet/reports/`), `W1 T3 BLOCKED-UI <screen path>` plus the screen's last lines, and `TIMEOUT W1 W2` (space-separated) for the rest.
- `fleet keys W1 Down Enter` sends keys to a worker's pane, for a dialog.
- `fleet status` prints `fleet: on` and one line per worker.
- `fleet stop W1` or `fleet stop --all` closes workers (`--all` also closes the workspace).
- `fleet off` stops all workers and turns fleet mode off.

## How a run looks

dispatch prints `fresh tier=T agent=TYPE` or `agent=Wn` (never `poll`) -> `fleet spawn` (fresh only) -> `fleet send` -> `fleet wait` -> `commit_task`. State lives in `.superlite/fleet.json`; screens in `.superlite/fleet/screens/`. None of it is committed.

## Smoke test

From the 2026-11-05 spike. Run in a scratch project with Herdr running.

| Step | Do | Expect |
|---|---|---|
| 1 Spawn under an account | `fleet on --accounts claude1`, then `fleet spawn --tier sonnet --plan PLAN` | `W1 account=claude1 pane=... agent=superlite:implementer`; `fleet status` shows `W1 ready` |
| 2 Prompt and wait | `fleet send W1 T1 --plan PLAN`, then `fleet wait` | `W1 T1 DONE <path>` and a report file |
| 3 Blocked on a dialog | Send a task whose work triggers a permission dialog, then `fleet wait` | `W1 T1 BLOCKED-UI <screen>`; `fleet keys W1 Enter` (or another answer) lets it continue |
| 4 Three workers | `fleet on` without `--accounts`, spawn three workers | Panes split in one workspace; accounts spread by headroom (two or three accounts) |
| 5 Subagents read as working | Send a task that makes a worker start its own subagents | Observe whether Herdr keeps the worker in state `working` while its subagents run, so `wait` does not report early. If it reads `idle` or `done` early, note it as a finding; this is not guaranteed |

## Troubleshooting

- Trust dialog (`Yes, I trust this folder`): accepted automatically at spawn.
- `Select login method` or another startup block: the account's login expired. Run `claude` once in that account's config dir. The screen is in `.superlite/fleet/screens/Wn.txt`.
- `BLOCKED: Wn no READY`: the prime prompt did not land. Check with `herdr agent read sl-<run folder>-wn`.
- `agent_prompt_stalled` (a herdr error code, shown in the `error:` line): the worker was mid-turn. Run `fleet wait`, then resend.

## Limits

- Workers share the checkout, so tasks must own disjoint files (the plan already guarantees this).
- No account swap mid-run: a worker keeps its account until stopped.
- Reviewers, fixers and the final reviewer stay in-process; only implementer tasks of a taskgraph plan run in panes.
