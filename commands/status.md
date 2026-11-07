---
description: Show the superlite run state: mode, orchestrator, plan approval, task progress, held tasks, budget.
argument-hint: ""
---

Show the current superlite state in under 15 lines. Run `sl orchestrator status` (mode and whether the plan is approved), `sl metrics --dir .superlite` (task progress and cost so far) and, if a plan exists, `sl budget --plan <plan>` and `sl hold --plan <plan>` (one `held Tn: reason` line per held task, or `held: none`). Report: orchestrator, approved or not, tasks done/running/waiting/held, each held task with its id and reason, cost and time so far, and the next step. Change nothing.
