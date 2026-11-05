# Coverage pass (brainstorming step 2, architectural size)

Before the question batch, check the request against every decision category below, so gaps surface before the plan instead of mid-build. It is on for architectural work in every mode; bounded and trivial work skip it. To turn it off, put `**Coverage:** off` in the spec or plan header (with a one-line reason), also when the user asks for that.

1. Read the spec, the code and the user's messages first. Add the project's own categories from `.superlite/coverage.md` (the same two-column table as below) when it exists.
2. Write the table into the design doc under `## Coverage` (`sl coverage` prints it with every row open): one row per category, `| Category | State | Basis |`. States:
   - `settled`: the spec, the code or the user answers it; the basis says where (spec section, `file:line`, the user's words).
   - `ruled`: you assume a default; the basis is the decision, and the doc gets a `Ruling: <decision> (because <reason>; cost if wrong: <cost>)` line.
   - `n/a`: the category does not apply; the basis says why, in a few words.
   - `spike`: a research unknown nobody can answer yet; the basis names the spike task (`S1`). Spikes are small tasks at the front of the plan, never questions.
   - `open`: a question for the user; the basis is the question.
3. Ask the open rows with `AskUserQuestion`: 4 per call, recommended option first, as few calls as possible, repeated until no row is open; each answered row becomes `settled` (the answer) or `ruled`. Never ask what the spec or code already answers. AI orchestrator: only major or uncertain rows become questions; minor and medium ones are `ruled`.
4. Unattended (AI orchestrator with the user away or saying "decide yourself", or `AskUserQuestion` failing, as in a headless run): rule every open row with its sensible default; the closing report lists those rulings. A user who says they are present is attended: ask first, and rule only when the call fails.
5. Human orchestrator: the review plan carries the table under `## Coverage`, in plain words, with no row open; the machine plan copies it unchanged.
6. `plan_tools lint` reports `COVERAGE:` for a missing, open or malformed row (plan-level: it never blocks stable tasks) and a `NOTE:` for a plan without the section. `sl coverage check FILE` runs the same check on a review plan or spec.

## Categories

| Category | Asks about |
|---|---|
| Scope and success criteria | what is in, what is out (non-goals), how success is measured |
| Domain and data model | entities, fields, relations and invariants |
| Persistence and migration | storage, schema, and migration of existing data |
| Interfaces and contracts | calls to and from existing modules, APIs and formats that must not break |
| UI states | empty, loading, error, offline, permissions, accessibility, localisation |
| Concurrency and state ownership | who owns which state, parallel access, ordering |
| Error handling and recovery | failures, retries, partial writes, corrupt input, messages the user sees |
| Security and privacy | access control, secrets, personal data, untrusted input |
| Performance and limits | sizes, latency, quotas, timeouts |
| Observability | logs, metrics, how a failure gets noticed |
| Testing strategy | test levels, test data and fixtures |
| Compatibility | platforms, versions, backward compatibility |
| Rollout | release order, feature flags, rollback |
| Research unknowns | what nobody knows yet: a spike task, never a question |
