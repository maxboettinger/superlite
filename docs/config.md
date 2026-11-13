# Config

In `skills/subagent-driven-development/config/`:

- `models.json`: prices (USD per million tokens) and output speed per model. Edit it when they change.
- `predictor.json`: the time and context coefficients and the size band `predict` uses. Refit with `sl predict --refit`.
- `routing.json`: task features to tier (`haiku` or `sonnet`), tier agents and limits, and the stats gate. With `baseline: default_tier` the gate holds a cheap tier's band when its first-time pass rate is below the default tier's rate on the same band (that band needs `min_n` samples), else below the fixed `min_first_time_pass`. A critical-path task never gets haiku.
- `run-configs.json`: named run configs for the lead and the workers (see Run config below).

## Permissions (Claude Code)

- `Bash(*/skills/subagent-driven-development/scripts/sl commit_task *)` in `permissions.allow` of the user settings (`~/.claude/settings.json`): lets fixer agents run `sl commit_task` in auto mode, whose classifier otherwise denies the call from a subagent. Allow rules are checked before the classifier and apply to subagents; a plugin cannot ship permission rules, so `/superlite:setup` offers it. Without it a fixer reports `commit: denied` and the coordinator commits.

## Run config

A run config is a named set of launch choices for a backlog lead and its fleet workers. `config/run-configs.json` is the built-in file; `$SUPERLITE_HOME/run-configs.json` is the machine layer; `.superlite/run-configs.json` in the project is the project layer. A file is `{"default": NAME or null, "configs": {NAME: partial config}}`; keys starting `_` are ignored. NAME resolves as the built-in `default` config, then each layer's `configs[NAME]` section by section (built-in, machine, project), then `--model`. The default NAME is the project file's `default`, else the machine's, else `default`.

Fields and built-in defaults:

- `lead.model`: `opus`. `lead.effort`: `xhigh` (`low|medium|high|xhigh|max`). `lead.autocompact`: `null`, which uses main's window. `lead.build_model`: `null` (one lead plans and builds); set, the planning lead stops after the plan and a build lead on that model runs it. `lead.build_effort`: `null` (the lead's effort), or an effort for the build lead.
- `lead.deny`: tools the lead does not get: `AskUserQuestion Artifact ArtifactComments ArtifactData ListAgents ReadNotifications ReportFindings ScheduleWakeup Workflow`. `lead.mcp`: `project`, the MCP servers kept. `lead.text`: `default`, the lead brief text variant id.
- `cache_ttl.lead` and `cache_ttl.workers`: `1h` (or `5m`).
- `workers`: a model per role; `null` keeps the agent file's model.

The config id is `NAME-` plus 8 hex of the sha256 over the canonical JSON of lead, cache_ttl and workers. A run's active config is the snapshot `<state dir>/run-config.json`. `sl run_config show|list` prints a resolved config or the known names.

`sl backlog start --config NAME` resolves once and starts the lead with `--model`, `--effort`, `--autocompact`, `--strict-mcp-config` (with `--mcp-config` for the kept servers), `--no-chrome` and the deny list; the lead keeps the Skill tool. `CLAUDE_CODE_PROMPT_CACHE_TTL` is set from `cache_ttl.lead`. `sl fleet on --config NAME` writes the snapshot for a run outside the backlog; `fleet spawn` then sets `CLAUDE_CODE_PROMPT_CACHE_TTL` from `cache_ttl.workers` and pins `--model` for a role the config names.

## Lead cap

`sl backlog start` and `sl backlog run` without `--cap` take the number of leads from the machine instead of a fixed 2, and print one line first: `cap: N (<deciding limit>; <other parts>)`. `--cap N` overrides it and prints no line. Only main computes it (a fleet worker neither prints nor runs the room command); `run` computes it once at its start. While a batch is planned, `sl backlog status` ends with the same line.

The room command is an argv list in `~/.superlite/machine.json` under `room`, run with a 20 s timeout. It prints one JSON object: `room` (integer >= 0, the free capacity), `unit` (text, for example `cores`) and optionally `reason` (text, why the room is small). Keys of `machine.json` and their defaults:

