# Telemetry: the local event log

Superlite appends one JSON line per event to `<superlite home>/events.jsonl` (`$SUPERLITE_HOME`, default `~/.superlite/`). Lines stay on the machine; a separate shipper reads the file. Nothing in superlite sends them anywhere.

## Line shape

One object per line, keys in a fixed order. Common fields, in order: `v`, `t`, `kind`, `session`, `run`, `repo_root`, `harness`, `version`, `worker`, `role`, `config_dir`. Then the fields of the kind. A field with no value is `null`, except the optional `agent_session`, which is left out. A whole line is at most 4096 bytes (the longest strings are cut first); `target` is cut to 200 characters.

## Kinds

| Kind | Fields | Writer |
|---|---|---|
| `invoke` | `name`, `via` | `sl_tel_emit` (skill and command hooks), Python |
| `mode` | `mode` | hooks, Python |
| `orchestrator` | `mode`, `by` | Python (`orchestrator.py`) |
| `fleet` | `on`, `accounts` | Python (`fleet.py`) |
| `session_start` | `source`, `duration_s` | hook `session-start` |
| `session_end` | `reason`, `duration_s` | hook `session-end` |
| `run_start` | `plan`, `tasks`, `detail`, `branch`, `mode`, `orchestrator`, `fleet` | Python (`plan_tools.py`) |
| `dispatch` | `task`, `role`, `agent_type`, `model`, `effort`, `tier`, `account`, `machine`, `label`, `writer_role` | hook `capture-agent-launch` |
| `agent_stop` | `task`, `role`, `model`, `effort`, `account`, `machine`, `duration_s`, `tokens`, `cost_usd`, `tool_calls`, `status`, `writer_role` | hook `capture-agent-stop` (one Python call); `fleet_io.py` at a fleet worker's report; `fleet.py` when a fleet worker is marked dead; `fleet.py` and `fleet_remote_worker.py` when superlite stops a fleet worker |
| `tests` | `mode`, `passed`, `failed`, `skipped`, `seconds`, `task` | Python (`run_tests.py`) |
| `gate` | `hook`, `decision`, `rule`, `tool`, `target` | the gate hooks (bash) |
| `review` | `review_kind`, `verdict`, `findings`, `round` | Python |
| `batch` | `batch`, `state`, `lead_model`, `pr`, `reason` | Python (`backlog_state.py`) |
| `feedback` | `fkind`, `reason` | Python (`feedback.py`) |
| `run_end` | `outcome`, `wall_s`, `cost_usd`, `tasks`, `first_time_pass`, `fix_rounds`, `final_verdict`, `agents`, `tests_passed`, `tests_failed`, `ci_red`, `questions`, `projected_min`, `critical_path_min`, `reason`, `mode`, `orchestrator`, `fleet` | Python (`orchestrator.py`), deferred while a batch is unshipped |

`agent_stop` `status` is the status word of the agent's report (`DONE`, `DONE_WITH_CONCERNS`, `NEEDS_CONTEXT`, `BLOCKED`, `UNKNOWN`, a reviewer's verdict), `DEAD` when superlite marks a fleet worker dead (its agent is gone: `fleet wait`, a refused send or keys, `fleet status`), or `STOPPED` when superlite stops a fleet worker on purpose (it closes its pane: `fleet stop`, `fleet off`, a one-turn worker after its report, backlog cleanup and reset); a `DEAD` or `STOPPED` line has `effort`, `tokens`, `cost_usd` and `tool_calls` null and `duration_s` only for a worker that was busy.

Example:

```json
{"v":1,"t":"2026-11-16T12:34:56.789Z","kind":"tests","session":null,"run":null,"repo_root":"/tmp/p","harness":null,"version":"1.5.252","worker":null,"role":null,"config_dir":null,"mode":"fast","passed":3,"failed":0,"skipped":1,"seconds":2.5,"task":"T2"}
```

Added fields beyond the base contract: `review_kind` (kind `review`), `writer_role` (kinds `dispatch` and `agent_stop`: the role of the fleet worker that wrote the line), `agent_session` (kind `agent_stop`, fleet workers only: the worker's own Claude Code session id, as herdr reported it after the worker started; left out when unknown; the common `session` stays the writer's), `backfill` (`true` on a line rebuilt by the export), and `mode`, `orchestrator` and `fleet` (kind `run_end`) (as of the run's end, from the source `run_start` uses).

## Writers

Python code calls `telemetry.emit(kind, ...)`; hooks source `hooks/telemetry.sh` and call `sl_tel_emit`. Both catch every error and return without output: a telemetry write never changes a hook's or tool's exit code, stdout or stderr. An unknown kind writes nothing.

## Run end

`run_end` is written when the run ends. While a backlog batch is not yet shipped the line is deferred: the fields are kept and the line is written when the batch ships or is abandoned. A run whose folder holds a lead brief has mode `backlog`.

## Rotation

At 20 MB the file is renamed to `events.jsonl.1`, older files shift up to `events.jsonl.5`, the oldest is dropped. Writers take a lock for the rename.

## Off switches

- `SUPERLITE_TELEMETRY=0` in the environment.
- The file `<superlite home>/telemetry-off`.

Either one turns every writer off.

## Privacy

No line holds a prompt, a response, a last message, an agent description, feedback text or file content. Fields are ids, names, counts, durations and short fixed words.

## Export

`sl telemetry export --since YYYY-MM-DD` rebuilds the same lines from the existing ledgers (run folders, backlog, feedback) for a backfill; each rebuilt line carries `backfill: true`. Exported `run_start` and `run_end` lines take `mode`, `orchestrator` and `fleet` from the archive's `run.json`; an older archive gives `backlog` when it names a batch, else null.
