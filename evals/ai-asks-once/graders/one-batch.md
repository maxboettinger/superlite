---
type: llm
criteria: Count the questions in the final message that ask the user to decide a design, scope or trade-off item. A numbered or top-level item counts once, together with its options, sub-questions and default. Never count Ruling lines, stated assumptions, an offer to continue, or a request to enable or allow a tool, command, Bash or permission (requests to enable a denied tool or permission are not counted). Pass when the count is four or fewer, zero included, since whether decisions are raised is graded elsewhere; fail only when it is five or more.
---

One batch of at most four decisions, as the AI orchestrator asks while planning. A request to enable Bash or another denied tool is never a decision.
