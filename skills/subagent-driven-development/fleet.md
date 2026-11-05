# Fleet mode

When `.superlite/fleet.json` says on (`"$SL" fleet on [--accounts a,b]`), workers are real Claude Code sessions in Herdr panes, one account each, editing the same checkout. Details: `docs/fleet.md`.

- `fresh tier=T agent=TYPE`: `"$SL" fleet spawn --tier T --plan $PLAN` prints `Wn account=A pane=P agent=TYPE`; then `"$SL" fleet send Wn Tn [Tm ...] --plan $PLAN`. Spawn registers the pool entry; `BLOCKED:` output (exit 3) means no worker: treat the task as BLOCKED.
- `agent=Wn`: `"$SL" fleet send Wn Tn --plan $PLAN`. `poll` never appears in fleet mode.
- After a dispatch round, run `"$SL" fleet wait --timeout 540000 --plan $PLAN` in the foreground instead of waiting for SendMessage replies. Act on its lines:
  - `Wn Tn DONE <report path>` (or `DONE_WITH_CONCERNS`, `BLOCKED`): read the report, then `commit_task` as usual.
  - `Wn Tn NEEDS_CONTEXT <report path>`: answer with `"$SL" fleet send Wn --text "..."`, then wait again.
  - `Wn Tn BLOCKED-UI <screen path>`: read the screen file; answer with `"$SL" fleet keys Wn KEY...` or `fleet send Wn --text "..."`, or treat the task as BLOCKED.
  - `TIMEOUT Wn Wm`: run `fleet wait` again.
- `"$SL" fleet status` lists workers; `fleet stop Wn` or `--all` closes them.

At freeze, `"$SL" fleet stop --all` runs before `trees clean` (no-op without fleet mode).
