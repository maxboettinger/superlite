---
description: Turn superlite's hidden checkpoints into real commits on the current branch (one per task), after you confirm.
---

superlite does not commit by default: each task is a hidden checkpoint under `refs/superlite/*` and the work is uncommitted in the tree.
1. Run `"$SL" autocommit status` (`SL` = `<superlite skill dir>/subagent-driven-development/scripts/sl`) and show the user the checkpoint list (task, short SHA, title, file count) and the current branch.
2. Ask for a yes. Do not run anything else until it comes.
3. On yes, run `"$SL" autocommit apply` and print its output. It makes one commit per task in order with the same titles and no trailer, then deletes the checkpoints. Changes outside the run stay in the tree uncommitted and the output names them; if it refuses (HEAD moved or a checkpointed file was edited again), print why and stop; the user can run `git add -A && git commit` instead.
`"$SL" autocommit clean` discards the checkpoints; `"$SL" autocommit on` makes later runs commit each task on the branch.
