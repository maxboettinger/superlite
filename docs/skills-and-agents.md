# Skills and agents

- `using-superlite` (injected at session start)
- `brainstorming`
- `writing-plans`
- `subagent-driven-development`
- `test-driven-development`
- `systematic-debugging`
- `verification-before-completion`
- `finishing-a-development-branch`

Agents (`agents/`):

- `implementer` (sonnet, medium): builds one task, then stays idle for reuse. With `fleet spawn --role implementer --brief <abs file>` and no prime it is a brief-only worker: the brief is the whole task, one turn, no pool entry.
- `implementer-haiku` (haiku, high): builds one `Kind: mechanical` task (fully specified, small, fast tests) exactly as written; stops rather than guesses.
- `package-reviewer` (sonnet, medium): reviews one committed task or one package, then fixes its own findings with regression tests; outside a run it commits its own fixes with a plain `git commit` of the files it changed; an out-of-scope fix stays an open finding.
- Roles without a tier: package-reviewer, final-reviewer and checker take no `--tier` (exit 2, `<role> takes no --tier (its agent file sets the model); ...`); `--tier` works for implementer, fixer, research and writer.
- `final-reviewer` (opus, high): a fresh one-turn reviewer that reads the review packet and any file or search its brief names (Read, Grep, Glob). It returns findings, each with a fix tier, and never fixes.
- `fixer-sonnet` (sonnet, medium): tier 1, cause known (including a fully specified change), fix confined to one module.
- `fixer-sonnet-high` (sonnet, high): tier 2, cause known but the fix spans modules or a seam, or a known probe class.
- `fixer-opus` (opus, high): tier 3, cause unknown (it diagnoses), or a lower tier failed twice.
- `checker` (sonnet, high): a one-turn worker that runs the built app, widget or extension once on its own simulator (or on macOS, or in a browser) and reports each listed check PASS, FAIL or NOT REACHABLE with screenshots; never fixes.
- `writer` (sonnet, medium): a one-turn worker that writes the one file its brief's `Output:` line names (Read, Grep, Glob, Write, Edit); no shell, and every other write is refused by permission.
