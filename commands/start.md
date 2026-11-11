---
description: Start a superlite session. Pick the mode (regular, MVP, feature, debug) and who orchestrates.
argument-hint: "[regular|mvp|feature|debug] [what you want]"
---

Start a superlite session. Arguments: $ARGUMENTS

1. If the first word of the arguments is `regular`, `mvp`, `feature` or `debug`, that is the mode; the rest is the request. Otherwise the mode is unset.
2. Ask what is still unset, in ONE AskUserQuestion (up to 2 questions):
   - Mode, if unset: Regular (size the request, then brainstorm, plan, build, review), MVP (smallest working version first), Feature (a change to existing code), Debug (find the cause, fix with a regression test).
   - Orchestrator, always unless the user already said: Human (you approve a plain-language review plan before anything is built) or AI (hands off). Then run `sl orchestrator set human|ai`: the one place the choice is set. It lives in `.superlite/orchestrator.json` of the session's run folder (`sl state where`); `lint --stable --plan` binds the session to the plan's worktree run and moves the file along, so a worktree run follows it. Never set it again.
   If AskUserQuestion is unavailable (tool error, headless, or the user said they are away), do not ask: mode Regular unless the arguments name one, orchestrator AI (`sl orchestrator set ai`, one `Ruling:` line), then step 4 at once, loading `superlite:brainstorming`. A new app or project is architectural, never trivial: no direct build.
   A project with a branch rule: `sl worktree ensure <topic> --branch <name>` (for example `feat/KEY-1-slug`); `--dir <name>` names the folder.
3. If there is no request text yet, ask for it in one line.
4. Load the skill for the mode and follow it:
   - Regular: `superlite:using-superlite` sizing, then `superlite:brainstorming`.
   - MVP: same as `/superlite:mvp`.
   - Feature: same as `/superlite:feature`.
   - Debug: same as `/superlite:debug`.

Menu by the "Project state" line in the session context (show only the options that fit):
- run in progress: Resume, Status, Start something new, Finish.
- existing code: Feature, Debug, Regular, MVP (a new app beside it), Review.
- empty folder: MVP (plan, clickable prototype to assess, then build), Regular.
Skip the menu for a clear one-line request you can size as trivial, or when the user already typed a `/superlite:` command.
