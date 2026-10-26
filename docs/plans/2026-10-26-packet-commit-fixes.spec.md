# Packet, commit and apply fixes (1.2.3)

Origin: the superlite 1.2.2 build (docs/plans/2026-10-26-coordinator-cost.report.md). Issues #22, #21, #23, #19.
Decisions by Max on 2026-10-26: §4 is labelled, the final review stays parallel; commit_task auto-accepts shared
test edits with an incident; one AI-orchestrated build, one PR, version 1.2.3.

## 1. Test summary carries per-file results and mode (#22)

- `run_tests` writes `"files": {"<test file>": [passed, failed]}` into every summary (fast and full) and
  `"mode": "fast|full"` into the background pointer `test-summary.latest`.
- A Python full run with no configured `testpaths` (pytest.ini, pyproject `[tool.pytest.ini_options]`, setup.cfg
  `[tool:pytest]`, tox.ini `[pytest]`) runs `tests/` when that folder exists, else the root with
  `--ignore=bench` when `bench/` exists. Configured `testpaths` and `.superlite/test-cmd.json` win.

## 2. Packet: stale incidents and §4 (#22)

- A `test-failure` incident is dropped from the packet when the packet's summary lists its file in `files` and
  does not list it failing: by test name (the first `test_\w+` token of the context) when there is one, else by
  the file's failed count being 0.
- A `fast` summary is shown in §4 under `- full suite not run yet (it runs alongside this review); newest fast
  run:` with its counts and failures; its failures still count as open.
- When the pointer names a `full` run whose summary does not exist yet and that started at least 5 s before the
  packet, the packet waits for it (default 600 s, `--wait-timeout S`), then reads it. A run started later (the
  coordinator's parallel `--full --background`) is not waited on.

## 3. commit_task: shared test edits (#21)

- A tracked, modified (not new, not deleted) file under `tests/` that no task owns commits with the task being
  committed instead of blocking. Each one prints `shared-test <path>` on stderr and logs a `workaround` incident
  `Tn: shared test adjusted` with resolution `accepted`. New files, deletions and source files still block.

## 4. autocommit apply squashes per task (#23)

- `apply` makes one commit per task: the task's files at its newest checkpoint, placed at the task's first
  position, titled as the task's first entry. `apply --no-squash` keeps one commit per checkpoint.
- When squashing would change the final tree (two tasks interleave on one file), `apply` falls back to one commit
  per checkpoint and prints `squash skipped: tasks interleave on <file>`.

## 5. Script tests never read the checkout's .superlite (#19)

- `tests/scripts/conftest.py` copies `tests/scripts/fixtures` once per session to a temp folder outside any git
  repository and exposes it as `conftest.FIXTURES`; every test module reads fixtures from there.

## Validation

`scripts/bump-version.sh 1.2.3`, `--audit` clean; `docs/tools.md` describes the new behaviour; the full script
suite (`tests/scripts`) is green.
