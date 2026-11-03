# Config

In `skills/subagent-driven-development/config/`:

- `models.json`: prices (USD per million tokens) and output speed per model. Edit it when they change.
- `predictor.json`: the time and context coefficients and the size band `predict` uses. Refit with `sl predict --refit`.
- `routing.json`: task features to tier (`haiku` or `sonnet`), tier agents and limits, and the stats gate. A critical-path task never gets haiku.

## Environment

- `CLAUDE_CODE_FORK_SUBAGENT=0` (settings `env`): turns off Claude Code's per-agent status summaries, which re-send each background agent's transcript every 30 s and are invisible to `metrics.jsonl`. `/superlite:setup` offers it; `budget:` prints `SUMMARIES ON` without it. See the README's Configuration section.
- `CLAUDE_CODE_SUBAGENT_PROMPT_CACHE_TTL=1h`: the implementer's cache TTL, also set by its frontmatter.
