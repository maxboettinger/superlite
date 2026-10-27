# Field report: piX `reviewing-periods v2` build (2026-10-27)

Run: piX repository, plan `docs/superpowers/plans/2026-10-27-reviewing-periods-v2.md`, human orchestrator, superlite 1.2.4 on Claude Code. 13 tasks (T0 to T11 with T10 split), a Python 3 standard-library script plus tests under a skill directory `config/skills/reviewing-periods/` (note the hyphen), markdown skill text, config docs. Outcome: shipped, 90 tests green, one real final-review finding. Build report: `docs/superpowers/plans/2026-10-27-reviewing-periods-v2.report.md` in piX.

| Measure | Predicted | Actual |
| --- | --- | --- |
| Wall clock | 21.3 min | 76.3 min |
| Agent cost | $1.31 | $3.17 |
| Coordinator cost | | about $8 (80 % of the run) |
| Agents | 12 | 18 |

Each finding below names the mechanism, how it showed, and a fix an agent can implement. Numbers and paths are from this run; no personal content.

## 1. Import checks cannot resolve a package under a hyphenated directory

Where: `commit_task.py` `IMPORT_DRIVER`, `pt_review.py contract`, the review packet's contract section.

What happened: the package lived at `config/skills/reviewing-periods/scripts/review/`. The driver turns the file path into dotted parts; `reviewing-periods` is not an identifier, so it falls back to `spec_from_file_location` and appends the file's own directory (`…/review`) to `sys.path`. The module's `from review.model import …` then fails with `ModuleNotFoundError: No module named 'review'`, every task's commit was `FAILED`, and the seam check printed 39 mismatches of the form `AttributeError: review not found in config.skills.reviewing-periods.scripts.review.shell`. The driver runs Python with `-I`, so `PYTHONPATH` is ignored.

Workaround used: a `.pth` file in `.superlite/venv/lib/python3.x/site-packages` pointing at the `scripts/` directory, plus `SUPERLITE_PYTHON=.superlite/venv/bin/python` on every `commit_task` call. The seam checks stayed red (ruling: covered by the integration tests).

Fix: derive the import root from the plan's `Produces` names (`review.shell.run_json` means: find the ancestor directory that holds `review/__init__.py` or `review/`), or read a `pythonpath`/`rootdir` from `.superlite/test-cmd.json` or the plan header (`**Source root:** config/skills/reviewing-periods/scripts`), and put that root first on `sys.path` in the driver and in the contract check. Fall back to the current behaviour only when no `Produces` name resolves.

## 2. Contract and seam checks treat prose `Produces` of documentation tasks as symbols

Where: `pt_review.py contract`, `finish.py` open incidents.

What happened: T9 (`Owns: SKILL.md`, `Tests: build`) had `**Produces:** SKILL.md sections "Voice", …`; the checker reported `` `SKILL` not declared in config/skills/reviewing-periods/SKILL.md `` for the T9↔T10a and T9↔T10b seams, and `` `references` not declared in … `` for T10a↔T11 and T10b↔T11. Eight noise incidents, repeated into the final packet and the finish summary.

Fix: skip the contract and seam checks for a seam whose producer has `Tests: build` or owns no source file of a known language; or require `Produces` of such tasks to start with a marker (`doc:`) that the checker ignores.

## 3. Probe adapter runs the CLI in text mode, so the bytes-stdin probe crashes in the adapter

Where: `plan_tools adapter` (generated `.superlite/probes/adapter.py`, `run()` uses `subprocess.run(..., input=stdin, text=True, encoding="utf-8")`), `probe_run`.

What happened: the encoding probe `stdin_bytes_invalid_utf8` passed `b'\xff\xfe…'`; the adapter failed with `'bytes' object has no attribute 'encode'`, counted as a crash of the CLI, and generated `tests/regression/test_probe_encoding_1.py` at the repository root. That test imports `.superlite/probes/adapter.py`, which is git-ignored, so it cannot be committed; it had to be removed before the PR. The real CLI handled invalid stdin fine (verified by hand).

Fix: in the adapter, pass bytes through without `text=True` when `stdin` is `bytes` (decode stdout/stderr with `errors="replace"`); write generated regression tests next to the plan's tests (the `pytest.ini` `testpaths`) or make them self-contained (no adapter import).

