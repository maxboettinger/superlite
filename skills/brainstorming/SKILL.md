---
name: brainstorming
description: Use when the user asks to build a feature or component, add functionality, or change behavior, before any implementation code is written.
---

# Brainstorming

Turn a request into an approved design with as little ceremony as the request allows. Intent comes first: know what the user wants to accomplish and what success looks like before you pick an approach. Who orchestrates is chosen first: a human orchestrator approves the plan once, before it runs; an AI orchestrator asks only major decisions and important uncertainties, once, while planning. After that only destructive, outward-facing (push, merge, publish) or security-sensitive actions stop you.

## 1. Size the request, in one line

Announce it: "This looks bounded, so I'll ask one batch of questions and show a short design here." The user can override.

- **Trivial** (a few tool calls: a typo, a rename, a one-line fix): do it and exit this skill. With a human orchestrator nothing is built, not even a small request, before the human approves a review plan (a one-page form for small ones).
- **Bounded** (a change to a flow that already exists in the repo): short in-chat design, one approval.
- **Architectural** (a new project or subsystem, or changes to interfaces others depend on): one combined design and plan doc, one approval.
- **Spike** ("can we...", "is it possible...", throwaway is fine): say what you will try in 2 sentences and try it. The output is an answer, not code you keep.

Hidden complexity found mid-task upgrades the size: say so and step up. A request with several independent subsystems: say so first and brainstorm only the first.

## 2. Explore and ask, once

Read the relevant code and recent commits first (broad sweeps: an Explore agent, model haiku, effort low). Never ask what the repo or the request already answers. `sl` below is `<skill-dir>/../subagent-driven-development/scripts/sl`.

**Coverage pass** (architectural work, before any question): Read `coverage.md` in this skill's folder and follow it. It gives each decision category one `## Coverage` row: settled, ruled, n/a, spike or open. All 14 rows, none merged or dropped: scope and success criteria; domain and data model; persistence and migration; interfaces and contracts; UI states; concurrency and state ownership; error handling and recovery; security and privacy (untrusted input); performance and limits (sizes, timeouts); observability; testing strategy; compatibility; rollout (release order, rollback); research unknowns. A ruled row's basis is the decision itself (a number, a step), not "none needed". Research unknowns become spike tasks, never questions; the open rows are the questions. `**Coverage:** off` in the spec, or from the user, skips the pass.

Run `sl orchestrator status` first. If purpose, constraints or success criteria are still missing, ask them in ONE `AskUserQuestion` call (no question tool: one plain-text message, same cap, nothing asked outside its numbered questions): up to 4 questions, multiple choice where possible, your recommended option first. For architectural work, include the plan `detail` choice in the same batch (AI orchestrator: a `Ruling:` line, not a question): `contracts`, `tests` (the default) or `full` (recommend it when the core is algorithmic or risky). When the status names no orchestrator, take it from the request, in a headless run AI with a `Ruling:`, else as one single-choice question in that same call, options `Human orchestrator: I approve the plan before it runs` and `AI orchestrator: asks only major questions while planning, then hands off` (details in `../subagent-driven-development/orchestrator.md`); then record it: `sl orchestrator set human|ai`. Never one question per message; bounded work gets at most one batch. Architectural work asks the open coverage rows in as few 4-question calls as possible, until none is open (plain text: 4 per message, no 5th, the rest after the reply). Nothing missing: ask nothing and restate your understanding in the design.

