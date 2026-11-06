# Testing layers

superlite has four test layers. Each one covers a different kind of change, and each one costs a different amount to run. A layer is required when a change touches the paths it maps to (the matrix is in [AGENTS.md](../AGENTS.md#testing-layers)).

| Layer | Runs | Cost per run | What it proves |
|---|---|---|---|
| unit | `sl run_tests --full` (or `skills/subagent-driven-development/scripts/sl run_tests --full`) | free | the scripts, hooks and tools, with no model call |
| headless | `SUPERLITE_E2E=1 sl run_tests --fast tests/e2e/test_headless.py` | about $0.10 | the plugin loads in `claude -p`, the SessionStart injection arrives and two run hooks fire |
| tui | `SUPERLITE_E2E=1 sl run_tests --fast tests/e2e/test_tui.py` | about $0.05 | the interactive-only facts, the agent-summary timer among them (needs `tmux` on PATH) |
| evals | `scripts/evals.sh` | about $2-4 | six cases of real agent work, measured against the baseline |

Every e2e test runs the agent on `--model haiku`, caps turns at 8 or fewer, and runs in an isolated session: no inherited `CLAUDE_CODE_*` or `SUPERLITE_*` session variables, `--setting-sources ""`, `--plugin-dir` set to this repo, stdin from `/dev/null`, and a fresh temporary working directory. One run of the whole e2e layer stays under about $0.30 and 6 minutes. The plain unit suite stays quota-free.

## Stamps

A layer is stale when its hash is not among the green hashes stored for it. The hash is a SHA-256 over the sorted `path` and per-file digest pairs of all files the layer maps to. Two rules keep it stable:

- A manifest (`.claude-plugin/*.json`, any `.<name>-plugin/*.json`, and `package.json` and `gemini-extension.json` at the root) is digested with every `"version": "<value>"` replaced by `"version": ""`, so a version bump alone moves no layer. Any other manifest change does.
- A file that enters the tui layer only through the keyword scan (`CLAUDE_CODE_FORK_SUBAGENT`, `agent_summary`) contributes its path and the lines that contain a keyword, not its whole content. `docs/plans/` and `tests/scripts/` are never scanned.

The green hashes (the newest 200 per layer) and the file list of the last green run live in one store per repository: `<git common dir>/superlite/test-layers.json`. Every checkout and linked worktree of the repository reads and writes the same file, so a layer stamped green in any of them counts in all of them that hold the same layer content. Outside a git repository the store is `.superlite/test-layers.json`. `--state PATH` overrides the store path on every command.

`run` writes a lock (`running.json`, beside the store) with its pid and the layer hash before it starts the command and removes it after. `check` and the Stop hook skip a layer whose lock pid is alive and whose lock hash equals the current hash, so a layer is not demanded again while its run is in progress.

    python3 scripts/test_layers.py check                  # one line per stale layer, naming up to 5 changed files; exit 2 when any
    python3 scripts/test_layers.py status                 # one line per layer: green, stale (with the changed files), running or none
    python3 scripts/test_layers.py run <layer>...         # run them in order; stamp each green one
    python3 scripts/test_layers.py stamp <layer> --ruling "<why>"   # record a deliberate skip

`stamp --ruling` appends `Ruling: skip <layer> - <why>` to `.superlite/progress.md`, so the skip is visible in the run's log.

## Stop hook

The repo's `.claude/settings.json` registers a Stop hook that runs `python3 "$CLAUDE_PROJECT_DIR/scripts/test_layers.py" check --hook`. When a layer the turn's changes require is stale, the hook blocks the turn once and names the layer. It stays silent when the Stop input carries `stop_hook_active: true` (so it blocks once per turn only) and during an active superlite run.

To turn the hook off for one session, set `SUPERLITE_TEST_LAYERS=off`.

## Rules of thumb

- Run e2e and evals once per change, not once per edit. They spend quota.
- A change is done only when every layer its paths require ran green since the change, or a ruling records why one was skipped.
- The e2e tests need `SUPERLITE_E2E=1`. Without it they skip, and the skip is not a pass.
