---
name: subagent-driven-development
description: Use when executing a superlite plan that has a %% taskgraph. Runs a ready-queue scheduler over an idle agent pool.
---

# Subagent-Driven Development

You are the coordinator: you decide, dispatch and rule; scripts do what has a definite answer; agents write, review and fix.

Shorthand: `SUPERLITE` = plugin root, two levels above this skill's "Base directory for this skill: ..." path (`cygpath -u` it first). `SL="$SUPERLITE/skills/subagent-driven-development/scripts/sl"`; run it as `"$SL" ...`. `PLAN` = the plan file; pass `--plan $PLAN` everywhere. Exit 3 (no Python): `incident add`.

**You never edit code or run raw `pytest`; fixes go to fixer agents: tiers, escalation and contract in `fixing.md`. Never pass `model`.**

**Rulings, not stalls.** Decide conflicts and plan defects (spec binds); append `Ruling: <decision> - <why> - <cost if wrong>` to `.superlite/progress.md`.

## Setup

- Run root: a worktree (`"$SL" worktree ensure <topic>`; plan header `**Worktree:** none`: in place, branch `superlite/<topic>` off the default branch). Write the start SHA to `.superlite/progress.md` (`- start <sha>`). `commit_task` excludes `.superlite/` in `.git/info/exclude` itself. Resuming another session's run: `"$SL" orchestrator takeover --plan $PLAN` first.
- Wave 0 is not yours: `lint --stable` builds `.superlite/briefs/wave0.md` and prints `START FIRST:` with the Agent line for `superlite:implementer-haiku` (T0; `wave0 --plan $PLAN` reprints). Send it first; stub owners wait (`WAIT FOR T0:`) for `commit_task T0`. `Ruling: skip T0` or `**Wave0:** none` mutes it. Then `"$SL" plan_tools adapter --plan $PLAN`.

Fleet mode (user asks): `"$SL" fleet on` before the first dispatch, then `fleet.md`: every role a worker, never in-process; missing or BLOCKED: report BLOCKED.
- Names: each Agent call's `description` is what `"$SL" fleet name <Tn or role> --plan $PLAN` prints (`sl:<repo>-<worktree>-<id>`).
- Prime: `"$SL" build_prime --plan $PLAN` prints `hash size`, writes `.superlite/prime.md`: slim for sonnet.
- Incidents: a BLOCKED or NEEDS_CONTEXT report is `"$SL" incident add --agent coordinator --file <task file> --line 0 --context "BLOCKED Tn: <why>"` (`--file`, `--line`, `--context` required; `--kind` optional, `incident add --help` lists the kinds).
- MCP: agents inherit the session's MCP tools; a project MCP server is approved before dispatch (background agents prompt in the main session).
- Graphify: `"$SL" graphify_gate` prints JSON. `use` false: skip. Installed: `graphify update .`. `needs_install` and `allowed`: `uv tool install graphifyy`, `graphify extract . --code-only`. Only you run it.

## Planning check

Order: plan -> `"$SL" plan_tools prune --plan $PLAN` -> `"$SL" plan_tools lint --plan $PLAN --spec SPEC --stable` (lists STABLE and FIX tasks, writes `.superlite/stable.json`; prints `SEND BEFORE ANY PLAN EDIT:`, ends `DISPATCH NOW: T2 T4` or `none`) -> `dispatch` and start every task on that line this turn -> only then patch the FIX tasks -> re-lint -> dispatch the newly stable tasks -> repeat until lint passes.

Each dispatch round, run the `THEN LOG` line lint prints. `finish` checks it against `lint-log.jsonl`.

Lint `WARNING: TESTS: no test command resolves`: before the first dispatch run `"$SL" testcmd --propose`, then `--write` (or give the task `**Tests:** fast cmd=`).

Dispatched tasks are frozen: keep blocks byte-identical, else lint says `FROZEN:` (restore them). `MISSED TARGET:` warns: split or stub those tasks, or `Ruling: accept predicted <N> min - <why sequential> - <cost>`.

## The scheduling loop

```mermaid
flowchart TB
  N[dispatch] --> A{per ready task}
  A -- agent=ID --> M[task message]
  A -- poll IDS --> Q[relevance poll] --> M
  A -- fresh --> P[prime file] -- READY --> M
  M --> D[DONE reports] --> C[commit_task T.. --dispatch] --> A
  C -. background .-> PR[probe_run --commit]
  C -. both sides in .-> SM[pt_review contract seam]
```

