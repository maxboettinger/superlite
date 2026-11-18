#!/usr/bin/env python3
"""Finding check: verify the line a reviewer finding quotes, fingerprint it, and keep a per-run ledger.

Library: normalize(s), fingerprint(file, quote, problem=""), verify(root, finding, window=10) -> {state, line, reason},
LEDGER, load(sd), append(sd, row), next_round(rows), prior(rows, fp). Stdlib only.
"""
# Complexity notation:
#   n = characters in the quote, L = lines in the file, s = bytes of the file, r = ledger rows
import hashlib  # O(1)
import json  # O(1)
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
from incident import append as _locked_append  # locked append with fsync | O(1)

LEDGER = "findings.jsonl"  # O(1)
MAX_BYTES = 2 * 1024 * 1024  # O(1)
MIN_QUOTE = 6  # normalized characters; shorter quotes prove nothing | O(1)
_WS = re.compile(r"\s+")  # O(1)


def normalize(s):  # O(n)
    """Collapse whitespace runs to one space; strip surrounding whitespace and backticks."""
    return _WS.sub(" ", s or "").strip().strip("`").strip()  # O(n)


def fingerprint(file, quote, problem=""):  # O(n)
    """Ten hex characters over the file and the normalized quote (the problem text when the quote is empty)."""
    q = normalize(quote)  # O(n)
    key = file + "\n" + q if q else file + "\n?" + normalize(problem)  # O(n)
    return hashlib.sha256(key.encode("utf-8")).hexdigest()[:10]  # O(n)


def _int(v):  # O(1)
    try:  # O(1)
        return int(v)  # O(1)
    except (TypeError, ValueError):  # O(1)
        return 0  # O(1)


def verify(root, finding, window=10):  # O(s) read + O(L n) scan
    """State verified (quote within `window` lines of the claimed line), moved (elsewhere) or unverified."""
    line = _int(finding.get("line"))  # O(1)

    def res(state, at, reason):  # O(1)
        return {"state": state, "line": at, "reason": reason}  # O(1)

    q = normalize(finding.get("quote") or "")  # O(n)
    if not q:  # O(1)
        return res("unverified", line, "no quote")  # O(1)
    if len(q) < MIN_QUOTE:  # O(1)
        return res("unverified", line, "quote too short")  # O(1)
    try:  # O(1)
        base = Path(root).resolve()  # O(1)
        target = (base / str(finding.get("file") or "")).resolve()  # O(1)
        target.relative_to(base)  # O(1)
    except (ValueError, OSError):  # O(1)
        return res("unverified", line, "outside root")  # O(1)
    try:  # O(1)
        if not target.is_file():  # O(1)
            return res("unverified", line, "file not found")  # O(1)
        if target.stat().st_size > MAX_BYTES:  # O(1)
            return res("unverified", line, "file too large")  # O(1)
        text = target.read_text(encoding="utf-8", errors="replace")  # O(s)
    except OSError:  # O(1)
        return res("unverified", line, "file not found")  # O(1)
    hits = [i for i, t in enumerate(text.splitlines(), 1) if q in normalize(t)]  # O(L n)
    if not hits:  # O(1)
        return res("unverified", line, "quote not in file")  # O(1)
    best = min(hits, key=lambda i: (abs(i - line), i))  # O(L)
    if abs(best - line) <= window:  # O(1)
        return res("verified", best, "")  # O(1)
    return res("moved", best, "quote found at line %d" % best)  # O(1)


def load(sd):  # O(r)
    """Ledger rows of a run folder; a missing file or an unparsable line is skipped."""
    rows = []  # O(1)
    try:  # O(1)
        lines = (Path(sd) / LEDGER).read_text(encoding="utf-8", errors="replace").splitlines()  # O(r)
    except OSError:  # O(1)
        return rows  # O(1)
    for ln in lines:  # O(r)
        try:  # O(1)
            row = json.loads(ln)  # O(1)
        except ValueError:  # O(1)
            continue  # O(1)
        if isinstance(row, dict):  # O(1)
            rows.append(row)  # O(1)
    return rows  # O(1)


def append(sd, row):  # O(1) locked append
    _locked_append(Path(sd) / LEDGER, [row])  # O(1)


def next_round(rows):  # O(r)
    return max([_int(r.get("round")) for r in rows] + [0]) + 1  # O(r)


def prior(rows, fp):  # O(r)
    """The newest routed or dismissed row with this fingerprint, else None."""
    for r in reversed(rows):  # O(r)
        if r.get("fp") == fp and r.get("state") in ("routed", "dismissed"):  # O(1)
            return r  # O(1)
    return None  # O(1)
