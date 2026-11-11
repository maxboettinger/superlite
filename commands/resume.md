---
description: Resume an interrupted superlite build from the last committed, tested wave.
argument-hint: "[plan path]"
---

Resume a superlite build. Arguments: $ARGUMENTS
1. Find the plan (the argument, else the newest in docs/superpowers/plans, else docs/plans), then run `sl orchestrator resume --plan <plan>` first: per task it shows the checkpoint, files edited after it, uncommitted Owns files and its last test run, with keep/drop hints to act on. `sl status` shows the run state. Read `.superlite/` state and `git log` to see which tasks are committed and tested.
2. Load `superlite:subagent-driven-development` and continue from the ready queue. Never redo a committed, passing task; re-run only tasks that were running or untested.
3. Report in two lines what was already done and what will run now. Respect the orchestrator choice and the human approval gate.