Keep `.superlite/pool.json` (agents: id, tasks, files, context_k, idle_min, busy, current, tier = the line's, T0 haiku). Sending a task sets `busy: true`, `current: Tn` (batch `Tn,Tm`); `commit_task` frees members singly. Never edit pool.json by hand (zsh: quote loop vars; `status`, `path` reserved): `"$SL" pool` (`add`, `busy`, `free`, `list`, `sync`) and `dispatch` (syncs first: real `context_k`, `idle_min` from transcripts, `busy` cleared by a newer stop record) keep it.

1. `"$SL" dispatch --plan $PLAN --cap 10` prints per ready task, longest first: `Tn agent=ID tier=T`, `Tn poll ID,ID tier=T` or `Tn fresh tier=T agent=TYPE`; `Tn` may be a batch `Tn,Tm` (same tier, never critical-path; `--batch 1` turns it off). Tiers come from `config/routing.json` via lint, never overridden; a task goes only to an agent of its tier. Start all.
2. Per line: `agent=ID`: SendMessage the task to that agent. `poll ID,ID`: one SendMessage to each listed agent, "Relevance 0-10 for Tn (files, consumes)? Reply `score: N - reason`"; next turn the highest wins (tie: smallest `context_k`). `fresh tier=T agent=TYPE`: Agent TYPE with the message "Read <abs>/.superlite/prime.md, then reply READY" (haiku: `prime-haiku.md` from `build_prime --tier haiku`), same text per tier all run; never paste the prime; send the task only after its reply `READY`, then register it: `"$SL" pool add ID --tier T --current Tn`. Idle agent: `"$SL" pool busy ID Tn[,Tm]`; `pool add --current Tn,Tm` for a batch. `evict=ID` (stderr): drop it. `dispatch` never offers a busy agent or one past 3 tasks, 80k context, 50 idle minutes. Stderr `unstable=Tn <reason>; rerun sl lint --stable`: patch and re-lint; a FIX task held only by `depends on unstable <ids>` is offered once those ids are committed.
3. Task message (batch: one message, in order): heading, `SUPERLITE=<abs plugin root>`, `PLAN=<abs plan path>`, `ROOT=<abs run root>`, "your task text: `<abs sl> task Tn --plan PLAN`", Owns and files not to touch, Review Focus categories, rulings and interface names (a fake returns the producer's `e.g.` examples), the literal absolute `sl` path (no `$SL`), verify command (batch: one per member, each with its own `--task Tn` and PATHS, run on its own: `<abs sl> run_tests --fast PATHS --task Tn --background`, then run the printed `wait:` line in the foreground (never as a background command) and end the turn only after it reports), "before DONE remove what you created (simulators, build folders, temp files)", and for haiku the full task block instead of `task` (mini prime cuts lines), and "reply in at most 200 words: status DONE / DONE_WITH_CONCERNS / NEEDS_CONTEXT / BLOCKED, files, test result, `Red run:` line, open questions".
4. Record all DONE tasks in one call (hidden checkpoints; `sl autocommit on`: real): `"$SL" commit_task T3 T5 --plan $PLAN --dispatch` commits each task's files, prints `Tn <sha>`, `Tn FAILED` or `Tn: no change since its last checkpoint <sha>` (one task: the SHA), then `next:`/dispatch lines. FAILED (unowned files, syntax/import problems): send it back. DONE_WITH_CONCERNS: fix correctness ones first. NEEDS_CONTEXT: answer. BLOCKED: log it; a fixer a tier up takes it. A haiku miss (NEEDS_CONTEXT, BLOCKED, red): `"$SL" routing miss --task Tn --plan $PLAN`; not retried on Haiku. Act on `next:` lines. Human step: `"$SL" hold Tn --reason R`, `--release Tn`. A task that must touch another task's file: `commit_task Tn --also F --ruling "..."`; it then owns it for the run (several tasks: the first).
5. After a commit, `commit_task` has started `probe_run --commit` and, for each seam with both sides committed, `pt_review contract --seam` in the background. A pass logs `verified`; a mismatch is an incident (`fixing.md`).
6. Probe failures: `incident hotspots --files <task files>` first; open failures go to fixers (`fixing.md`); ruled false positive: `probe_run --dismiss ID`. `commit_task` accepts generated `tests/regression/` files from any task.

## Reviews (D16)

```mermaid
flowchart LR
  C[commit] --> T{seam, Complexity >= 5, Review Focus risk, open incident?}
  T -- yes --> R1[package-reviewer on that task]
  T -- no --> W[wait for the package] --> R2[one package-reviewer, all its diffs]
  R1 & R2 --> X[fixes + regression tests] --> K[commit_task again]
```

- Matching tasks get `superlite:package-reviewer` on commit; others one per package (last: per task). Fleet: `fleet spawn --for-review Tn` or `--package X`; `--for-dispatch` prints `review: Tn`.
- Brief: absolute `sl` path, commit or range, spec slice, `PLAN`, files, `incident hotspots` output, adapter path. It reviews, fixes with regression tests, logs; never commits.

## Coordinator batching

- One message per turn: all dispatches, reviews, background starts.
- Every test run is `run_tests ... --background`; wait in Final review 2 and 5.
- `run_tests` and `dispatch` refuse below 20 GB free (warn below 50) and remove trees of committed tasks and stopped workers; refused: `"$SL" trees clean`.

## Final review

```mermaid
flowchart TB
  G[all tasks reviewed + committed] --> ST[run_tests --full, wait]
  ST --> PK[packet from its summary]
  PK --> FR[fresh final-reviewer, findings only]
  FR --> V{findings, suite red?}
  V -- yes --> FX[fixers by tier] --> ST2[run_tests --background]
  V -- no --> W[run_tests --wait] --> Z[freeze]
```

1. Gate: all tasks and reviews committed, all seams `verified`.
2. `run_tests --full --background`, then its `wait:` line. Then build the packet: `"$SL" plan_tools packet --plan $PLAN --base <start-sha>` (a run without a plan: `"$SL" plan_tools packet --inline --spec <spec.md> --base <start-sha>`, no `--plan`; later rounds add `--previous <rounds.md>`) uses that run's summary, probe results and incidents, and writes `.superlite/review-packet.md`. UI screenshots (`.png`, `.jpg`, `.jpeg`) go in `.superlite/render/` first: the packet's `## Render evidence` section lists them for the reviewer. Write `.superlite/render/index.md` too, one `- <file>: <caption>` line per current screenshot: the packet then lists only those, so superseded pre-fix shots drop out.
3. Start a fresh final reviewer then. Fleet on (inline builds too): `"$SL" fleet spawn --role final-reviewer --plan $PLAN`, then `"$SL" fleet send Wn --brief <abs>/.superlite/review-packet.md --label FR<round> --plan $PLAN`. Fleet off: Agent `superlite:final-reviewer`, brief = the absolute `sl` path and "read .superlite/review-packet.md", nothing more. The tree stays frozen. It answers once: `Verdict: APPROVED` or `CHANGES_REQUESTED` plus `file:line - problem - fix - tier N` lines. No `Checked:` block (fast path too) is no review: start a fresh one. Full review asked: add `--full` to the `fleet send` (Agent: `Full review` in the brief).
4. Red suite lines are findings. Send all to fixers (`fixing.md`); then `commit_task Tn` per owning task (`--claim F --ruling TEXT` for files outside Owns) and one more `run_tests --background`.
5. Before the final commit, `"$SL" run_tests --wait`; green means freeze.

## Measure and budget

`lint` and `dispatch` print `budget:` lines (`**Budget-usd:**`: cap). At `WARN` finish in-flight work; at `OVER CAP` no extra review rounds, no fix rounds beyond the first, then `commit_task` and finish.

## Freeze, rulings, finish

Green: freeze. Archive `incidents.jsonl`, `progress.md` by the plan. Run `"$SL" fleet stop --all` (no-op off fleet), `"$SL" trees clean` (also orphaned Xcode DerivedData; `--module-cache-hours 24` prunes module cache), delete what you created (simulators, build folders, `-derivedDataPath` folders in your session scratchpad), then `"$SL" finish --plan $PLAN`; print its rulings in your closing message under "Rulings I made" with cost, and its last block (report summary) before any merge or PR option; full: `<plan>.build-report.md`. Then invoke `superlite:finishing-a-development-branch`.

## Stop conditions

Ask only for an irreversible, destructive, security-sensitive or outward step (merge, push, publish), or a plan so broken all paths are guesses.

**AI orchestrator** (`sl orchestrator status`; also user away, "decide yourself"): never end your turn to wait. Take the safe path: defer outward or destructive actions, read a broken plan conservatively, record the ruling, list what you deferred. **Human orchestrator**: nothing is built, dispatched or written but the review plan before the human's approving reply; ask in plain text, end the turn, then `"$SL" orchestrator approve --review PATH` and the machine plan; `lint --stable`, `dispatch`, `wave0`, `build_prime` refuse before (`orchestrator.md`).

## Red flags

| Thought or act | Do instead |
|---|---|
| Pasting the prime or a task before READY | Send "Read <abs>/.superlite/prime.md, then reply READY"; wait |
| Work to a busy agent, or "after T3" | `dispatch` |
| Editing code, raw `pytest`, or a foreground suite | Fixer agent; `run_tests --background` |
| Committing by hand | `commit_task T3 T5 --dispatch` |
| Killing by image name | By PID only |