## 4. Fresh agents need the whole prime pasted by the coordinator; eviction at 80k makes that the dominant cost

Where: `dispatch` (`fresh tier=sonnet`), the prime rule "pasted verbatim, same bytes all run", eviction `context over 80k`.

What happened: the prime was 43 to 45k characters. Nine implementers plus three re-dispatches after eviction meant the coordinator emitted the prime twelve times, about 130k output tokens; `lint` reported the coordinator at 80 % of the cost and 73 turns. Every agent crossed 80k context after one task (the prime alone is about 11k tokens plus the task plus the code it reads), so no agent was reused: `dispatch` offered `fresh` for every wave. The wall clock was 3.6× the prediction mostly for this reason.

Fix options: let the implementer read `.superlite/prime.md` itself and reply `READY <sha256>` (the coordinator compares the hash from `build_prime`); or count the prime out of the 80k eviction budget; or raise the eviction threshold for agents whose tasks are small. The `--sections` option helped a little (dropping spec sections not needed by the remaining tasks).

## 5. `commit_task` refuses every task while any unowned file is changed in the tree

Where: `commit_task.py` out-of-scope check.

What happened: the spec and the research note (docs outside `docs/superpowers/plans/`) were untracked; every `commit_task` printed `out-of-scope docs/…` and `Tn FAILED` with no hint that the docs were the cause. It took a human decision (commit the docs first) to unblock.

Fix: treat `docs/**/*.md` the way the plan folder is treated (never blocking, never staged), or print one line `hint: commit or exclude these files, they are outside every Owns` and name them once instead of once per task.

## 6. `run_tests` fails when run from a subdirectory, and the message does not say so

Where: `run_tests.py`.

What happened: three implementers ran `sl run_tests --fast …` from the skill directory and got `exit code 1: exclude: **/node_modules/**, **/.git/**` with 0 tests; they fell back to `uv run pytest`. From the repository root the same command worked.

Fix: `chdir` to the repository root (the directory holding `.superlite/`) before running, or print `run from <root>` when the cwd is below it.

## 7. `finish` crashes on a non-UTF-8 byte in the ledger

Where: `finish.py read_ledger`.

What happened: a `Ruling:` line appended with `echo` contained a literal `0xff` byte (a shell escape in the text); `finish` died with `UnicodeDecodeError`. `commit_task` also failed on the same byte.

Fix: read the ledger with `errors="replace"`, and have `incident add` and any ledger writer validate UTF-8.

## 8. Lint false positives

Where: `plan_tools lint`.

- Placeholder check: `[!todo]` (an Obsidian callout type quoted in a Global constraint) was reported as `placeholder TODO`. Suggest matching `TODO`/`TBD` only as whole uppercase words outside backticks.
- Spec coverage: sections named `Decisions (Max, 2026-10-27)`, `What the first run showed, in one paragraph`, `Acceptance (countable, on the W44 transcript)` and `Open for Max` were reported as uncovered; the documented exclusions (Intent, Decisions, Validation, Out of scope) match only exact headings. Suggest a prefix or keyword match (`Decisions`, `Acceptance`, `Validation`, `Open …`).
- `EXAMPLE:` on a consumer whose producer is already dispatched (frozen) cannot be fixed by adding `e.g.` lines to the producer; the only move is to drop the `Consumes` entry. A hint saying so would save a round.

## 9. The coordinator guard blocks a Python helper written to the scratchpad

Where: `hooks/block-coordinator-edits`.

What happened: a Bash heredoc writing a patch script to the session scratchpad (outside the repository) to edit the plan markdown was blocked as "coordinator must not write project code". Plan edits then went through the editor tool, one per hunk.

Fix: scope the guard to paths inside the repository (or outside `.superlite/`, `docs/**`, and the harness scratchpad).

## 10. Smaller notes

- `pt_review contract --seam` wants `Ta,Tb`; the error text says "two task ids" but not the comma form.
- `dispatch` evicted every agent after one task (see 4), so `poll` and `agent=ID` lines never appeared in this run.
- The human-orchestrator approval ignores an `AskUserQuestion` answer and needs a typed reply (by design, but it cost one round because the plan-writing skill did not say so at the point of asking).
- `wave0` for a Python package under a non-`src` root worked once the skeleton task's brief named `pythonpath`; it would be useful for `test-cmd.json` to record the import root for the drivers in 1.
