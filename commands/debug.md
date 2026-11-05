---
description: Find the root cause of a bug first, then fix it with a regression test.
argument-hint: "[the bug or failing test]"
---

Superlite debug mode. Problem: $ARGUMENTS

Before the first write run `<superlite skill dir>/subagent-driven-development/scripts/sl worktree ensure <topic>` and work in the folder it prints. A hook refuses edits in the main checkout once this flow starts; for a trivial change run `sl worktree inplace --reason "<why>"`. If the problem is empty, ask for it in one line (what fails, how to reproduce). Then load `superlite:systematic-debugging` and follow it: reproduce, find the root cause, write the failing regression test, fix, verify. Fix inline: you write the regression test and the fix yourself and commit them on the worktree's branch. Fix-only agents (`fixer-*`) run only inside a plan run, where `commit_task` has a task id to commit against. Use the project's own test command. Do not widen the change beyond the cause.
