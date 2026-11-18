# Superlite: budget pause, project corrections, finding evidence, reviewer eval

**Goal:** a run stops spending at its cap, a user correction reaches every later run, a reviewer finding must prove the line it rests on, and reviewer quality can be measured on real merged pull requests.
**Architecture:** four packages on existing seams. `budget.py` gains a gate that `dispatch` and `fleet spawn` call. A new `corrections.py` owns one tracked project file that prime, briefs, packet and session start read. A new `finding_check.py` verifies a finding's quoted line and fingerprints it; `findings.py` screens, dedupes and ledgers with it. `bench/reviewer_eval*.py` runs the final reviewer on merged pull requests and scores graded findings.
**Tech stack:** Python 3.10+ stdlib; bash 3.2-compatible hooks; pytest through `sl run_tests`.
**Spec:** this file, section Design.
**Detail:** contracts
**Target-min:** 11
**Wave0:** none
**Max chars:** 60000

Global constraints:
- Every line of a Python script under `skills/**/scripts/` keeps the repo's `# O(...)` complexity comment and the notation header; stdlib only; LF endings. Files under `bench/` and `tests/` carry no such comments.
- This repository is public: no host names, user names, home paths, other project or repository names in code, tests, docs or commit messages.
- `hooks/session-start`: bash 3.2 syntax, builtins only on the normal path (no `cat`, no subshell), `printf`, never a heredoc; it passes `tests/scripts/test_hooks_bash32.py` and `tests/scripts/test_hooks_contract.py`.
- The verdict is `sl run_tests` (never raw pytest); every new test sees a red run before the code it tests.
- An existing test that pins a changed text or output is updated in the same task only when it is in the task's Owns. Any other test your change turns red: leave it, and name the file and the failing assertion in your report (the coordinator rules it).
- A new `sl` tool needs no registration: `sl <name>` runs `scripts/<name>.py`.
- Exit codes: 0 done, 2 usage error or refusal, 3 a `BLOCKED` gate.
- Fail open: an exception inside the budget gate or inside a corrections read never breaks `dispatch`, `fleet spawn`, a prime, a brief, a packet or the session-start hook; the caller goes on as if the gate passed or the file were absent.
- The run folder of a plan is `state.resolve(plan)`; its ledger is `<run folder>/progress.md`.

## Design

### 1. Budget pause

- The cap of a run is the newest ledger line `- Budget cap: <usd> (extend|raise) - <ruling>`, else the plan header `**Budget-usd:**`. No cap: nothing below applies.
- Paused means actual spend is above the cap (`state == "over"`, as today). While paused, `dispatch` prints `dispatch: BLOCKED: <gate line>` on stderr, nothing on stdout, exit 3; every `fleet spawn` (plain role, `--for-review`, `--package`, `--for-dispatch`) prints `BLOCKED: fleet spawn: <gate line>` and exits 3 before any pane. `commit_task`, `fleet wait`, `run_tests` and `finish` keep working, so tasks in flight finish and are committed.
- Gate line: `budget: paused: spent $<spent> of $<cap> cap; least cap to finish $<need>; <next step>`. `need` is the larger of spend and projected cost, rounded up to a cent. Next step, AI orchestrator with no extension yet: `once: sl budget extend --plan <plan> --ruling "<why>" (+25%)`; otherwise: `stop the run; the user raises it: sl budget raise --to <need> --ruling "<their words>" --plan <plan>`.
- `sl budget extend --plan P --ruling TEXT`: the AI orchestrator's one extension per run. New cap = current cap x 1.25, rounded to a cent. Refused (exit 2) without a cap, without a ruling, when the ledger already holds an `(extend)` line, or when the orchestrator is not AI.
- `sl budget raise --to USD --ruling TEXT --plan P`: the user's raise, run by the coordinator on the user's word. Refused (exit 2) without a cap, without a ruling, or when USD is not above the spend so far.
- The 70% warning stays and now names the projected cost against the cap.

### 2. Project corrections

- File: `docs/superlite/corrections.md` in the project, tracked in git. Three header lines, then one `- <text>` line per correction.
- `sl corrections add "<text>"`: one line (whitespace collapsed, home paths written as `~`), at most 300 characters. Refused whole, the file untouched (exit 2): empty text, a secret or an email address in it (the `feedback.py` patterns), a text over 300 characters, or a file that would pass 2,048 bytes. A duplicate is a no-op (exit 0). The write is atomic; inside a git work tree the file is then committed alone (`git commit -- <file>`), so no other change rides along and the run's tree stays clean for `commit_task`.
- `sl corrections list` prints numbered lines; `sl corrections rm N` drops line N the same way (atomic, committed alone).
- Readers, all through `corrections.section(root)`: the three primes (after the standing note), fixer briefs, the package-review brief, the review packet head (never cut) and the session-start hook of a main session or lead. A file over 2,048 bytes (edited by hand) is ignored by every reader.
- Capture: the session-start hook always adds one line telling the session to record a user correction with `sl corrections add`; `sl finish` prints the file's size and the same reminder.

### 3. Finding evidence

- A reviewer finding carries the exact text of the line it rests on: `file:line - problem - fix - tier N - quote: <line text>`, and `"quote"` in the report's JSON block. A finding about something missing quotes the line where it belongs (a signature, a call, a heading).
- `finding_check.verify` reads the file under the project root: the quote (whitespace collapsed, at least 6 characters) must be part of a line within 10 lines of the cited one (`verified`), else part of another line of the file (`moved`: the line is corrected), else the finding is `unverified`.
- Fingerprint: 10 hex characters of the SHA-1 of the path and the normalized quote (without a quote: the path and the problem text). It names the same finding across rounds even when line numbers move.
- `findings route` screens before it writes briefs. A final-review report (label starting `FR`) needs a quote on every finding; other reports are checked only where a finding has one. Unverified findings are not briefed: one stderr line `UNVERIFIED <file>:<line> - <problem> (<reason>) from <label>` each. Findings with one fingerprint in a call become one, at the highest tier. A fingerprint routed in an earlier call is a repeat: its tier moves up one (at most 3) and its brief line names the earlier id. A dismissed fingerprint is dropped with a `DISMISSED` stderr line.
- Ledger: `<run folder>/findings.jsonl`, one row per screened finding (`fp`, `id`, `round`, `state` routed|unverified|dismissed, `file`, `line`, `tier`, `problem`, `label`). `sl findings dismiss FP --ruling TEXT --plan P` records a dismissal and a ledger `Ruling:`; `sl findings rounds --plan P [--out FILE]` prints the earlier rounds as markdown for `packet --previous`.
- A `CHANGES_REQUESTED` whose findings are all unverified is no review: the coordinator starts a fresh final reviewer.

### 4. Reviewer eval

