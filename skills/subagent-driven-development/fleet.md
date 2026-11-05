# Fleet mode

The user asks for fleet ("use fleet", workers in Herdr): run `"$SL" fleet on [--accounts a,b] --plan $PLAN` before the first dispatch. While `.superlite/fleet.json` says on, the implementer tasks of the taskgraph run in real Claude Code sessions in Herdr panes (worker `Wn` shows in Herdr as `sl-<run folder>-wn`), one account each, editing the same checkout. Reviewers, fixers and the final reviewer stay in-process Agent calls; an inline build without a taskgraph starts no worker: tell the user. Details: `docs/fleet.md`.

- `fresh tier=T agent=TYPE`: `"$SL" fleet spawn --tier T --plan $PLAN` prints `Wn account=A pane=P agent=TYPE`; then `"$SL" fleet send Wn Tn [Tm ...] --plan $PLAN`. Spawn registers the pool entry; `BLOCKED:` output (exit 3) means no worker: treat the task as BLOCKED.
- `agent=Wn`: `"$SL" fleet send Wn Tn --plan $PLAN`. `poll` never appears in fleet mode.
- After a dispatch round, run `"$SL" fleet wait --timeout 540000 --plan $PLAN` in the foreground instead of waiting for SendMessage replies. Act on its lines:
  - `Wn Tn DONE <report path>` (or `DONE_WITH_CONCERNS`, `BLOCKED`): read the report, then `commit_task` as usual.
  - `Wn Tn NEEDS_CONTEXT <report path>`: answer with `"$SL" fleet send Wn --text "..."`, then wait again.
  - `Wn Tn BLOCKED-UI <screen path>`: read the screen file; answer with `"$SL" fleet keys Wn KEY...` or `fleet send Wn --text "..."`, or treat the task as BLOCKED.
  - `TIMEOUT Wn Wm`: run `fleet wait` again.
- `"$SL" fleet status` lists workers; `fleet stop Wn` or `--all` closes them.

At freeze, `"$SL" fleet stop --all` runs before `trees clean` (no-op without fleet mode).
