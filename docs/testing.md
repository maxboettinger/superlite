# Testing layers

superlite has four test layers. Each one covers a different kind of change, and each one costs a different amount to run. A layer is required when a change touches the paths it maps to (the matrix is in [AGENTS.md](../AGENTS.md#testing-layers)).

| Layer | Runs | Cost per run | What it proves |
|---|---|---|---|
| unit | `sl run_tests --full` (or `skills/subagent-driven-development/scripts/sl run_tests --full`) | free | the scripts, hooks and tools, with no model call |
| headless | `SUPERLITE_E2E=1 sl run_tests --fast tests/e2e/test_headless.py` | about $0.10 | the plugin loads in `claude -p`, the SessionStart injection arrives and two run hooks fire |
| tui | `SUPERLITE_E2E=1 sl run_tests --fast tests/e2e/test_tui.py` | about $0.05 | the interactive-only facts, the agent-summary timer among them (needs `tmux` on PATH) |
| evals | `scripts/evals.sh` | about $1-3 | three cases of real agent work, measured against the baseline |

Every e2e test runs the agent on `--model haiku`, caps turns at 8 or fewer, and runs in an isolated session: no inherited `CLAUDE_CODE_*` or `SUPERLITE_*` session variables, `--setting-sources ""`, `--plugin-dir` set to this repo, stdin from `/dev/null`, and a fresh temporary working directory. One run of the whole e2e layer stays under about $0.30 and 6 minutes. The plain unit suite stays quota-free.

## Stamps

A layer is stale when the SHA-256 over the current contents of all files it maps to differs from the hash stamped at its last green run. The stamps live in `.superlite/test-layers.json`, which is git-ignored through `.superlite/`.

    python3 scripts/test_layers.py check                  # print the stale layers; exit 2 when any
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