- A case set lives outside the repository: `<superlite home>/reviewer-eval/<set>/cases.json` (`id`, `repo`: a local clone, `base`, `merge`, `title`, `body`) and `results/<UTC timestamp>.json`.
- Per case and variant (`name=model:effort`): clone the repository at the merge commit without a remote, write the pull request text as the spec, build an inline review packet against the base, run the `final-reviewer` agent on it headlessly, parse its findings, verify each quote (section 3) and fingerprint it.
- Grading: the verified findings of all variants of a case are pooled by fingerprint, without variant names; one strong-model call per case grades each as `real`, `nit` or `wrong` and marks `serious`.
- Score per variant: real, serious, nit, wrong, ungraded, unverified, recall (its real findings over the pool's real findings), precision (real over real plus wrong), mean cost per review.
- CLI: `uv run --no-project python bench/reviewer_eval_cli.py make-case|run|report`.

### 5. Rulings

Ruling: the pause triggers on actual spend, not on the projection (because a projection early in a run is a guess; cost if wrong: the last task in flight overshoots the cap by its own cost).
Ruling: `budget raise` does not verify that a human typed it (because a hook that proves authorship is a feature of its own; cost if wrong: an AI orchestrator that ignores its instructions can raise the cap, and the ledger line shows it).
Ruling: the budget gate fails open (because the budget has never broken a caller, and unreadable metrics say nothing about spend; cost if wrong: a run with a broken metrics file is not paused).
Ruling: duplicates are findings with one fingerprint; "same path, line within 10" is the window of the quote check, not a second merge rule (because merging different quotes needs a judgment a script cannot make; cost if wrong: two wordings of one defect on neighbouring lines reach one fixer brief as two findings).
Ruling: checker lines and red-suite lines carry no quote and are not screened (because their evidence is a screenshot or a test run).
Ruling: the reviewer eval covers the final reviewer (because the package reviewer edits and commits, which needs its own harness; cost if wrong: package-review quality stays unmeasured until that harness exists).
Ruling: eval cases and results stay under the superlite home (because answer keys of private projects must not reach a public repository).
Ruling: `**Detail:** contracts` (14 small tasks with named tests and exact values; cost if wrong: a weaker test, caught by the package review).

## Coverage

| Category | State | Basis |
|---|---|---|
| Scope and success criteria | settled | the four ideas the user chose; done when each section's named tests pass, the required test layers are green and a 3-case live eval run prints a table |
| Domain and data model | ruled | ledger lines of section 1, the file of section 2, the ledger rows of section 3, the case and result files of section 4 |
| Persistence and migration | ruled | new files only; a run without `findings.jsonl` or a project without the corrections file behaves as before |
| Interfaces and contracts | ruled | `budget` keeps its flag-only form; finding lines and JSON without a quote still parse; `findings route` output lines unchanged for routed findings |
| UI states | n/a | no UI |
| Concurrency and state ownership | ruled | ledger appends through the locked append `incident.py` uses; the corrections file is replaced atomically and committed alone |
| Error handling and recovery | ruled | gate and corrections reads fail open; refused writes leave the file byte-identical |
| Security and privacy | ruled | corrections refuse secrets and emails; quote checks read only files that resolve under the project root; eval data outside the repository |
| Performance and limits | ruled | 2,048-byte file, 300-character line, 6-character quote floor, 10-line window, 2 MB file limit for a quote check, 60,000-character diff for grading |
| Observability | ruled | `BLOCKED` lines, `- Budget cap:` ledger lines, `UNVERIFIED`/`DISMISSED` lines, `findings.jsonl`, the eval result file |
| Testing strategy | ruled | named unit tests per task; headless, tui and evals layers once by the coordinator; one live 3-case eval run |
| Compatibility | ruled | Python 3.10, bash 3.2; reports written before this change (no quote) still route |
| Rollout | settled | one pull request, one patch release (the user's answer) |
| Research unknowns | n/a | none |

```mermaid
flowchart LR
  B[budget.gate] --> D[dispatch]
  B --> FS[fleet spawn]
  C[corrections.py] --> P[primes]
  C --> BR[fix and review briefs]
  C --> PK[review packet]
  CF[(docs/superlite/corrections.md)] --> C
  CF --> SS[session-start hook]
  R[reviewer report] --> FR[fleet_report.parse] --> FI[findings route]
  FC[finding_check] --> FI
  FI --> L[(findings.jsonl)]
  FI --> FB[fixer briefs]
  FR --> EV[reviewer eval]
  FC --> EV
```

## Task graph

```mermaid
flowchart LR
  BG1[budget pause core]
  BG2[dispatch and spawn gates]
  CR1[corrections tool]
  CR2[corrections in primes and finish]
  CR3[corrections in review brief and packet]
  CR4[corrections at session start]
  FD1[finding quote in reports]
  FD2[finding check]
  FD3[findings screen and ledger]
  FD4[reviewer and fixing prose]
  DOC1[skill and tool docs]
  RE1[reviewer eval core]
  RE2[reviewer eval live adapters]
  RE3[reviewer eval cli]
  %% taskgraph
  BG1 --> BG2
  CR1 --> CR2
  CR1 --> CR3
  FD2 --> FD3
  CR1 --> FD3
  FD3 --> FD4
  BG2 --> DOC1
  FD3 --> DOC1
  FD1 --> RE2
  FD2 --> RE2
  RE1 --> RE3
  RE2 --> RE3
```

```mermaid
%% schedule
gantt
  title Predicted schedule (mm:ss)
  dateFormat X
  axisFormat %M:%S
  section lane 1
  CR1 corrections tool :cr1, 0, 319s
  FD3 findings screen and ledger :fd3, 319, 344s
  DOC1 skill and tool docs :doc1, 662, 284s
  section lane 2
  RE1 reviewer eval core :re1, 0, 318s
  CR2 corrections in primes and finish :cr2, 319, 306s
  RE3 reviewer eval cli :re3, 659, 317s
  section lane 3
  BG1 budget pause core :bg1, 0, 317s
  BG2 dispatch and spawn gates :bg2, 317, 307s
  FD4 reviewer and fixing prose :fd4, 662, 284s
  section lane 4
  FD2 finding check :fd2, 0, 316s
  RE2 reviewer eval live adapters :re2, 316, 344s
  section lane 5
  CR4 corrections at session start :cr4, 0, 281s
  CR3 corrections in review brief and pack :cr3, 319, 305s
  section lane 6
  FD1 finding quote in reports :fd1, 0, 281s
```

critical path: FD2 → RE2 → RE3 (16.3 min) · peak width 6 · predicted build 16.3 min · predicted total ≈ 26.8 min (target ✗ 11.0)

## Package: budget

App type: CLI. Categories: protocol (subcommands, exit codes), state (ledger lines), numeric (cap arithmetic).
**Probe entry:** none (it reads a run folder; the named tests cover each case)

### BG1 budget pause core · Complexity 4 · Est. context 40k
**Owns:** skills/subagent-driven-development/scripts/budget.py, tests/scripts/test_budget_pause.py, tests/scripts/test_metrics_history.py
**Components:** 2
**LOC owned:** 150
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 1
**Produces:** budget.effective_cap(plan, sl_dir) -> float | None · budget.gate(plan_path, sl_dir=".superlite") -> str | None · budget.main(argv=None) -> int
  e.g. effective_cap with header `**Budget-usd:** 3.00` and no ledger line -> 3.0; with ledger lines `- Budget cap: 3.75 (extend) - a` then `- Budget cap: 6 (raise) - b` -> 6.0; without a header cap -> None
  e.g. gate with compute() giving state "over", cost_usd 3.2, cap_usd 3.0, need_usd 4.1, extended False, AI orchestrator -> 'budget: paused: spent $3.20 of $3.00 cap; least cap to finish $4.10; once: sl budget extend --plan <plan> --ruling "<why>" (+25%)'
  e.g. gate with state "warn" or "ok", or no cap -> None; gate when compute raises -> None
**Review Focus:** state: `test_effective_cap_header_then_newest_ledger_line` (the three e.g. values); protocol: `test_gate_line_over_cap_ai_not_extended` (the e.g. line, `<plan>` the path given); protocol: `test_gate_line_after_extension_names_raise` (extended True -> the line ends `stop the run; the user raises it: sl budget raise --to 4.10 --ruling "<their words>" --plan <plan>`); protocol: `test_gate_none_under_cap_and_without_cap`; state: `test_gate_never_raises` (a missing plan file -> None, no output); numeric: `test_extend_once_adds_25_percent` (cap 3.00: exit 0, stdout `budget: cap $3.00 -> $3.75 (extended once, +25%)`, ledger gains `- Budget cap: 3.75 (extend) - <ruling>`; a second extend: exit 2, stderr holds `already extended`, ledger unchanged); protocol: `test_extend_refused_for_human_orchestrator` (exit 2, stderr holds `AI orchestrator`); protocol: `test_extend_and_raise_need_a_cap_and_a_ruling` (no header cap: exit 2; `--ruling ""`: exit 2); numeric: `test_raise_must_be_above_spend` (spend 3.2: `raise --to 3` exit 2; `raise --to 6 --ruling "user"` exit 0, stdout `budget: cap $3.00 -> $6.00 (raised)`, effective_cap 6.0); numeric: `test_need_is_projection_rounded_up` (spend 3.2, projected 4.0934 -> need_usd 4.10; projected None -> need_usd 3.20); protocol: `test_flag_only_form_still_prints_the_line` (`budget.py --plan P` exit 0, one `budget:` line); protocol: `test_warn_names_projection_against_cap` (state warn, projected 2.4, cap 3 -> the line holds `WARN: 70% of the cap reached; projected $2.40 against the $3.00 cap`); protocol: `test_over_line_says_paused` (state over -> the line holds `OVER CAP: paused` and the gate line's text after `budget: paused: `)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** `compute()` uses `effective_cap` for `cap_usd` and adds `header_cap_usd`, `extended` (an `(extend)` ledger line exists) and `need_usd`; the `state` rule is unchanged. `main` takes an optional first word `extend` or `raise` before the flags and keeps the flag-only form. The orchestrator mode comes from `orchestrator.py`'s own reader (the function `orchestrator status` prints from), never a second parser. Ledger lines are appended to `<dir>/progress.md` with one trailing newline. Gate and line tests patch `budget.compute`; ledger and CLI tests use `tmp_path` and patch `compute` for the spend. `test_metrics_history.py` is owned only to update the two tests that pin the old WARN and OVER CAP wording.

### BG2 dispatch and spawn gates · Complexity 3 · Est. context 46k
**Owns:** skills/subagent-driven-development/scripts/dispatch.py, skills/subagent-driven-development/scripts/fleet.py, tests/scripts/test_budget_gate.py
**Components:** 2
**LOC owned:** 60
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 1
**Review Focus:** protocol: `test_dispatch_refuses_while_paused` (gate patched to return `budget: paused: x`: exit 3, stderr `dispatch: BLOCKED: budget: paused: x`, stdout empty); protocol: `test_dispatch_runs_when_gate_is_none` (exit 0, the dispatch lines as before); state: `test_dispatch_gate_error_fails_open` (gate patched to raise: exit 0); protocol: `test_fleet_spawn_refuses_before_any_pane` (plain `spawn --role fixer --tier sonnet`: exit 3, stdout `BLOCKED: fleet spawn: budget: paused: x`, no worker added to fleet.json); protocol: `test_fleet_for_dispatch_and_for_review_refuse` (each: exit 3, the same line, no worker); protocol: `test_fleet_spawn_without_a_plan_is_not_gated` (a brief-only spawn outside a plan run reaches the next check)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** The gate is BG1's `budget.gate(plan_path, sl_dir=".superlite") -> str | None` (the refusal line while paused, else None; `sl task BG1` shows its examples). In `dispatch.main` the gate sits right after the disk check and before `render`. In `fleet.py` it sits beside the disk gate and also covers `--for-dispatch` (which the disk gate leaves to dispatch): one check for every spawn path that knows its plan, before any pane or worker id. Follow how the neighbouring tests of `test_fleet.py` and `test_fleet_trees_614.py` start a spawn without Herdr.

## Package: corrections

App type: CLI and file I/O. Categories: file (atomic write, cap, git commit of one path), encoding (one line, UTF-8, JSON escaping in the hook), state (duplicates, oversize file), protocol (exit codes).
**Probe entry:** none (it writes and commits a project file; the named tests cover each case)

### CR1 corrections tool · Complexity 5 · Est. context 36k
**Owns:** skills/subagent-driven-development/scripts/corrections.py, tests/scripts/test_corrections.py
**Components:** 2
**LOC owned:** 170
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 2
**Produces:** corrections.FILE: str · corrections.MAX_BYTES: int · corrections.MAX_LINE: int · corrections.add(root: Path, text: str, commit: bool = True) -> tuple[int, str] · corrections.remove(root: Path, n: int, commit: bool = True) -> tuple[int, str] · corrections.lines(root: Path) -> list[str] · corrections.section(root: Path) -> str | None · corrections.main(argv=None) -> int
  e.g. FILE == "docs/superlite/corrections.md"; MAX_BYTES == 2048; MAX_LINE == 300
  e.g. add(root, "Use uv,\n never pip") on a project without the file -> (0, "corrections: added (1 line, <n>/2048 bytes)") and lines(root) == ["Use uv, never pip"]
  e.g. add(root, "key ghp_abcdefghijklmnopqrstuvwxyz0123456789") -> (2, "corrections: refused: the text holds a secret or an email address"), no file written
  e.g. section(root) with lines ["Use uv, never pip", "German UI strings"] -> "## Corrections (binding, from the user)\n\n- Use uv, never pip\n- German UI strings"; section(root) without the file -> None
**Review Focus:** file: `test_add_creates_file_with_header_and_line` (the file starts `# Corrections`, ends with `- Use uv, never pip\n`, LF only); encoding: `test_add_collapses_whitespace_to_one_line`; encoding: `test_add_writes_home_path_as_tilde` (a text holding the test's home path stores `~`); protocol: `test_add_refuses_secret_and_email` (the e.g. and `mail a@b.example`: code 2, file absent); protocol: `test_add_refuses_over_300_characters` (301 characters: code 2, message holds `300 characters`); file: `test_add_over_cap_leaves_file_byte_identical` (fill to within 20 bytes of 2048, add 40 more: code 2, message holds `2048-byte cap` and `sl corrections rm`, file bytes equal); state: `test_add_duplicate_is_a_noop` (same text in another case and spacing: (0, "corrections: already recorded"), mtime and bytes unchanged); file: `test_add_commits_only_its_file` (a git repo with another modified tracked file: after add, `git status --porcelain` lists only that other file, `git log -1 --format=%s` starts `corrections: `, `git show --stat --format= HEAD` names only the corrections file); file: `test_add_without_git_writes_and_makes_no_commit`; file: `test_failed_commit_keeps_the_line_and_says_so` (a repo whose `pre-commit` hook exits 1: code 0, message ends `; not committed: ` plus git's last line); state: `test_remove_drops_line_n_and_refuses_a_bad_n` (rm 1 of 2 keeps the second; rm 5: code 2); state: `test_section_ignores_an_oversize_file` (a 3,000-byte file: lines == [] and section is None); protocol: `test_cli_add_list_rm_exit_codes` (`add` 0 then `list` prints `1. Use uv, never pip`; `list` on no file prints `corrections: none`; `rm 9` exits 2)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** The header is three fixed lines: `# Corrections`, a blank line, `One line per correction from the user; superlite gives this file to every run. Managed by sl corrections.`, then a blank line before the list. Secret and email detection reuses the pattern table of `feedback.py` (import it; a text is refused when `feedback.scrub` would write `<secret>` or `<email>` into it); the home-path rewrite reuses the same table's path patterns. Check the 300-character limit before anything truncates. Atomic write: a temp file in the same folder, then `os.replace`. Commit: `git -C <root> add -- <FILE>` then `git -C <root> commit -q -m "corrections: <text cut to 60 characters>" -- <FILE>`; never `git add -A`. `root` in the CLI is `--root`, else the git top level of the current folder, else the current folder. A leading `- ` of the text is dropped.

### CR2 corrections in primes and finish · Complexity 3 · Est. context 44k
**Owns:** skills/subagent-driven-development/scripts/build_prime.py, skills/subagent-driven-development/scripts/finish.py, tests/scripts/test_prime_corrections.py
**Components:** 2
**LOC owned:** 50
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 2
**Consumes:** corrections.section(root: Path) -> str | None (CR1) · corrections.lines(root: Path) -> list[str] (CR1) · corrections.FILE: str (CR1) · corrections.MAX_BYTES: int (CR1)
**Review Focus:** state: `test_slim_prime_has_corrections_after_the_standing_note` (a run with a standing note and one correction: the index of `## Corrections (binding, from the user)` is after the standing note's and before `## Background`); state: `test_mini_and_full_primes_have_the_section` (once each); state: `test_prime_without_the_file_has_no_section`; state: `test_prime_survives_a_corrections_error` (`corrections.section` patched to raise: the prime builds, no section); protocol: `test_finish_summary_names_corrections` (two corrections: the summary holds `corrections: 2 lines, <n>/2048 bytes (docs/superlite/corrections.md); a user correction from this run that later runs need: sl corrections add "<rule>"`; no file: `corrections: 0 lines, 0/2048 bytes`)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** The project root is the one each builder already uses (`pt.stable_root(str(plan))`). One helper in `build_prime.py` wraps the call and returns None on any exception; `build`, `build_slim` and `build_mini` each add its result right after the standing-note part (after `Read first` when there is no note). In `finish.py` the line joins the summary block next to the rulings; follow the existing tests of `finish.summary` for the fixture.

### CR3 corrections in review brief and packet · Complexity 3 · Est. context 52k
**Owns:** skills/subagent-driven-development/scripts/fleet_io.py, skills/subagent-driven-development/scripts/pt_review.py, tests/scripts/test_brief_corrections.py
**Components:** 2
**LOC owned:** 40
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 2
**Consumes:** corrections.section(root: Path) -> str | None (CR1)
**Review Focus:** state: `test_review_brief_has_corrections` (`fleet_io.review_brief` for one committed task in a project with one correction holds the section once); state: `test_packet_head_has_corrections_after_the_standing_note`; state: `test_packet_corrections_survive_the_size_cap` (`--max-tokens 2000`: the section is still whole); state: `test_inline_packet_has_corrections` (`packet --inline --spec`); state: `test_brief_and_packet_without_the_file_are_unchanged` (byte-identical to a build with `corrections.section` patched to return None); state: `test_a_corrections_error_changes_nothing` (patched to raise: both build)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** In `pt_review.cmd_packet` the section sits in the head list right after the `## Standing note` block, which is never cut. In `fleet_io.review_brief` it sits where the brief carries its standing note. Fixtures: `tests/scripts/test_packet_standing_note_738.py` and `tests/scripts/test_review_brief_note_738.py` show how to build both.

### CR4 corrections at session start · Complexity 3 · Est. context 34k
**Owns:** hooks/session-start, tests/scripts/test_session_start_corrections.py
**Components:** 1
**LOC owned:** 30
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 2
**Review Focus:** state: `test_main_session_gets_the_corrections_lines` (cwd holds the file with two lines: the context holds `Project corrections (binding, from the user; docs/superlite/corrections.md):` followed by both `- ` lines); protocol: `test_every_main_session_gets_the_capture_line` (with and without the file the context holds `When the user corrects you in a way later runs need, record it: sl corrections add "<rule>".`); state: `test_oversize_file_is_skipped` (a 3,000-character file: no `Project corrections` text, the capture line still there); state: `test_worker_session_gets_no_corrections` (`SUPERLITE_FLEET_WORKER=W1`: neither text); state: `test_lead_session_gets_them` (`SUPERLITE_FLEET_ROLE=lead` with a worker id: both texts); encoding: `test_output_stays_valid_json` (a corrections line holding `"`, `\` and a tab: stdout parses with `json.loads` and the line reads back unchanged, the tab as a tab)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** Add both texts to `content` after the version line and before the compaction block, so `escape_for_json` covers them. Read the file with `IFS= read -r -d ''` (it returns 1 at end of file), take only its lines that start with `- `, and skip the file when it is longer than 2,048 characters. The file path is relative to the hook's working folder. The header text of the file is not copied.

## Package: findings

App type: CLI and library. Categories: protocol (report grammar, subcommands, exit codes), file (paths under the root), encoding (whitespace, backticks, CRLF), state (ledger, rounds, repeats).
**Probe entry:** none (it reads report files and a project tree; the named tests cover each case)

### FD1 finding quote in reports · Complexity 3 · Est. context 36k
**Owns:** skills/subagent-driven-development/scripts/fleet_report.py, tests/scripts/test_fleet_report_quote.py
**Components:** 1
**LOC owned:** 30
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 3
**Produces:** fleet_report.parse(text: str, label: str = "", allow_json: bool = True) -> dict
  e.g. parse("Verdict: CHANGES_REQUESTED\nsrc/a.py:12 - off by one - use <= - tier 1 - quote: `for i in range(n - 1):`")["findings"] -> [{"file": "src/a.py", "line": 12, "problem": "off by one", "fix": "use <=", "tier": 1, "quote": "for i in range(n - 1):"}]
  e.g. the same line without ` - quote: ...` -> the same entry with "quote": ""
  e.g. a json block whose finding has "quote": "x = 1" -> that finding keeps "quote": "x = 1"; a finding with "quote": 5 breaks the block (valid False)
**Review Focus:** protocol: `test_finding_line_with_quote` and `test_finding_line_without_quote` (the two e.g. lines); encoding: `test_quote_keeps_inner_dashes_and_tier_words` (quote `` `x = a - b  # - tier 2 - quote: y` `` after `- tier 1 - quote: `: tier 1, the quote is the whole text between the outer backticks); encoding: `test_quote_without_backticks` (`- quote: return None` -> "return None"); protocol: `test_json_finding_quote_must_be_a_string`; protocol: `test_review_and_work_templates_name_quote` (`fleet_report.REVIEW`, `WORK` and `WORK_BATCH` each hold `"quote": "<the exact text of that source line>"`)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** `FINDING_LINE` gains one optional tail group after `tier N`; the first `- tier N` that is followed by the tail or the line end ends the fix text. One pair of wrapping backticks is dropped from the quote. `_finding_ok` accepts a missing `quote` and a string one. Tests that read `REVIEW` or `WORK` by name keep passing; one that pins their literal text is reported, not edited.

### FD2 finding check · Complexity 5 · Est. context 30k
**Owns:** skills/subagent-driven-development/scripts/finding_check.py, tests/scripts/test_finding_check.py
**Components:** 2
**LOC owned:** 140
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 3
**Produces:** finding_check.normalize(s: str) -> str · finding_check.fingerprint(file: str, quote: str, problem: str = "") -> str · finding_check.verify(root: Path, finding: dict, window: int = 10) -> dict · finding_check.LEDGER: str · finding_check.load(sd: Path) -> list[dict] · finding_check.append(sd: Path, row: dict) -> None · finding_check.next_round(rows: list[dict]) -> int · finding_check.prior(rows: list[dict], fp: str) -> dict | None
  e.g. normalize("  `for i in   range(n - 1):` ") -> "for i in range(n - 1):"
  e.g. fingerprint("src/a.py", "for i in range(n - 1):") == fingerprint("src/a.py", "  for i in  range(n - 1): "), 10 lowercase hex characters; fingerprint("src/a.py", "", "off by one") != fingerprint("src/a.py", "off by one")
  e.g. verify(root, {"file": "src/a.py", "line": 14, "quote": "for i in range(n - 1):"}) with that text on line 12 -> {"state": "verified", "line": 12, "reason": ""}
  e.g. the same quote only on line 80 -> {"state": "moved", "line": 80, "reason": "quote found at line 80"}; a quote not in the file -> {"state": "unverified", "line": 14, "reason": "quote not in file"}
  e.g. LEDGER == "findings.jsonl"; next_round([]) -> 1; next_round([{"round": 2}]) -> 3; prior(rows, "ab12") -> the newest row with that fp and state "routed" or "dismissed", else None
**Review Focus:** encoding: `test_normalize_and_fingerprint` (the e.g. values); encoding: `test_verify_matches_part_of_a_line_whitespace_blind_case_sensitive` (quote `range(n - 1)` matches `for i in  range(n - 1):`; `Range(n - 1)` does not); state: `test_verify_window_and_moved` (the three e.g. results; two matches outside the window: the nearest line wins); protocol: `test_verify_reasons` ("no quote" for a missing or empty quote, "quote too short" for 5 normalized characters, "file not found", "file too large" for a file over 2 MB, "quote not in file"); file: `test_verify_refuses_paths_outside_the_root` (`../x.py`, an absolute path outside, and a symlink inside the root that points outside: "outside root", the target never read); encoding: `test_verify_reads_crlf_and_bad_utf8` (a CRLF file and one with an invalid byte: the quote on a clean line verifies); state: `test_ledger_append_load_and_bad_lines` (two appends then a garbage line: load returns the two rows); state: `test_prior_ignores_unverified_rows`
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** The fingerprint hashes `file + "\n" + normalize(quote)`, or `file + "\n?" + normalize(problem)` when the quote is empty. `verify` resolves `root / file` and requires the result to be inside `root.resolve()` before it opens anything; it reads with `errors="replace"`. Append with the locked append helper `incident.py` exports (the one `feedback.py` imports), so two writers never interleave.

### FD3 findings screen and ledger · Complexity 6 · Est. context 58k
**Owns:** skills/subagent-driven-development/scripts/findings.py, tests/scripts/test_findings_screen.py, tests/scripts/test_findings_route.py, tests/scripts/test_findings_brief_603.py
**Components:** 3
**LOC owned:** 190
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 2, 3
**Consumes:** finding_check.verify(root: Path, finding: dict, window: int = 10) -> dict (FD2) · finding_check.fingerprint(file: str, quote: str, problem: str = "") -> str (FD2) · finding_check.append(sd: Path, row: dict) -> None (FD2) · finding_check.next_round(rows: list[dict]) -> int (FD2) · finding_check.prior(rows: list[dict], fp: str) -> dict | None (FD2) · corrections.section(root: Path) -> str | None (CR1)
**Produces:** findings.screen(found: list[dict], root: Path, sd: Path) -> tuple[list[dict], list[str]] · findings.main(argv=None) -> int
  e.g. screen of one `FR1` finding without a quote -> ([], ["UNVERIFIED src/a.py:12 - off by one (no quote) from FR1"])
  e.g. screen of two findings with one fingerprint, tiers 1 and 2 -> one finding, tier 2
**Review Focus:** state: `test_final_review_finding_without_quote_is_not_briefed` (route of an `FR1` report with one such finding: stdout `findings: none routed (1 unverified, 0 dismissed)`, stderr the e.g. line, no brief file, one ledger row state `unverified`); state: `test_other_reports_route_without_a_quote` (a report labelled `T3`: routed as before, its ledger row has a fingerprint from path and problem); state: `test_moved_quote_corrects_the_line` (the brief line names the line the quote is on); state: `test_one_fingerprint_twice_becomes_one_finding_at_the_highest_tier`; state: `test_repeat_moves_up_one_tier_and_names_the_earlier_id` (round 1 routes `F-T1-1` at tier 1; the same fingerprint in round 2: tier 2, the brief line holds `repeat of F-T1-1`, the `fixer` line says `tier=sonnet-high`; a tier 3 repeat stays 3); state: `test_dismissed_fingerprint_is_dropped` (after `dismiss`: route prints stderr `DISMISSED <fp> src/a.py:12 - off by one (ruled: not a defect)` and writes no brief for it); protocol: `test_dismiss_records_ruling_and_refuses_unknown_fp` (`dismiss <fp> --ruling "not a defect" --plan P`: exit 0, a ledger row state `dismissed`, `progress.md` gains `- Ruling: finding <fp> src/a.py:12 dismissed - not a defect`; an unknown fp or an empty ruling: exit 2); protocol: `test_rounds_markdown` (two rounds: stdout has `## Round 1` and `## Round 2`, each finding as `- F-T1-1 src/a.py:12 - off by one (tier 1) fp <fp>: routed`; `--out F` writes the same text; no ledger: `rounds: none`); protocol: `test_brief_line_carries_quote_and_fingerprint` (the brief's finding line ends `` quote: `for i in range(n - 1):` fp: <fp> ``); state: `test_fix_brief_has_corrections` (a project with one correction: the task brief and the coordinator brief each hold the corrections section once, after the standing note); state: `test_route_without_ledger_or_corrections_file_still_works`
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** The ledger rows come from FD2's `finding_check.load(sd: Path) -> list[dict]` (every row of `<run folder>/findings.jsonl`, bad lines skipped). `collect` keeps `quote` and dedupes as today; `screen` then verifies, fingerprints, merges and checks the ledger. A quote is required when the report label starts with `FR` (any case); elsewhere a finding is verified only when it has one. `route` calls `screen`, numbers the survivors as today, appends one ledger row per screened finding with the round `next_round` gives for the call, and prints the notes on stderr. A corrections error leaves the briefs without the section. The two owned existing test files are owned only to follow the new finding-line tail and the `none routed` wording.

### FD4 reviewer and fixing prose · Complexity 3 · Est. context 40k
**Owns:** agents/final-reviewer.md, agents/package-reviewer.md, skills/subagent-driven-development/fixing.md, skills/subagent-driven-development/fleet.md, tests/scripts/test_docs_finding_quote.py
**Components:** 1
**LOC owned:** 60
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 3
**Review Focus:** protocol: `test_final_reviewer_grammar_names_quote` (agents/final-reviewer.md holds ``file:line - problem - fix - tier N - quote: `<the exact text of that line>` `` and `a finding whose quote is not in the file is dropped`); protocol: `test_final_reviewer_missing_things_quote_an_anchor` (it holds `quotes the line where it belongs`); protocol: `test_final_reviewer_names_earlier_findings_by_id` (the section 0b rule holds `naming the earlier one by its id`); protocol: `test_package_reviewer_open_findings_carry_quote` (agents/package-reviewer.md holds `an open finding carries the exact text of its line as quote`); protocol: `test_fixing_names_unverified_repeat_and_dismiss` (fixing.md holds `UNVERIFIED`, `repeat of`, `findings dismiss` and `no review: start a fresh final reviewer`); protocol: `test_fleet_md_names_rounds` (fleet.md holds `findings rounds --plan $PLAN --out` and `packet --previous`); protocol: `test_final_reviewer_keeps_its_older_rules` (the phrases `Checked:`, `FAST PATH`, `partial: lines A-B not read` and `at most 300 words` are still there)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** In final-reviewer.md the quote sits outside the 300-word cap (say so in the Output paragraph). fixing.md gets three bullets: an `UNVERIFIED` line is no finding and goes to no fixer, and a review whose findings are all unverified is no review; a repeat arrives one tier up and counts as a failed round; a finding ruled no defect is closed with `"$SL" findings dismiss <fp> --ruling "<why>" --plan PLAN`. fleet.md's Fixers bullet gains the stderr lines and, for a later round, `"$SL" findings rounds --plan $PLAN --out <abs>/.superlite/rounds.md` before `plan_tools packet --previous`. Change nothing else in these files; every `sl` call written must exist (tests/scripts/test_doc_contract.py).

## Package: docs

App type: file I/O (prose). Categories: file, encoding.
**Probe entry:** none (prose; the named tests pin the wording)

### DOC1 skill and tool docs · Complexity 3 · Est. context 46k
**Owns:** skills/subagent-driven-development/SKILL.md, skills/subagent-driven-development/metrics.md, docs/gates.md, docs/tools.md, commands/resume.md, tests/scripts/test_docs_budget_corrections.py
**Components:** 1
**LOC owned:** 60
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 1, 2, 3
**Review Focus:** protocol: `test_skill_budget_section_names_pause_extend_and_raise` (SKILL.md's `## Measure and budget` holds `BLOCKED: budget`, `budget extend --plan $PLAN --ruling`, `budget raise --to` and `/superlite:resume`, and no longer `no extra review rounds`); protocol: `test_skill_stop_conditions_name_the_budget_pause` (the Stop conditions section holds `a budget pause after the one extension`); protocol: `test_skill_final_review_names_unverified_and_rounds` (the Final review section holds `UNVERIFIED` and `findings rounds`); protocol: `test_skill_names_corrections_add` (SKILL.md holds `corrections add`); protocol: `test_metrics_md_documents_the_subcommands` (metrics.md holds `sl budget extend` and `sl budget raise`); protocol: `test_gates_md_row` (docs/gates.md's cost-cap row holds `pauses the run` and no longer `stops optional work`); protocol: `test_tools_md_rows` (docs/tools.md has rows for `corrections` and `finding_check`, and its `budget` and `findings` rows name `extend`, `raise`, `dismiss` and `rounds`); protocol: `test_resume_names_budget_raise` (commands/resume.md holds `sl budget raise`)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** SKILL.md, `## Measure and budget`: at `WARN` finish the work in flight; while paused, `dispatch` and `fleet spawn` exit 3 with `BLOCKED: budget ...`; an AI orchestrator runs `"$SL" budget extend --plan $PLAN --ruling "<why>"` once; refused, or paused again: commit what finished, write `.superlite/stopped.md` as `/superlite:stop` does, `fleet stop --all`, and end the turn with the line's least cap; the user's raise is `"$SL" budget raise --to <usd> --ruling "<their words>" --plan $PLAN`, then `/superlite:resume`; a human orchestrator never extends. Stop conditions: add the pause to the AI orchestrator's list of reasons to end a turn. Final review step 4: `findings route` drops `UNVERIFIED` findings; `findings: none routed` after `CHANGES_REQUESTED` means a fresh final reviewer; a later round builds the packet with `findings rounds` output as `--previous`. Rulings paragraph: one sentence, a user correction later runs need goes to `"$SL" corrections add "<rule>"`. Keep every other sentence of these files; keep SKILL.md's length within 600 characters of today's.

## Package: reviewer eval

App type: CLI and data pipeline. Categories: numeric (recall, precision, means, empty pools), state (pooling, grades without a finding), file (set folder, results outside the repository), protocol (variants, subcommands).
**Probe entry:** none (it starts paid model runs and clones repositories; the named tests use fakes)

### RE1 reviewer eval core · Complexity 4 · Est. context 30k
**Owns:** bench/reviewer_eval.py, tests/bench/test_reviewer_eval.py
**Components:** 2
**LOC owned:** 160
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 4
**Produces:** reviewer_eval.CaseError(ValueError) · reviewer_eval.load_cases(set_dir: Path) -> list[dict] · reviewer_eval.parse_variant(text: str) -> dict · reviewer_eval.pool(found: dict[str, list[dict]]) -> list[dict] · reviewer_eval.score(found: dict[str, list[dict]], grades: dict[str, dict], stats: dict[str, dict]) -> dict[str, dict] · reviewer_eval.run_case(case: dict, variants: list[dict], review_fn, grade_fn, work: Path) -> dict · reviewer_eval.summarize(rows: list[dict]) -> dict[str, dict] · reviewer_eval.table(summary: dict[str, dict]) -> str
  e.g. parse_variant("fast=sonnet:medium") -> {"name": "fast", "model": "sonnet", "effort": "medium"}; parse_variant("sonnet") raises ValueError
  e.g. pool({"a": [{"fp": "f1", "file": "x.py", "line": 3, "problem": "p1", "quote": "q1"}, {"fp": "f2", ...}], "b": [{"fp": "f2", ...}, {"fp": "f3", ...}]}) -> three entries sorted by fp, each with exactly the keys fp, file, line, problem, quote
  e.g. score(that found, {"f1": {"grade": "real", "serious": True}, "f2": {"grade": "real", "serious": False}, "f3": {"grade": "wrong", "serious": False}}, {"a": {"unverified": 0, "cost_usd": 1.0}, "b": {"unverified": 2, "cost_usd": 0.5}}) -> {"a": {"real": 2, "serious": 1, "nit": 0, "wrong": 0, "ungraded": 0, "unverified": 0, "recall": 1.0, "precision": 1.0, "cost_usd": 1.0}, "b": {"real": 1, "serious": 0, "nit": 0, "wrong": 1, "ungraded": 0, "unverified": 2, "recall": 0.5, "precision": 0.5, "cost_usd": 0.5}}
  e.g. run_case(case, variants, review_fn, grade_fn, work) -> {"case": case["id"], "pool": 3, "variants": <the score dict>}; review_fn(case, variant, work) -> {"findings": [...], "unverified": int, "cost_usd": float, "seconds": float}; grade_fn(case, pooled) -> {fp: {"grade": ..., "serious": ...}}
**Review Focus:** numeric: `test_score_example` (the e.g. values); numeric: `test_score_without_real_findings` (a pool with no `real` grade: recall None; a variant with no real and no wrong: precision None; nothing divides by zero); state: `test_ungraded_and_unknown_grades` (a pooled fp without a grade counts as `ungraded` and leaves recall and precision alone; a grade for an fp not in the pool is ignored; a grade word other than real, nit, wrong counts as `ungraded`); state: `test_pool_hides_variants_and_is_stable` (the e.g. pool; the same input in another dict order gives the same list); protocol: `test_parse_variant` (the e.g. values; an empty name, model or effort raises ValueError); file: `test_load_cases_checks_keys_and_ids` (a case without `merge` raises CaseError naming the key; an id holding `/` or `..` raises CaseError; a missing cases.json raises CaseError); state: `test_run_case_calls_review_per_variant_and_grade_once` (two variants: review_fn called twice, grade_fn once with the pooled list); numeric: `test_summarize_and_table` (two rows: counts are summed, recall is total real over total pool real, cost_usd is the mean per review; `table` has one header line and one line per variant, variants sorted by name)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** Pure functions: no subprocess, no model call, no import from `skills/`. A case has the keys `id`, `repo`, `base`, `merge`, `title`, `body`; an id matches `^[A-Za-z0-9._-]{1,64}$` and is not `.` or `..`. A row keeps the pool's real count as `pool_real`, so `summarize` can total it. Tests live in `tests/bench/` and import the module the way `tests/bench/test_mechanical_ab.py` imports its own.

### RE2 reviewer eval live adapters · Complexity 6 · Est. context 56k
**Owns:** bench/reviewer_eval_live.py, bench/experiments/common.py, tests/bench/test_reviewer_eval_live.py
**Components:** 3
**LOC owned:** 190
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 4
**Consumes:** fleet_report.parse(text: str, label: str = "", allow_json: bool = True) -> dict (FD1) · finding_check.verify(root: Path, finding: dict, window: int = 10) -> dict (FD2) · finding_check.fingerprint(file: str, quote: str, problem: str = "") -> str (FD2)
**Produces:** reviewer_eval_live.LiveError(RuntimeError) · reviewer_eval_live.checkout(case: dict, work: Path) -> Path · reviewer_eval_live.packet(clone: Path, case: dict) -> Path · reviewer_eval_live.review(case: dict, variant: dict, work: Path) -> dict · reviewer_eval_live.grade(case: dict, pooled: list[dict], model: str = "opus") -> dict
  e.g. checkout({"id": "pr-7", "repo": "<a local repo>", "merge": "<sha>", ...}, work) -> work/"pr-7", HEAD detached at the merge commit, `git remote` prints nothing
  e.g. review(case, {"name": "current", "model": "opus", "effort": "high"}, work) with a reviewer reply of two finding lines, one quoting a line that is not in the file -> {"findings": [<one entry with "fp">], "unverified": 1, "cost_usd": 0.42, "seconds": <float>}
  e.g. grade(case, pooled) with a reply `[{"fp": "f1", "grade": "real", "serious": true}]` -> {"f1": {"grade": "real", "serious": True}}; a reply without a JSON array -> {}
**Review Focus:** file: `test_checkout_detaches_at_merge_without_a_remote` (a two-commit repo in `tmp_path`; a second checkout of the same case replaces the folder); file: `test_packet_writes_spec_and_returns_the_packet_path` (the packet tool faked: `<clone>/.superlite/spec.md` starts `# <title>`, the command holds `packet`, `--inline`, `--spec` and `--base <base>`; a non-zero exit raises LiveError with the tool's stderr); state: `test_review_parses_verifies_and_fingerprints` (the e.g., with the model call faked to return that reply and `total_cost_usd` 0.42); protocol: `test_review_uses_the_variant_model_and_effort` (the command holds `--agent final-reviewer`, the variant's model in the `--agents` entry and `--effort high`); state: `test_review_model_failure_raises_live_error` (no result event: LiveError naming the case and variant); numeric: `test_grade_parses_array_and_bad_reply_gives_no_grades` (the two e.g. results; an entry without `fp` is skipped); file: `test_grade_cuts_the_diff_to_60000_characters` (a 100,000-character diff: the prompt's diff part is 60,000 characters and ends with a `(diff cut)` line); protocol: `test_grade_prompt_hides_variant_names` (the prompt holds each pooled fp and no variant name)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** `checkout`: `git clone --no-hardlinks -q <repo> <work>/<id>`, `git checkout -q --detach <merge>`, `git remote remove origin`. `packet`: write `.superlite/spec.md` as `# <title>`, a blank line, the body; run this checkout's `sl plan_tools packet --inline --spec .superlite/spec.md --base <base>` in the clone; return `.superlite/review-packet.md`. `review`: checkout, packet, then the command `mechanical_ab.claude_cmd(model, prompt, budget, agent="final-reviewer")` with its `--effort` value replaced by the variant's, prompt `fleet_report.brief_message("final-reviewer", <packet path>)`, cwd the clone, env `common.clean_env()`, timeout 1800 s, budget 3.0; then `fleet_report.parse`, `finding_check.verify` against the clone (a `moved` result corrects the line) and `finding_check.fingerprint`. Stream parsing: move the event and result parsing of `common.run_claude` into `common.parse_stream(stdout: str, seconds: float) -> Run` and have `run_claude` call it; `review` uses the same function (that is the only change to common.py). `grade`: one tool-less `common.run_claude` call as `bench/experiments/e4_review.py` makes it (budget 2.0), prompt: the pull request title and body, `git diff <base> <merge>` from the case's repo cut to 60,000 characters, the pooled findings as `fp | file:line | problem | quote` lines, and the instruction to answer only a JSON array of `{"fp", "grade": "real"|"nit"|"wrong", "serious": true|false}`: real = a defect the change introduces or leaves in the changed code, nit = true but no defect, wrong = not true; serious = wrong results, data loss, a crash or a security hole. Every subprocess and model call goes through a module-level function the tests patch; no test starts `claude` or the network.

### RE3 reviewer eval cli · Complexity 4 · Est. context 40k
**Owns:** bench/reviewer_eval_cli.py, docs/experiments.md, tests/bench/test_reviewer_eval_cli.py
**Components:** 2
**LOC owned:** 150
**Tests:** fast
**Model:** sonnet
**Kind:** design
**Covers:** 4
**Consumes:** reviewer_eval.parse_variant(text: str) -> dict (RE1) · reviewer_eval.run_case(case: dict, variants: list[dict], review_fn, grade_fn, work: Path) -> dict (RE1) · reviewer_eval.table(summary: dict[str, dict]) -> str (RE1) · reviewer_eval.CaseError(ValueError) (RE1) · reviewer_eval_live.review(case: dict, variant: dict, work: Path) -> dict (RE2) · reviewer_eval_live.grade(case: dict, pooled: list[dict], model: str = "opus") -> dict (RE2) · reviewer_eval_live.LiveError(RuntimeError) (RE2)
**Produces:** reviewer_eval_cli.set_dir(name: str) -> Path · reviewer_eval_cli.main(argv=None) -> int
  e.g. set_dir("own") with SUPERLITE_HOME=/tmp/h -> Path("/tmp/h/reviewer-eval/own"); set_dir("../x") raises ValueError
**Review Focus:** file: `test_set_dir_under_the_superlite_home_and_refuses_bad_names` (the e.g. values; without SUPERLITE_HOME: under the user's `.superlite`); protocol: `test_make_case_appends_and_refuses_a_duplicate` (`make-case --repo R --pr 7 --set own` with the `gh` call faked to return a merge commit, title and body: cases.json gains id `pr-7` with `base` = the merge commit's first parent; a second call exits 2 with `pr-7 already in the set`; a pull request without a merge commit exits 2); protocol: `test_run_default_variant_comes_from_the_agent_file` (no `--variant`: one variant `current` with the `model:` and `effort:` of agents/final-reviewer.md); state: `test_run_writes_results_and_prints_the_table` (two cases, review and grade faked: exit 0, `<set>/results/<timestamp>.json` holds `rows` and `summary`, stdout ends with the table; nothing is written under the repository); state: `test_run_limit_and_a_failing_case` (`--limit 1` runs one case; a case whose review raises LiveError is listed under `failed` in the result file, the other cases still run, exit 1); protocol: `test_report_prints_the_newest_result` (two result files: the newer one's table; no results: exit 2, `no results in <set>`); protocol: `test_usage_errors_exit_2` (an unknown set, a bad `--variant`); file: `test_experiments_doc_has_the_section` (docs/experiments.md has a `## Reviewer eval` heading and names the three subcommands)
**Steps:** 1 failing tests, 2 run: FAIL, 3 implement, 4 run: PASS
**Notes:** Two more RE1 functions are used: `reviewer_eval.load_cases(set_dir: Path) -> list[dict]` (the cases of `<set>/cases.json`; CaseError on a missing file, key or a bad id) and `reviewer_eval.summarize(rows: list[dict]) -> dict[str, dict]` (per-variant totals of the `run_case` rows, the input of `table`). Flags: `make-case --repo PATH --pr N --set NAME`; `run --set NAME [--variant name=model:effort]... [--limit N] [--grader-model opus] [--work DIR]` (work default: a fresh temp folder, removed at the end); `report --set NAME`. `make-case` reads `gh pr view N --json mergeCommit,title,body` in the repo through one module-level function the tests patch. Timestamps: UTC `%Y%m%dT%H%M%SZ`. The docs section (about 25 lines): what a case set is and where it lives, the three commands, how to read the table, change one setting per comparison, a run spends model quota per case and variant. Add no other change to docs/experiments.md.

## Review Focus

- budget (CLI): protocol, state, numeric. Risks: a gate that blocks `commit_task` or `finish` and strands work in flight; a second extension; a raise below the spend.
- corrections (CLI, file I/O): file, encoding, state, protocol. Risks: a commit that takes other files along; a truncated instead of refused write; a secret stored in a tracked file; hook output that is no longer valid JSON.
- findings (CLI, library): protocol, file, encoding, state. Risks: a real finding dropped by a whitespace difference; a read outside the project root; a repeat that is not recognised after lines moved; older reports without a quote no longer routing.
- docs: file. Risks: an `sl` call in prose that does not exist; removed older rules.
- reviewer eval (CLI, data pipeline): numeric, state, file, protocol. Risks: a division by zero on an empty pool; variant names reaching the grader; results written into the repository; a test that starts a paid model run.

## Coordinator steps after the last task

1. Test layers once: `sl run_tests --full`, then `fleet run --layer headless`, `--layer tui` and `--layer evals` (the change touches `hooks/session-start`, `agents/**`, `skills/**` and `commands/**`).
2. Live proof of section 4: build a set of 3 of this repository's own merged pull requests with `make-case`, run `reviewer_eval_cli.py run` with the default variant, keep the table for the closing report. A failure here is a finding for a fixer.
3. Final review, then ship: patch bump with `scripts/bump-version.sh`, pull request, merge.

## Self-review

- Coverage: sections 1-4 map to BG1-BG2, CR1-CR4 and FD3, FD1-FD4, RE1-RE3; DOC1 carries the coordinator-facing text of 1-3.
- Graph: every edge is a test that runs the producer's code (BG2, CR2, CR3, FD3, RE2, RE3) or a doc-contract test that needs the described `sl` call to exist (FD4, DOC1). No two tasks own one file.
- Names: `corrections.section`, `finding_check.verify`, `finding_check.fingerprint`, `budget.gate`, `fleet_report.parse` and the `reviewer_eval*` functions are written the same in every Consumes and Produces line.
