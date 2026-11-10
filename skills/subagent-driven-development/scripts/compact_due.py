"""Hint that a session's context grew past the point where automatic compaction should already have run.

    compact_due.context_tokens(transcript_path) -> int | None
    compact_due.is_due(sl_dir, tokens, sid=None, threshold=500000) -> bool
    compact_due.nudge_line(tokens) -> str
    compact_due.mark(sl_dir, sid=None) -> None

With an auto-compact window set (`sl setup` offers 400,000 tokens) Claude Code compacts by itself and the context never
reaches the threshold. A main-conversation request above it means no such window is active, so the agent is asked once
per session to tell the user how to set one. The size is the input side of the last main-conversation request in the
transcript (input, cache read and cache write tokens), read from the file's last 256 KB only.

CLI (hooks/compact-nudge): compact_due.py <sl_dir>, the hook's JSON on stdin (session_id, transcript_path). Prints the
hint and exits 0 when due, else exits 1. Stdlib only.
"""
# Complexity notation:
#   T = bytes of the transcript tail read (at most 256 KB), L = lines in it
from __future__ import annotations

import json  # O(1)
import os  # O(1)
from pathlib import Path  # O(1)

__all__ = ["context_tokens", "is_due", "nudge_line", "mark"]

_THRESHOLD = 500_000
_TAIL_BYTES = 262_144
_INPUT_FIELDS = ("input_tokens", "cache_read_input_tokens", "cache_creation_input_tokens")


def context_tokens(transcript_path: str) -> int | None:  # O(T)
    """Input-side tokens of the last main-conversation request in the transcript's tail, or None when none is found."""
    if not transcript_path:  # O(1)
        return None  # O(1)
    try:  # O(1)
        with open(os.path.expanduser(transcript_path), "rb") as f:  # O(1)
            size = f.seek(0, os.SEEK_END)  # O(1)
            start = max(0, size - _TAIL_BYTES)  # O(1)
            f.seek(start)  # O(1)
            data = f.read()  # O(T)
    except OSError:  # O(1)
        return None  # O(1)
    lines = data.split(b"\n")  # O(T)
    if start > 0:  # the first line of a tail is cut somewhere in the middle | O(1)
        lines = lines[1:]  # O(L)
    for raw in reversed(lines):  # O(L) iterations
        if b'"usage"' not in raw:  # O(len)
            continue  # O(1)
        try:  # O(1)
            e = json.loads(raw.decode("utf-8", errors="replace"))  # O(len)
        except ValueError:  # O(1)
            continue  # O(1)
        if not isinstance(e, dict) or e.get("isSidechain"):  # a subagent's request is not this context | O(1)
            continue  # O(1)
        msg = e.get("message")  # O(1)
        usage = msg.get("usage") if isinstance(msg, dict) else None  # O(1)
        if not isinstance(usage, dict):  # O(1)
            continue  # O(1)
        vals = [usage.get(k) for k in _INPUT_FIELDS]  # O(1)
        if not any(isinstance(v, int) and not isinstance(v, bool) for v in vals):  # O(1)
            continue  # O(1)
        return sum(v for v in vals if isinstance(v, int) and not isinstance(v, bool))  # O(1)
    return None  # O(1)


def _marker_name(sid: str | None) -> str:  # O(|sid|)
    safe = "".join(c for c in (sid or "") if c.isalnum() or c in "-_")  # O(|sid|)
    return "compact-hint." + safe if safe else "compact-hint"  # O(1)


def is_due(sl_dir: str, tokens: int | None, sid: str | None = None, threshold: int = _THRESHOLD) -> bool:  # O(1)
    """True when the context is above the threshold and this session was not told yet."""
    if tokens is None or tokens <= threshold:  # O(1)
        return False  # O(1)
    return not (Path(sl_dir) / _marker_name(sid)).exists()  # O(1)


def mark(sl_dir: str, sid: str | None = None) -> None:  # O(1)
    """Remember that this session was told, so the hint shows once per session."""
    try:  # O(1)
        (Path(sl_dir) / _marker_name(sid)).write_text("", encoding="utf-8")  # O(1)
    except OSError:  # O(1)
        pass  # O(1)


def nudge_line(tokens: int) -> str:  # O(1)
    """Host-neutral line asking the agent to tell the user how to turn on automatic compaction."""
    return (  # O(1)
        f"Session context is at about {tokens // 1000}k tokens and no auto-compact window is active below that, so "
        "this session compacts only near the model's limit. Tell the user once, in one line: run `/autocompact 400k` "
        "(or `sl setup`, which offers the same as a setting) and superlite sessions compact and continue by "
        "themselves. Then continue the current work."
    )


if __name__ == "__main__":  # O(T) CLI for hooks
    import sys  # O(1)

    sl = sys.argv[1] if len(sys.argv) > 1 else ""  # O(1)
    if not sl:  # O(1)
        sys.exit(1)  # O(1)
    try:  # O(1)
        inp = json.loads(sys.stdin.read() or "{}")  # O(input)
    except ValueError:  # O(1)
        inp = {}  # O(1)
    if not isinstance(inp, dict):  # O(1)
        inp = {}  # O(1)
    sid = inp.get("session_id") if isinstance(inp.get("session_id"), str) else None  # O(1)
    path = inp.get("transcript_path") if isinstance(inp.get("transcript_path"), str) else ""  # O(1)
    if (Path(sl) / _marker_name(sid)).exists():  # told already: do not read the transcript | O(1)
        sys.exit(1)  # O(1)
    tokens = context_tokens(path)  # O(T)
    if is_due(sl, tokens, sid):  # O(1)
        print(nudge_line(tokens), flush=True)  # O(1)
        mark(sl, sid)  # O(1)
        sys.exit(0)  # O(1)
    sys.exit(1)  # O(1) not due