- `room`: no default; the argv list of the room command.
- `lead_units`: 2; units of room one lead takes. Measured on a machine with 18 cores and 64 GB: 9 live leads with 24 to 26 agents used about 0.6 cores and 1.8 GB each with their workers, so 2 per lead leaves room for a lead's fast test runs (full suites queue on the full-suite lock).
- `leads_per_repo`: 6; leads for this repository.
- `leads_per_machine`: 12; live leads on the machine (herdr agents named `sl-*-lead`); herdr unreachable drops this limit.
- `lead_weekly_max`: none; percent (0 to 100); an account at or above it in the weekly usage counts as not usable.

The cap is the smallest of these limits, each a total lead count: running leads plus `room // lead_units`; `leads_per_repo`; running leads plus what `leads_per_machine` leaves; and, when no account is usable, the running leads. The line names the limit that decided first, then the room and the accounts. A key that is not valid falls back to its default and the line says `machine.json <key> invalid, default <v>`. Examples:

- `cap: 6 (6 per repository; room 30 cores, 2 per lead; accounts ok)`
- `cap: 2 (room 0 cores: two full suites run; accounts ok)`
- `cap: 1 (no account usable: a1: weekly_all 95% >= lead_weekly_max 90%; room 12 cores, 2 per lead)`

Without a usable room command the cap falls back to `fixed cap 2: <why>` (for example `machine.json names no room command`, `room command exited 3`). Usage data missing reads `accounts unknown (no usage data)` and sets no limit. Planned batches that another planned batch holds by a shared file count in `<n> held by overlap`.

## Environment

- `CLAUDE_CODE_FORK_SUBAGENT=0` (settings `env`): turns off Claude Code's per-agent status summaries, which ask each background agent's model every 30 s for a status line, sending the agent's transcript, or a few hundred characters of notes when the server serves the short mode, and are invisible to `metrics.jsonl`. `/superlite:setup` offers it; `budget:` prints `SUMMARIES ON` without it. See the README's Configuration section.
- `autoCompactWindow` (user settings, e.g. `400000`; `sl setup` offers it): the context size at which Claude Code compacts by itself. Models with a 1M window otherwise compact only near their limit (about 967k tokens). `/autocompact 400k` saves the same for the current model, `claude --autocompact 400k` sets it for one launch. Around each compaction superlite's hooks supply the summary instructions and the continuation text ([hooks](hooks.md)).
- `SUPERLITE_NO_AUTOCOMPACT=1`: turns off superlite's part in compaction: the summary instructions (`pre-compact`), the continuation text after a compaction (`session-start`) and the hint to set a window (`compact-nudge`). Claude Code's own compaction is not affected.
- `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL=1h`: the implementer's cache TTL, also set by its frontmatter.
- `SUPERLITE_HERDR_BIN`: the `herdr` binary for fleet mode; default `herdr` on PATH.
- `SUPERLITE_CLAUDE_PROFILE_BIN`: the `claude-profile` binary used to read account usage; default `claude-profile` on PATH. Missing means the first allowed account is used; account names then cannot be resolved to a config dir, so pass config dir paths instead.
- `SUPERLITE_LEAD_CAP_LIVE=0`: the lead cap reads no accounts and no herdr agents (the script tests set it).
- `SUPERLITE_FLEET_ACCOUNTS`: comma list of accounts `fleet on` allows when `--accounts` is absent (e.g. `claude1,claude3`; an entry may also be a config dir path such as `~/.claude-account1`, which works without `claude-profile`); else every account `claude-profile list --json` returns, else `current`.
- `SUPERLITE_FLEET_WORKER`: set by `fleet spawn` on a worker pane to its id (`W1`); the hooks treat the session as a fleet worker. Do not set it by hand.
- `SUPERLITE_FLEET_AGENT`: set by `fleet spawn` on a worker pane to its agent type (e.g. `superlite:implementer`); recorded in the worker's stop record.
