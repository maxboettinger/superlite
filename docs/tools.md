# Tools

Mechanical steps are scripts, not agents. Every tool runs as `bash <skill-dir>/scripts/sl <tool> ...`, where `<skill-dir>` is `skills/subagent-driven-development`. The `sl` launcher runs a `.sh` tool under bash and a `.py` tool under the first working Python, and exits 3 when there is none. It caches that interpreter, so each later call is one Python start (`SUPERLITE_PYTHON` skips the probe entirely). Tools that need each other import them in process instead of spawning `sl` again. The tools are Python, but the project can be any language.

| Tool | What it does |
|---|---|
| `plan_tools` | Plan lint (`--stable` freezes tasks and tiers), task graph, stubs, schedule, prune, and the `adapter`, `packet` and `contract` review subcommands |
| `wave0` | Builds the Wave 0 skeleton brief for `implementer-haiku` from the plan alone |
| `routing` | Maps each task's plan features to a tier (haiku or sonnet) using `routing.json` |
| `shape` | Build shape: contract examples, removable edges, prune, chain ids |
| `predict` | Predicts each task's time, context and cost; `--refit` fits the coefficients |
| `build_prime` | Builds the shared prime that every agent reads first (`--tier haiku` builds the mini prime) |
| `dispatch` | Ready tasks and who runs each, in one call (`next_tasks` + `assign`) |
| `pool` | Keeps `.superlite/pool.json` (never edit it by hand): `add ID --tier T [--current Tn]`, `busy ID Tn`, `free ID`, `list`, `sync` (real `context_k` from the agent transcript, `idle_min`, `busy` cleared by a newer stop record; `dispatch` syncs first) |
| `next_tasks` | Computes which tasks are ready |
| `assign` | Scores idle agents and picks the most relevant one |
| `commit_task` | Checks scope, then checkpoints (default: hidden `refs/superlite/*` commits, branch untouched) or commits (autocommit on) one or more tasks' owned files; `--dispatch` also prints the next dispatch; a modified, tracked test under `tests/` that no task owns joins the task (logged); `Tn --also FILE --ruling "TEXT"` (one task) commits a file another task owns and records the ruling; a `**Ticket:** KEY` plan header prefixes messages `KEY Tn: title`; unowned `docs/**/*.md` never blocks or stages; out-of-scope files print one `hint:` line; the import check uses the `pythonpath` roots |
| `autocommit` | `on`/`off`/`status` opt-in real commits (`.superlite/autocommit.json`, env `SUPERLITE_AUTOCOMMIT=1`); `apply` turns checkpoints into commits on the current branch, one commit per task (`--no-squash`: one per checkpoint); `clean` deletes them |
| `run_tests` | Runs the project's test command (`{junit}`, `{names}` = test file basenames joined by `\|` for `--filter`; every non-empty sidecar `<junit stem>*.xml` is counted), with `--background` (prints `summary: <path>` and a `wait:` line), then `--wait PATH` for that run's summary (bare `--wait`: the shared latest pointer); writes `.superlite/test-summary.json`; `--task Tn [--plan P]` runs compiled stacks in the isolated tree `.superlite/trees/Tn` (the summary stays in the main `.superlite`); works from any subdirectory (runs from the folder holding `.superlite/`, note on stderr) |
| `testcmd` | Resolves the project's test command: `.superlite/test-cmd.json`, else detection (npm, go, cargo, dotnet, Python); a Python full run without testpaths runs `tests/` (else ignores `bench/`); `{only_testing}` for xcodebuild, Swift Testing and XCTest output, `isolate` flag; optional `pythonpath`: repo-relative import roots after the root and `src/` |
| `pyroots` | Import roots for a project: `import_roots(root, plan)` reads `pythonpath` from `.superlite/test-cmd.json`, else derives them from the plan's `Produces` names (hyphenated package directories included) |
| `pt_review` | `adapter`, `packet` (the final review packet) and `contract` (seam checks; a producer without Python sources is checked by declaration: the first name of each Produces must be declared in an owned source file, parameters unchecked). The packet diffs against the newest `checkpoints.json` sha when there is one, else the working tree. The packet drops `test-failure` incidents the newest summary shows green and labels a fast summary `full suite not run yet` |
| `probe_run` | Parallel robustness probes with no agents (Python projects only) |
| `trees` | `trees.py clean` removes the isolated test trees under `.superlite/trees` (`sl trees clean`, at finish); `path Tn` prints one |
| `incident` | Records and queries the shared incident log (file, line, context) |
| `feedback` | Superlite's own friction inbox, `~/.superlite/feedback.jsonl` per machine: `add TEXT [--kind K] [--plan P]` (text scrubbed of home paths, e-mails, tokens), `triage [--host H]... [--all]` (merges the hosts in `feedback-hosts` over ssh, groups duplicates, ranks by count, matches open issues via `gh`), `mark ID...`; `finish` asks for it |
| `budget` | One line of elapsed time and cost against the plan's target and cap |
| `metrics` | Per-task time, tokens and cost from `.superlite/metrics.jsonl` and agent transcripts |
| `history` | Run history: `write` rows to `~/.superlite/history.jsonl`, `read`, `derive` stats, `import` bench scores |
| `graphify_gate` | Gates Graphify for search in non-trivial codebases |
| `finish` | Collects the finish summary (rulings, commits or checkpoints, test counts, open incidents) |
| `orchestrator` | Human or AI gate: `set`, `approve --review`, `status`, `bind` (bind this session to a `.superlite`), `end` (archive the run markers and gate files into `.superlite/runs/<time>/`) |
| `state` | `where`: which `.superlite` this session uses (`SUPERLITE_STATE_DIR`, the session's binding, else `./.superlite`; a plan resolves at its git toplevel) |

`_pyrun.py` is a shared helper, not a tool. Probes live in `probes/` with the probe pack in `probes/pack/`.

The coordinator guard (`hooks/block-coordinator-edits`) judges `cp`, `mv` and `tee` with a directory target (trailing `/`, `.` or an existing directory) by `<dir>/<basename of the first source>`, and resolves `sys.argv[N]` writer targets to the interpreter's N-th positional argument, through one `VAR=literal` assignment in the same command; anything unresolvable still blocks.
