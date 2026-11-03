---
name: using-superlite
description: Use when starting any conversation - sizing requests, picking a superlite skill
---

First message, no mode named, not trivial: `/superlite:start`.

**Size.** Trivial: do it (human mode: after an approved review plan). A new app is never trivial. Bounded (existing flow): chat design, build. Architectural: one AskUserQuestion (≤4), one design+plan.

**Orchestrator**, in that batch: human (approves the plan first) or AI; "decide yourself", away, headless, AskUserQuestion unavailable: AI (a Ruling), `brainstorming`, no menu. `sl orchestrator set human|ai`. AI asks only major or uncertain questions, then halts only on destructive, outward or security steps.

**Skills** (`superlite:`): build `brainstorming`, plan `writing-plans`, run `subagent-driven-development`, bug `systematic-debugging`, TDD `test-driven-development`, done `verification-before-completion`, finish `finishing-a-development-branch`.

**2+ tasks: `subagent-driven-development`,** loaded before the plan; no `general-purpose` agents; inline only when small (few files, one chain; say so). Non-trivial builds end with a fresh `superlite:final-reviewer`.

**Tools.** `<skill-dir>/../subagent-driven-development/scripts/sl <tool>`, never `python`. Graphify only if `sl graphify_gate` allows.

**Superlite broke or unclear?** `sl feedback add "<what, where, expected>"`; don't fix mid-task.

**Off Claude Code:** `references/<harness>-tools.md` (tool names, running `agents/*.md`).
