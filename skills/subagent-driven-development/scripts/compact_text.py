"""Texts for the automatic compaction of a superlite session (Claude Code PreCompact and SessionStart(compact) hooks).

    compact_text.instructions() -> str          what the compaction summary keeps and drops
    compact_text.continuation(sl_dir) -> str    what the session reads after compaction: how to go on, and the run state

The run state is what `sl status` prints for sl_dir, plus `sl backlog status` while a batch is not shipped; each line is
cut at 300 characters and the block at 3,000. It is read in this process, never changed. If it raises or takes longer
than 5 seconds, the text names the command instead, so the session is always told how to go on.

CLI: compact_text.py instructions | continuation <sl_dir>. Stdlib only.
"""
# Complexity notation:
#   s = lines of the run state, B = bytes of the state files read
from __future__ import annotations

import sys  # O(1)
import threading  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)

__all__ = ["instructions", "continuation"]

_LINE_MAX = 300
_STATE_MAX = 3000
_STATE_LIMIT_S = 5.0

_INSTRUCTIONS = (
    "This session orchestrates a superlite run. The run state (plan, tasks, backlog, test results) is on disk and is "
    "shown again after compaction: do not restate it.\n"
    "Keep, verbatim where short:\n"
    "1. The user's goal and every standing instruction, ruling or correction they gave, newest last.\n"
    "2. Decisions made in this session with their reason, and the options ruled out.\n"
    "3. In flight now: background commands, agents, workers and leads, what each will return, and any question "
    "waiting on the user.\n"
    "4. The exact next step.\n"
    "5. The paths of files that hold state, not their contents.\n"
    "Drop: tool output, file contents, diffs, test logs, and finished tasks beyond one line each."
)

_GO_ON = (
    "Load no skill the next step does not need. Then continue the run from its next step without asking for "
    "confirmation; ask only when a major decision is open. If a background command, worker or lead is still running, "
    "wait for it; do not start it again."
)
_WITH_STATE = ("The context was compacted automatically; the conversation summary may be incomplete. "
               "Trust the run state below over the summary. ")
_NO_STATE = ("The context was compacted automatically; the conversation summary may be incomplete. "
             "Run `sl status` first (backlog mode: `sl backlog status`) and trust it over the summary. ")


def instructions() -> str:  # O(1)
    """Summary instructions for the compaction of an orchestrator session."""
    return _INSTRUCTIONS  # O(1)


def _backlog_lines(sd: Path) -> list:  # O(B)
    """`sl backlog status` lines while sd holds a backlog with a batch that is not shipped, else none."""
    if not (sd / "backlog.json").is_file():  # O(1)
        return []  # O(1)
    import backlog_state  # O(1)
    data = backlog_state.load(sd / "backlog.json")  # O(B)
    batches = data.get("batches") or []  # O(1)
    if not any(isinstance(b, dict) and b.get("state") != "shipped" for b in batches):  # O(batches)
        return []  # O(1)
    return list(backlog_state.status_lines(data))  # O(batches)


def _state_lines(sd: Path) -> list:  # O(B)
    import orchestrator  # O(1)
    import status  # O(1)
    return list(status.overview(sd, orchestrator.plan_file(sd, None))) + _backlog_lines(sd)  # O(B)


def _state(sd: Path) -> str:  # O(B)
    """The capped run state, or "" when it cannot be read within the limit."""
    box = {}  # O(1)

    def work():  # O(B)
        try:  # O(1)
            box["lines"] = _state_lines(sd)  # O(B)
        except BaseException:  # a corrupt state file or a SystemExit of a tool: no state, never a traceback | O(1)
            box["lines"] = None  # O(1)

    t = threading.Thread(target=work, daemon=True)  # O(1)
    t.start()  # O(1)
    t.join(_STATE_LIMIT_S)  # O(limit)
    lines = box.get("lines")  # O(1)
    if not lines:  # O(1)
        return ""  # O(1)
    out, used = [], 0  # O(1)
    for ln in lines:  # O(s) iterations
        ln = " ".join("".join(c for c in str(ln) if c >= " " or c.isspace()).split())  # one line, no control characters: the hook puts it into a JSON string | O(len)
        if len(ln) > _LINE_MAX:  # O(1)
            ln = ln[:_LINE_MAX - 3] + "..."  # O(1)
        if used + len(ln) + 1 > _STATE_MAX:  # O(1)
            break  # O(1)
        out.append(ln)  # O(1)
        used += len(ln) + 1  # O(1)
    return "\n".join(out)  # O(s)


def continuation(sl_dir: str) -> str:  # O(B)
    """What a session with a run reads after compaction: how to go on, then the run state when it could be read."""
    state = _state(Path(sl_dir))  # O(B)
    if not state:  # O(1)
        return _NO_STATE + _GO_ON  # O(1)
    return _WITH_STATE + _GO_ON + "\n\nRun state:\n" + state  # O(s)


if __name__ == "__main__":  # O(B) CLI for hooks
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""  # O(1)
    if cmd == "instructions":  # O(1)
        print(instructions(), flush=True)  # O(1)
        sys.exit(0)  # O(1)
    if cmd == "continuation" and len(sys.argv) > 2:  # O(1)
        print(continuation(sys.argv[2]), flush=True)  # O(B)
        sys.stdout.flush()  # O(1)
        import os  # O(1)
        os._exit(0)  # a state read still running past the limit must not hold the hook | O(1)
    sys.exit(2)  # O(1) unknown command
