---
description: First-run check: toolchain, test command, model tiers, and conflicts with other plugins.
argument-hint: ""
---

Check and report, changing nothing without a yes:
- the project language and test command (`sl testcmd`, `test-cmd.json` or detection) and that it runs;
- Python 3.10+ for the `sl` tools;
- the model tiers in `config/models.json` and `config/routing.json`;
- whether superpowers is also enabled (two process skills compete: suggest disabling one for this project);
- whether `.superlite/` is gitignored;
- in Claude Code's interactive CLI only (`CLAUDE_CODE_ENTRYPOINT=cli`): whether `CLAUDE_CODE_FORK_SUBAGENT` is `0`. Otherwise Claude Code asks every background agent's model for a 3-5 word status line every 30 s, sending the agent's transcript, or a few hundred characters of notes when the server serves the short mode; superlite never reads it and the requests appear in no transcript, so the budget cannot count them (`agent_summary`; anthropics/claude-code#86879). The fix line offers to add `"CLAUDE_CODE_FORK_SUBAGENT": "0"` to the `env` map of the user settings (`$CLAUDE_CONFIG_DIR/settings.json`, default `~/.claude/settings.json`; keep the other keys). It takes effect in the next session and removes only the `fork` subagent type, which superlite never uses.
- in Claude Code only: whether the user settings (`$CLAUDE_CONFIG_DIR/settings.json`, default `~/.claude/settings.json`) let fixer agents commit: `permissions.allow` holds `Bash(*/skills/subagent-driven-development/scripts/sl commit_task *)`. Without it, auto mode's classifier denies the fixers' `sl commit_task` calls and the coordinator commits for them. Allow rules are checked before the classifier, for subagents too, and a plugin cannot ship one. The fix line offers to add that rule to `permissions.allow` (keep the other entries and keys).
- in Claude Code only: whether an auto-compact window is set, so a long orchestrator session compacts and continues by itself: `autoCompactWindow`, or a `modelSettings.<model>.autoCompactWindow` that `/autocompact` saved, of 500000 or less in the user settings (`$CLAUDE_CONFIG_DIR/settings.json`, default `~/.claude/settings.json`), or `CLAUDE_CODE_AUTO_COMPACT_WINDOW` in the environment. Without one, a model with a 1M window compacts only near its limit (about 967k tokens): every turn pays for the whole context and the user has to run `/compact` by hand. With one, Claude Code compacts at the window, `hooks/pre-compact` tells the summary what to keep, and `hooks/session-start` tells the session to go on and shows it the run state. A plugin cannot ship the setting. The fix line offers to add `"autoCompactWindow": 400000` to the user settings (keep the other keys); it applies to every Claude Code session of that account, at the latest from the next session. `/autocompact 400k` sets the same for the current model only.
Give a pass or fix line for each.
