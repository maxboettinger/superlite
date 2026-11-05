# Config

In `skills/subagent-driven-development/config/`:

- `models.json`: prices (USD per million tokens) and output speed per model. Edit it when they change.
- `predictor.json`: the time and context coefficients and the size band `predict` uses. Refit with `sl predict --refit`.
- `routing.json`: task features to tier (`haiku` or `sonnet`), tier agents and limits, and the stats gate. A critical-path task never gets haiku.

## Environment

- `CLAUDE_CODE_FORK_SUBAGENT=0` (settings `env`): turns off Claude Code's per-agent status summaries, which ask each background agent's model every 30 s for a status line, sending the agent's transcript, or a few hundred characters of notes when the server serves the short mode, and are invisible to `metrics.jsonl`. `/superlite:setup` offers it; `budget:` prints `SUMMARIES ON` without it. See the README's Configuration section.
- `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL=1h`: the implementer's cache TTL, also set by its frontmatter.
- `SUPERLITE_HERDR_BIN`: the `herdr` binary for fleet mode; default `herdr` on PATH.
- `SUPERLITE_CLAUDE_PROFILE_BIN`: the `claude-profile` binary used to read account usage; default `claude-profile` on PATH. Missing means the first allowed account is used; account names then cannot be resolved to a config dir, so pass config dir paths instead.
- `SUPERLITE_FLEET_ACCOUNTS`: comma list of accounts `fleet on` allows when `--accounts` is absent (e.g. `claude1,claude3`; an entry may also be a config dir path such as `~/.claude-account1`, which works without `claude-profile`); else every account `claude-profile list --json` returns, else `current`.
- `SUPERLITE_FLEET_WORKER`: set by `fleet spawn` on a worker pane to its id (`W1`); the hooks treat the session as a fleet worker. Do not set it by hand.
- `SUPERLITE_FLEET_AGENT`: set by `fleet spawn` on a worker pane to its agent type (e.g. `superlite:implementer`); recorded in the worker's stop record.
