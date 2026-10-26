---
description: Switch this project to the AI orchestrator: superlite plans, builds and decides on its own.
argument-hint: ""
---

Run `sl orchestrator set ai`, then `sl orchestrator status`, and confirm in one line. While planning, the AI orchestrator asks one batch of major or uncertain decisions (minor and medium become rulings); after the first dispatch it stops only for destructive, outward-facing (push, merge, publish) or security-sensitive actions.
