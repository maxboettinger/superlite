---
name: using-superlite
description: Use when starting any conversation - sizing requests, picking a superlite skill
---

First message, no mode named, not trivial: `/superlite:start`.

**Size.** Trivial: do it (human mode: after an approved review plan). Bounded (changes an existing flow): chat design, build. Architectural: one AskUserQuestion (≤4), one design+plan.

**Orchestrator**, in that batch: human (approves the plan first) or AI; "decide yourself", away, headless: AI (a Ruling). `sl orchestrator set human|ai`. AI asks only major or uncertain questions while planning, then halts only on destructive, outward, security-sensitive steps.

**Skills** (`superlite:`): build `brainstorming`, plan `writing-plans`, run `subagent-driven-development`, bug `systematic-debugging`, TDD `test-driven-development`, done `verification-before-completion`, finish `finishing-a-development-branch`.

**2+ tasks: `subagent-driven-development`,** loaded before the plan; no `general-purpose` builders or reviewers; inline only when small (a few files, one chain; say so). Non-trivial builds end with a fresh `superlite:final-reviewer` (review packet).

**Tools.** `bash <skill-dir>/../subagent-driven-development/scripts/sl <tool>`, never `python`. Graphify only if `sl graphify_gate` allows.

**Superlite broke, slow, unclear, repetitive?** `sl feedback add "<what, where, expected>"`; don't fix it mid-task.

**Off Claude Code:** `references/<harness>-tools.md` (tool names, running `agents/*.md`).
