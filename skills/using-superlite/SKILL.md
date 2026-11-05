---
name: using-superlite
description: Use when starting
---

First message, no mode, not trivial: `/superlite:start`.

**Size.** Trivial: do it (human mode: after an approved review plan). A new app is never trivial. Bounded (existing flow): chat design, build. Architectural: one AskUserQuestion (≤4), one design+plan.

**Orchestrator**, same batch: human (approves plan first) or AI; "decide yourself", away, headless, no AskUserQuestion: AI (a Ruling), `brainstorming`, no menu. `sl orchestrator set human|ai`. AI asks only major/uncertain questions; halts only on destructive/outward/security steps.

**Skills** (`superlite:`): build `brainstorming`, plan `writing-plans`, run `subagent-driven-development`, bug `systematic-debugging`, TDD `test-driven-development`, done `verification-before-completion`, finish `finishing-a-development-branch`.

**2+ tasks: `subagent-driven-development`,** loaded before the plan; no `general-purpose` agents; inline only if small (few files, one chain; say so). Non-trivial: end with fresh `superlite:final-reviewer`. Fleet: `sl fleet on` before the first dispatch; taskgraph implementers only; inline starts no worker.

**Tools.** `<skill-dir>/../subagent-driven-development/scripts/sl <tool>`, never `python`. Graphify only if `sl graphify_gate` allows.

**Superlite broke/unclear?** `sl feedback add --kind bug|slow|unclear|repeat|idea "<what, where, expected>"`; don't fix mid-task.

**Other harness:** `references/<harness>-tools.md`, `agents/*.md`.
