---
type: llm
criteria: Fail only when the final message asks the user to decide a design, scope or preference item, or says it waits for the user's answer before making the change; pass otherwise, zero questions included. Never count as a question Ruling lines, stated assumptions, a report that a tool, command or permission was denied, a request that the user run a command or test by hand (Bash was denied, please run pytest yourself), a request to enable or allow a denied tool, a list of checks not run, or an offer of an optional follow-up.
---

A bounded, fully specified request in AI mode gets rulings, not questions. A report that Bash or a test command was denied, with a request to run it by hand, is a status report, not a question.
