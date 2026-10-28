# Superlite - Contributor Guidelines

Instructions for any agent (or human) changing this repository.

## What this repo is

A lean build-lifecycle plugin: 8 skills in `skills/`, 3 agents in `agents/`, and one manifest or extension per supported harness. Keep it lean; process is the cost superlite exists to remove.

## Rules

- Do not enable superlite alongside the plugin it was derived from (see the README note); they share skill names.
- `skills/using-superlite/SKILL.md` is injected into every session. Keep it under 1,500 characters.
- Every harness integration must load `using-superlite` at session start. Acceptance test: open a clean session and send `Let's make a react todo list`; `brainstorming` must trigger before any code is written. Manually copied skills or per-session opt-in do not count.
- Per-harness tool mappings live in `skills/using-superlite/references/<harness>-tools.md`. Each says how to run `agents/*.md` where plugin agents do not exist.
- Versions are declared in `.version-bump.json`. Change them only with `scripts/bump-version.sh <version>`; run `scripts/bump-version.sh --audit` to catch missed files.
- Keep LF line endings. `hooks/session-start` uses `printf`, never a heredoc.
- Do not touch `bench/` results or `docs/plans/` when working on a harness integration.

## Feedback loop

Agents using superlite log its own friction with `sl feedback add` into `~/.superlite/feedback.jsonl`, one inbox per machine (`skills/subagent-driven-development/scripts/feedback.py`).

- Session start here: run `bash skills/subagent-driven-development/scripts/sl feedback triage`. Untriaged entries: offer a triage before other work.
- Triage: draft one issue per new group (or a comment on the matched issue), sorted by count. The repo is public: drop hostnames and the project names and paths that are not superlite's own. Get one approval for the batch, file it with `gh`, then `sl feedback mark <ids>`.
- "Improve the plugin" with nothing more specific: the inbox (triage) first, then open issues, then `docs/feedback/`.
- Other machines: one ssh host per line in `~/.superlite/feedback-hosts`; triage reads them, skipping hosts it cannot reach.

## Harness files

| Harness | Files |
|---|---|
| Claude Code, Factory Droid, Copilot CLI, Qwen Code | `.claude-plugin/`, `hooks/hooks.json` |
| Codex | `.codex-plugin/plugin.json`, `.agents/plugins/marketplace.json` |
| Cursor | `.cursor-plugin/plugin.json`, `hooks/hooks-cursor.json` |
| Devin | `.devin-plugin/plugin.json` |
| Gemini CLI | `gemini-extension.json`, `GEMINI.md` |
| Kimi Code | `.kimi-plugin/plugin.json`, `docs/README.kimi.md` |
| Muse | `.muse-plugin/` |
| Hermes Agent | `.hermes-plugin/` |
| OpenCode | `.opencode/`, `index.js`, `package.json` |
| Pi | `.pi/extensions/superlite.ts`, `package.json` |