With an AI orchestrator (chosen, the user still present) the batch holds only **major** decisions (design, scope, a trade-off, anything destructive or outward-facing) and **uncertain** ones (you cannot name the right answer from the code, docs or the user's messages). Minor and medium choices are `Ruling:` lines, never questions. A second batch only when an answer opens a new major question, a coverage row is still open, or writing the plan surfaces one before the first dispatch. After the first dispatch the AI orchestrator does not ask.

## 3. Design

Write what you understood (the user's words apart from your assumptions), then the design: architecture, components, data flow, error handling and testing, as short as the size allows.

- **YAGNI.** Cut every feature the user did not ask for or the stated success criteria do not need.
- **Clear units.** One purpose each, a defined interface, testable alone; you can say what it does, how it is used and what it depends on. If using it means reading its internals, fix the boundary.
- **Fit the codebase.** Follow existing patterns. Fix existing code only where it blocks the work; no unrelated refactors.
- Name the approach you chose and, when a real alternative exists, why you rejected it, in one sentence. Do not present three approaches by default.

## 4. Approve once, then build

**Bounded:** present the design in chat and stop until the user says yes. Then run `<skill-dir>/../subagent-driven-development/scripts/sl worktree ensure <topic>` and work in the folder it prints. Then implement with `superlite:test-driven-development`. No spec file, no plan doc.

**Architectural:**

1. With an AI orchestrator write ONE doc, `<plans>/YYYY-MM-DD-<topic>.md` (`<plans>` is `docs/superpowers/plans/` when that folder exists, else `docs/plans/`; a location the user named wins): the design above (with the `## Coverage` table), then the plan half from `superlite:writing-plans`, appended. With a human orchestrator write the review plan instead (`<date>-<topic>.review.md`, template `../writing-plans/review-plan.md`); the machine plan comes after the yes. The doc is the first file of the change: run `sl worktree ensure <topic>` (with `--branch <name>` for a project with a branch rule) first and write it in the folder it prints, never into the shared main checkout (a plan header `**Worktree:** none` opts out).
2. Self-review inline for placeholders, contradictions, scope (one plan, or decompose?) and requirements that could be read two ways; fix them in place. No review loop, no subagent.
3. With a human orchestrator ask in plain text, not AskUserQuestion (the hook verifies the human's typed reply): the review plan's path, a five-line summary and "Reply approve to start, or tell me what to change"; END THE TURN and do nothing until the human replies. Only then run `sl orchestrator approve --review <path>` and write the machine plan from it with `superlite:writing-plans`: task-graph format for the orchestrator, never shown for approval, adding or changing nothing the human approved. With an AI orchestrator skip the approval. Run `sl graphify_gate`; on `needs_install: true` add the Graphify install opt-in (`uv tool install graphifyy`) to that same question. Never install without a yes.
4. On approval, invoke `superlite:subagent-driven-development` once, in this session (the one coordinator). It runs `lint --stable`, dispatches the stable tasks at once and patches only the FIX tasks.

Until approval only read-only exploration: no scaffolding, no dependency installs, no product code. Approval covers the doc as presented; if the user changes the design, revise and re-present once.

## AI orchestrator

With an AI orchestrator there is no review plan and no approval; questions follow step 2 (major and uncertain only, while planning). Unattended (the user says they are away, "decide yourself", the prompt pre-approves design and plan, or a headless run): skip the questions too. Choose the sensible default for each open question and open coverage row, the plan `detail` included (`full` for algorithmic or risky cores, otherwise `tests`), and record it in the doc (bounded work: in chat) as a line:

`Ruling: <decision> (because <reason>)`

Install Graphify only if `SUPERLITE_ALLOW_INSTALL=graphify` is set. Then go straight to implementation (bounded: `sl worktree ensure <topic>` first, work in the folder it prints) or to `superlite:subagent-driven-development` (architectural: the doc and everything after go in that worktree, step 4). The closing message lists all rulings. Destructive, outward-facing and security-sensitive actions are deferred, not waited on: take the safe path, record it, keep going.

## Red flags

| Thought | Reality |
|---|---|
| "Too simple to need a design" | Trivial is exempt. Bounded gets a short design and a yes. |
| "Let me ask one thing first" (again) | Batch everything into one `AskUserQuestion`. |
| "I'll start while they read the design" | The approval is the gate. Present, then stop. |
| "I know this kind of app, so it's bounded" | Bounded means the flow exists in this repo. A new project is architectural. |
| "Let me offer three approaches" | Recommend one. Mention an alternative only if it is real. |
| "They are away, so I will ask anyway" | Unattended means rule and record, not wait. |
