# Fleet mode

The user asks for fleet ("use fleet", workers in Herdr): run `"$SL" fleet on [--accounts a,b] --plan $PLAN` before the first dispatch. While `.superlite/fleet.json` says on, every superlite role runs as a worker: a real Claude Code session in a Herdr pane (worker `Wn` shows in Herdr as `sl-<run folder>-<hash>-wn`), one account each, editing the same checkout. While fleet is on, never call `Agent` for a superlite role (implementer, fixer, package reviewer, final reviewer, researcher); a hook blocks it. With fleet off every role stays an in-process Agent call. An inline build without a taskgraph starts no worker: tell the user. Details: `docs/fleet.md`.

Fleet covers one taskgraph plan in one checkout: several tickets go into one plan and one run, not one worktree each. Fleet asked for but `sl fleet` unknown (compare `sl version` with the session-start line) or `fleet spawn` exits 3: report BLOCKED with the exact error before any dispatch; never fall back to in-process agents. `sl feedback add` comes in addition, never instead.

## Implementers

`"$SL" fleet spawn --for-dispatch --plan $PLAN` is the one call per dispatch round, Wave 0 included (it sends `.superlite/briefs/wave0.md` as T0), instead of `dispatch` plus a spawn and a send per line. It runs `dispatch`, starts a worker for each `fresh tier=T agent=TYPE` line, sends each line's tasks (an `agent=Wn` line goes to that idle worker) and prints one `Wn Tn[,Tm] sent` line per worker; `evict=` lines go to stderr. `BLOCKED: Tn[,Tm] not sent (<reason>)` (the call then exits 3) means no worker got those tasks: treat them as BLOCKED; the other lines still went out. `poll` never appears in fleet mode.

By hand, one line: `fresh tier=T agent=TYPE`: `"$SL" fleet spawn --tier T --plan $PLAN` prints `Wn account=A pane=P agent=TYPE`; then `"$SL" fleet send Wn Tn [Tm ...] --plan $PLAN`. `agent=Wn`: `"$SL" fleet send Wn Tn --plan $PLAN`.

## Other roles

Every other role takes a brief file under `.superlite/briefs/` (never pasted into the send): `"$SL" fleet spawn --role R [--tier T] --plan $PLAN` prints `Wn account=A pane=P agent=TYPE`, then `"$SL" fleet send Wn --brief <abs file> [--label L] --plan $PLAN`. A one-turn worker answers once and `fleet wait` stops it.

- Package reviewer: `--role package-reviewer`; the brief holds what the review brief in `SKILL.md` holds.
- Final reviewer: `--role final-reviewer`, a fresh worker per round: `fleet send Wn --brief <abs>/.superlite/review-packet.md --label FR<round>`.
- Fixers: `"$SL" findings route --plan $PLAN <json paths>` prints `fixer tier=T brief=P files=F task=Tn` per finding group. Per line: `fleet spawn --role fixer --tier T`, then `fleet send Wn --brief P`. Escalation: the same brief to a worker one `--tier` up.
- Research: `--role research` (read-only `superlite:researcher`).
- Test layers, in a repo with `scripts/test_layers.py`: `"$SL" fleet run --layer headless|tui|evals --plan $PLAN` runs the layer in a shell pane; no brief.

## Waiting and acting

Run `"$SL" fleet wait --timeout 540000 --plan $PLAN` in the foreground instead of waiting for SendMessage replies. Act on its lines, not on report text. One-turn workers are stopped by `fleet wait`.

- `Wn <label> <STATUS> findings=<n> <sd>/fleet/reports/<id>.json`: `<id>` is the label's first comma part; ` (screen)` marks the screen fallback.
  - Task labels (`DONE`, `DONE_WITH_CONCERNS`): `commit_task` as usual.
  - `findings=` above 0 or `CHANGES_REQUESTED`: `findings route` with the JSON paths, then the fixer lines above.
  - `BLOCKED`: treat the task as BLOCKED.
  - `UNKNOWN` (no parsable report): read `.superlite/fleet/reports/<id>.md` once, then decide.
  - `NEEDS_CONTEXT`: answer with `"$SL" fleet send Wn --text "..."`, then wait again.
- `Wn layer-L GREEN|RED exit=<n> <log path>` plus `  <last line>`: a layer result; read the log on RED.
- `Wn Tn BLOCKED-UI <screen path>`: read the screen file; answer with `"$SL" fleet keys Wn KEY...` or `fleet send Wn --text "..."`, or treat the task as BLOCKED.
- `TIMEOUT Wn Wm`: run `fleet wait` again.

`"$SL" fleet status` lists workers; `fleet stop Wn` or `--all` closes them. At freeze, `"$SL" fleet stop --all` runs before `trees clean` (no-op without fleet mode).

Batch leads and backlog mode (`/superlite:backlog`): `backlog.md`.
