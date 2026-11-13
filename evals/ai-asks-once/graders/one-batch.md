---
type: llm
criteria: First list, one per line, each question in the final message that asks the user to decide a design, scope or trade-off item, then count the lines. A numbered or top-level item is one line, together with its options, sub-questions and default, also when it is a bold heading with bullet options under it. Never list Ruling lines, stated assumptions, the defaults it will use when the user does not answer, an offer to continue, or a request to enable or allow a tool, command, Bash or permission (requests to enable a denied tool or permission are not counted). Pass when the count is four or fewer, zero included, since whether decisions are raised is graded elsewhere; fail only when it is five or more.
---

One batch of at most four decisions, as the AI orchestrator asks while planning. A request to enable Bash or another denied tool is never a decision.
