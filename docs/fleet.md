# Fleet mode

## What it is

With fleet mode on, a superlite run executes every role (implementers, fixers, package reviewers, the final reviewer, research, test layers) in real Claude Code sessions or shell panes that live in Herdr: one worker per pane (`W1`, `W2`, ...), each started under the subscription account with the most headroom. The coordinator keeps the same loop (dispatch, task message, report, `commit_task`, reviews, fixes); with fleet off nothing changes and every agent stays an in-process call. You can watch and steer every worker in Herdr: worker `W1` appears there as the agent `sl-<run folder>-<hash>-w1` (lowercase, at most 32 characters; `<hash>` is 4 hex digits of the run root's path, so equal folder names and worktrees with a long shared prefix stay apart). Herdr keeps agent names unique per server.

Turn it on by asking the coordinator to "use fleet": it runs `sl fleet on` before the first dispatch. Without that every agent stays in-process and Herdr shows only the coordinator. With fleet on, an in-process `Agent` call for a superlite role is blocked. Implementer workers cover the tasks of a plan with a taskgraph; an inline build without a taskgraph starts no implementer worker.

Fleet covers the implementer tasks of one taskgraph plan in one checkout: several tickets go into one plan and one run, not one worktree each. Fleet asked for but `sl fleet` unknown (compare `sl version` with the session-start line) or `fleet spawn` exits 3: report BLOCKED with the exact error before any dispatch; never fall back to in-process agents. `sl feedback add` comes in addition, never instead.

## Roles

Start one with `"$SL" fleet spawn --role R [--tier T] --plan PLAN`, then give it a brief with `fleet send Wn --brief FILE`.

| Role | Agent | Model and effort | Prime |
|---|---|---|---|
| `implementer` (default) | `superlite:implementer[-haiku]` | the tier's model (`--tier sonnet` or `haiku`), effort from the agent file | primed with `.superlite/prime.md`, then sent tasks; reused |
| `fixer` | `superlite:fixer-{sonnet,sonnet-high,opus}` (`--tier 1\|2\|3`, or `sonnet\|sonnet-high\|opus`) | sonnet medium, sonnet high, opus high | none; one brief, a fresh worker per fix |
| `package-reviewer` | `superlite:package-reviewer` | sonnet, medium | none; one brief |
| `final-reviewer` | `superlite:final-reviewer` | opus, high; a fresh worker per round | none; `.superlite/review-packet.md` |
| `research` | `superlite:researcher` (`agents/researcher.md`) | haiku, low; read-only (Read, Grep, Glob; no shell) | none; one brief |

The reviewers take no `--tier`; an unknown role or tier exits 2 with `error: ...`. A test layer is not an agent: `fleet run --layer headless|tui|evals` runs `scripts/test_layers.py` in a shell pane and records the role `layer`.

- Every worker gets `--effort` from its agent file (frontmatter effort is ignored in a main-thread session), `CLAUDE_CODE_ENABLE_PROMPT_SUGGESTION=0` and `SUPERLITE_FLEET_ROLE=<role>`.
- Briefs live in `.superlite/briefs/` (inside the worker's cwd; spawn adds `--add-dir` when the state dir is outside it). A brief is a file the worker reads, never pasted text.
- A one-turn worker (everything except the implementer) ends with a status line and one JSON block; `fleet wait` stops it once its status is final.
- Fleet relies on accounts in auto mode. A non-auto account stops reads outside the cwd at a permission dialog, which `wait` reports as `BLOCKED-UI`.

## Capacity

- A tab holds 4 panes and a pane never splits below 20 rows. The fifth worker, or a split that would leave a pane under 20 rows, opens a new tab in the same workspace; the next workers split that tab again.
- Accounts spread over every superlite session on the machine: each spawn records the worker's account in `~/.superlite/fleet/agents/<agent name>`, and the next spawn counts the live workers (`herdr agent list`) of other sessions too, a lead and its workers included, before it picks the account. Without an agent list it counts this run only.
- `current` and config dir entries that `claude-profile` knows are checked against that account's usage and caps like a named account; at its cap they are refused (`BLOCKED: no account with headroom`) and the others get the worker.
- A prime that stalls (`agent_prompt_stalled`) is resent once; a second stall is `BLOCKED`. `BLOCKED: Wn no READY` names the pane size (rows and columns), since a pane too small to show the reply is the usual cause.

## Prerequisites

- A running Herdr server and `herdr` on PATH (or `SUPERLITE_HERDR_BIN`).
- Each account's `CLAUDE_CONFIG_DIR` logged in once (run `claude` in it). The default account (`~/.claude`) is started with the variable unset: set to that path, Claude Code starts its first-run setup.
- Account names need `claude-profile` (it maps a name to its config dir and ranks accounts by usage). Config dir paths (an entry with a slash or starting with `~`, e.g. `--accounts ~/.claude-account1`; the account name is its basename) work without it, and `current` always works. Without `claude-profile`, a bare name fails at spawn with `BLOCKED: no config dir for account <name> (claude-profile list unavailable; pass a config dir path instead)` and `fleet on` prints a warning; the first allowed account is used. Without any account list, the single account `current` (the coordinator's own config dir) is used.

## Commands

Run as `"$SL" fleet ...`. All take `--plan PLAN` to find the run.

- `fleet on [--accounts claude1,claude3]` turns fleet mode on (default order: the `--accounts` flag, then `SUPERLITE_FLEET_ACCOUNTS`, then every account `claude-profile list --json` returns, then `current`).
- `fleet spawn --tier sonnet` (role `implementer`) starts a worker and primes it; prints `W1 account=claude1 pane=w6:p1 agent=superlite:implementer`. Exit 3 with `BLOCKED: ...` when no account has headroom or startup fails.
- `fleet send W1 T3 --plan PLAN` sends a task (`W1 T3 T4` for a batch); prints `W1 T3 sent`, or `W1 T3,T4 sent` for a batch. `fleet send W1 --text "use the v2 API"` sends free text, for example an answer to NEEDS_CONTEXT.
- `fleet spawn --role fixer|package-reviewer|final-reviewer|research [--tier T]` starts a worker of that role (no prime); prints the same line plus ` role=<role>`.
- `fleet send W1 --brief FILE [--label L]` sends a brief file; prints `W1 <label> sent`. The label defaults to the file's name without `.md`.
- `fleet run --layer headless|tui|evals --plan PLAN` runs a test layer in a shell pane (the repo's `scripts/test_layers.py run <layer>`); prints `W5 layer-headless started account=claude3 pane=w6:p2`.
- `"$SL" findings route --plan PLAN REPORT.json ...` turns report findings into fixer briefs; prints `fixer tier=<sonnet|sonnet-high|opus> brief=<path> files=<a,b> task=<Tn>` per brief, or `findings: none`.
- `fleet wait [--timeout 540000] [W1 ...]` waits for busy workers. Prints `Wn <label> <STATUS> findings=<n> <json path>` (`W1 T3 DONE findings=0 <sd>/fleet/reports/T3.json`; the report text is the `.md` next to it) with `<STATUS>` one of `DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`, `APPROVED`, `CHANGES_REQUESTED` or `UNKNOWN` (no parsable block); a line read from the screen ends with ` (screen)`. A layer prints `Wn layer-headless GREEN|RED exit=<n> <log path>` plus its last line. `W1 T3 BLOCKED-UI <screen path>` plus the screen's last lines, and `TIMEOUT W1 W2` (space-separated) for the rest, stay as they were.
- `fleet keys W1 Down Enter` sends keys to a worker's pane, for a dialog.
- `fleet status` prints `fleet: on` and one line per worker.
- `fleet stop W1` or `fleet stop --all` closes workers (`--all` also closes the workspace).
- `fleet off` stops all workers and turns fleet mode off. It writes its state first and closes the workspace last, so it is safe to run from inside the fleet's own workspace.

## How a run looks

dispatch prints `fresh tier=T agent=TYPE` or `agent=Wn` (never `poll`) -> `fleet spawn` (fresh only) -> `fleet send` -> `fleet wait` -> `commit_task`. A review or fix round: `fleet spawn --role package-reviewer|final-reviewer` -> `fleet send Wn --brief` -> `fleet wait` (`APPROVED` or `CHANGES_REQUESTED findings=n`) -> `findings route` -> one fresh fixer worker per printed line. State lives in `.superlite/fleet.json`; screens in `.superlite/fleet/screens/`. None of it is committed.

## Smoke test

From the 2026-11-05 spike. Run in a scratch project with Herdr running.

| Step | Do | Expect |
|---|---|---|
| 1 Spawn under an account | `fleet on --accounts claude1`, then `fleet spawn --tier sonnet --plan PLAN` | `W1 account=claude1 pane=... agent=superlite:implementer`; `fleet status` shows `W1 ready` |
| 2 Prompt and wait | `fleet send W1 T1 --plan PLAN`, then `fleet wait` | `W1 T1 DONE findings=0 <path>` and a report file |
| 3 Blocked on a dialog | Send a task whose work triggers a permission dialog, then `fleet wait` | `W1 T1 BLOCKED-UI <screen>`; `fleet keys W1 Enter` (or another answer) lets it continue |
| 4 Three workers | `fleet on` without `--accounts`, spawn three workers | Panes split in one workspace; accounts spread by headroom (two or three accounts) |
| 5 Subagents read as working | Send a task that makes a worker start its own subagents | Observe whether Herdr keeps the worker in state `working` while its subagents run, so `wait` does not report early. If it reads `idle` or `done` early, note it as a finding; this is not guaranteed |
| 6 8 workers | `fleet on`, spawn eight workers | Two tabs of 4, all ready |
| 7 Final reviewer worker | `fleet spawn --role final-reviewer`, `fleet send Wn --brief .superlite/review-packet.md --label FR1`, `fleet wait` | `Wn FR1 APPROVED findings=0 <json>` or `CHANGES_REQUESTED findings=n`; the worker is stopped |
| 8 Fix round | `findings route --plan PLAN <json>`, then per line `fleet spawn --role fixer --tier T` and `fleet send Wn --brief P` | `fixer tier=... brief=... files=... task=Tn` lines; fixer workers end `DONE` |
| 9 Layer run | `fleet run --layer headless --plan PLAN`, then `fleet wait` | `Wn layer-headless GREEN\|RED exit=n <log>` plus the last log line |
| 10 Guard | With fleet on, make an in-process `Agent` call for a superlite role | The call is blocked |
| 11 Off from inside | Run `fleet off` from a pane of the fleet's own workspace | `fleet: off` is printed and `fleet.json` says off before the pane closes |

## Batch leads (backlog mode)

`/superlite:backlog` works a whole issue backlog from the main session. Main loop: `sl backlog plan` (a read-only triage worker proposes file-disjoint batches), `decide` (Max's answers and one ship approval), `start` (per batch a worktree and a lead worker, at most `--cap` at once), `wait` (one line per lead that ends), `answer` (resumes a lead that escalated). State lives in `<main root>/.superlite/backlog.json`; each shipped batch leaves a short summary in `.superlite/backlog/<B>.md`.

A lead is a fleet worker of main's run with role `lead`, started in its batch worktree with its own `.superlite` and its own fleet. Env: `SUPERLITE_FLEET_ROLE=lead`, `SUPERLITE_FLEET_AGENT=lead`, `SUPERLITE_FLEET_WORKER=Wn`, `SUPERLITE_STATE_DIR=<worktree>/.superlite`, `SUPERLITE_FLEET_PARENT_DIR=<main .superlite>`. It runs with `--permission-mode auto` and may only run `Bash(maxapp ship *)` and `sl backlog ship *`; `AskUserQuestion` is disallowed. Hooks treat it as a coordinator, and fleet panes answer permission dialogs with no.

Ship lock: leads ship one at a time. `sl backlog ship B lock` takes the machine-wide ship lock `~/.superlite/locks/ship-<repo>.lock` (`{batch, lead, agent, repo, time}`); `merge` or `release` frees it. A lock is stale when its lead's agent is no longer live; the next `lock` takes it over. After `merge` the lead's PR is merged and `sl backlog ship` fast-forwards the main checkout, so the next lead builds on it.

Escalation: a lead that needs a major decision lets its workers finish, writes `.superlite/question.json` (`{"questions": [...]}`, the AskUserQuestion shape) and ends with `Status: NEEDS_DECISION`. `backlog wait` prints the batch, main asks Max and runs `backlog answer B --file F`, which writes `answer-<n>.json` and resumes the lead.

| Step | Do | Expect |
|---|---|---|
| Lead ships a batch | `backlog plan`, `decide`, `start B1`, `wait` | a lead builds in its worktree; `wait` prints the batch as shipped after `lock`, `bump`, `merge` |
| Escalation | A lead writes `question.json` and ends `NEEDS_DECISION` | `wait` names the batch as needs_decision; `answer B1 --file F` resumes it |
| Two leads ship in turn | Start two batches; both reach `ship lock` | the second `lock` waits until the first `merge` or `release` |

## Troubleshooting

- Trust dialog (`Yes, I trust this folder`): accepted automatically at spawn.
- `Select login method` or another startup block: the account's login expired. Run `claude` once in that account's config dir. The screen is in `.superlite/fleet/screens/Wn.txt`.
- `BLOCKED: Wn no READY (pane R rows, C cols)`: the prime prompt did not land. Check with `herdr agent read sl-<run folder>-<hash>-wn`.
- `agent_prompt_stalled` (a herdr error code, shown in the `error:` line): spawn resends the prime once; a second stall is BLOCKED. For a `fleet send` to a worker that was mid-turn: run `fleet wait`, then resend.

## Limits

- Workers share the checkout, so tasks must own disjoint files (the plan already guarantees this).
- No account swap mid-run: a worker keeps its account until stopped.
- Implementer tasks need a taskgraph plan; a fixer, reviewer or research worker needs only a brief file.
