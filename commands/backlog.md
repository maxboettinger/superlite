---
description: Work a whole issue backlog: batch leads plan, build, review and ship each batch while you keep only the backlog and the decisions.
argument-hint: ""
---

You are main (AI orchestrator, lean context). `SL` = `<plugin root>/skills/subagent-driven-development/scripts/sl`. The rules live in `skills/subagent-driven-development/backlog.md`; read its `## Main` section once. Never read issue bodies, lead transcripts, panes or reports: the backlog file and the wait lines are your only view.

1. Run `"$SL" backlog status` first, and again after any compaction. It shows every batch with its state and tells you the next step.
2. No batches yet: run `"$SL" backlog plan` as a background command (a triage worker proposes file-disjoint batches); you are notified when it ends.
3. Run `"$SL" backlog decide --print`. It prints the open questions. Ask them with AskUserQuestion, at most 4 per call, your recommendation first. Write the answers to `.superlite/backlog-answers.json` as `{"answers": {question: answer}}` and run `"$SL" backlog decide --file .superlite/backlog-answers.json`. The last question is the one ship approval.
4. Run `"$SL" backlog start` (a worktree and a lead per startable batch, capped at 2). Herdr missing or exit 3 means BLOCKED: stop and say so, never fall back to in-process agents.
5. Run `"$SL" backlog wait` as a background command. It prints one line per lead that ends. Per line: `needs_decision`: read the questions it names, ask them with AskUserQuestion, write the answers file, run `"$SL" backlog answer B --file F`; `shipped`: nothing to do, run `start` again for newly startable batches; `parked`: note the reason for the final report; BLOCKED: report it and stop that batch.
6. Repeat 4 and 5 until `"$SL" backlog status` shows every batch shipped or parked. Then give the closing report: shipped PRs, parked batches with reasons, outside issues.
