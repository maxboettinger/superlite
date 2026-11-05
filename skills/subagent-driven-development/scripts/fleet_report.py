#!/usr/bin/env python3
"""Fleet worker reports: parse a worker's reply into one dict, and build the one-line brief message.

    fleet_report.parse(text, label="", allow_json=True) -> {"status", "files", "tests", "findings", "summary", "valid"}
    fleet_report.brief_message(role, path) -> one line telling a worker to read PATH and how to end its reply

`parse` never raises. Only a valid last fenced json block sets `valid` True; the fallbacks (a `Verdict:` line with
finding lines, then a `Status:` line, then a status token) keep `files` [], `tests` "" and `summary` "".
"""
# Complexity notation:
# s = characters of the reply, f = findings in it
import json  # O(1)
import re  # O(1)
import sys  # O(1)
from pathlib import Path  # O(1)

sys.path.insert(0, str(Path(__file__).resolve().parent))  # O(1)
import metrics as mx  # noqa: E402 | O(1)

STATUSES = ("APPROVED", "CHANGES_REQUESTED", "DONE_WITH_CONCERNS", "DONE", "NEEDS_CONTEXT", "BLOCKED")  # O(1)
BLOCK = re.compile(r"^[ \t]*```json[^\n]*\n(.*?)\n?^[ \t]*```[ \t]*$", re.DOTALL | re.M)  # a fenced json block; only a fence line closes it, so a fence inside a string does not | O(s) per opener
VERDICT = re.compile(r"^\s*\**Verdict:\**\s*(APPROVED|CHANGES_REQUESTED)\b", re.M)  # O(1)
FINDING_LINE = re.compile(r"^\s*(?:[-*]\s+)?(\S+?):(\d+)\s+-\s+(.+?)\s+-\s+(.+)\s+-\s+tier\s+([123])\s*$", re.M)  # O(1)
WORK = ("End your reply with the line `Status: <DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED>`, then one fenced json block: "
        '{"status": "<that word>", "files": ["<path changed>"], "tests": "<test command and result line>", '
        '"findings": [{"file": "<path>", "line": <int>, "problem": "<text>", "fix": "<text>", "tier": <1|2|3>}], '
        '"summary": "<one line>"}. `findings` lists only the findings still open; `tier` is the integer 1, 2 or 3 (fixing.md).')  # O(1)
REVIEW = ("After the `Checked:` lines (outside the 300-word cap), end with one fenced json block: "
          '{"status": "<APPROVED|CHANGES_REQUESTED>", "files": [], "tests": "", '
          '"findings": [{"file": "<path>", "line": <int>, "problem": "<text>", "fix": "<text>", "tier": <1|2|3>}], '
          '"summary": "<one line>"}, one finding entry per finding line; `tier` is the integer 1, 2 or 3.')  # O(1)


def _int(v, lo: int, hi: int | None = None) -> bool:  # O(1)
    """An int (not a bool) of at least LO and, when HI is given, at most HI."""
    return isinstance(v, int) and not isinstance(v, bool) and v >= lo and (hi is None or v <= hi)  # O(1)


def _finding_ok(f) -> bool:  # O(1)
    return (isinstance(f, dict) and isinstance(f.get("file"), str) and bool(f["file"])  # O(1)
            and _int(f.get("line"), 0) and isinstance(f.get("problem"), str) and isinstance(f.get("fix"), str)
            and _int(f.get("tier"), 1, 3))


def _from_json(text: str) -> dict | None:  # O(s)
    """The last fenced json block as a report, or None when it is missing, broken or the wrong shape."""
    found = None  # O(1)
    for found in BLOCK.finditer(text):  # the last match counts | O(s)
        pass  # O(1)
    if found is None:  # O(1)
        return None  # O(1)
    try:  # O(1)
        obj = json.loads(found.group(1))  # O(s)
    except (ValueError, RecursionError):  # not json, or nested too deep | O(1)
        return None  # O(1)
    if not isinstance(obj, dict):  # O(1)
        return None  # O(1)
    status = obj.get("status")  # O(1)
    status = status.upper() if isinstance(status, str) else None  # O(1)
    files, tests, summary, findings = obj.get("files", []), obj.get("tests", ""), obj.get("summary", ""), obj.get("findings", [])  # O(1)
    if (status not in STATUSES or not isinstance(files, list) or not all(isinstance(x, str) for x in files)  # O(f)
            or not isinstance(tests, str) or not isinstance(summary, str) or not isinstance(findings, list)
            or not all(_finding_ok(f) for f in findings)):  # one bad finding breaks the block
        return None  # O(1)
    return {"status": status, "files": files, "tests": tests, "findings": findings, "summary": summary, "valid": True}  # O(1)


def parse(text: str, label: str = "", allow_json: bool = True) -> dict:  # O(s)
    """A worker's reply as a report. Order: the last json block (when ALLOW_JSON), a `Verdict:` line with its finding
    lines, a `Status:` line or leading status token, the label's own `Tn ... STATUS`, else UNKNOWN."""
    text = text if isinstance(text, str) else ""  # O(1)
    report = _from_json(text) if allow_json else None  # O(s)
    if report:  # O(1)
        return report  # O(1)
    base = {"files": [], "tests": "", "findings": [], "summary": "", "valid": False}  # O(1)
    m = VERDICT.search(text)  # O(s)
    if m:  # O(1)
        found = [{"file": g[0], "line": int(g[1]), "problem": g[2], "fix": g[3], "tier": int(g[4])}  # O(f)
                 for g in FINDING_LINE.findall(text)]
        return {**base, "status": m.group(1), "findings": found}  # O(1)
    status = mx.status_of(text)  # `Status: X`, else a status token on the first line | O(s)
    if not status and label:  # O(1)
        tid = label.split(",")[0].strip()  # the label's first id | O(1)
        m = re.search(mx.TASK_STATUS.format(re.escape(tid)), text)  # `T4 gallery: BLOCKED by the API` | O(s)
        status = m.group(1).upper() if m else None  # O(1)
    return {**base, "status": status or "UNKNOWN"}  # O(1)


def brief_message(role: str, path: str) -> str:  # O(1)
    """The one line a worker gets for a brief file: read PATH, then how to end the reply (the final reviewer has its
    own, a packet and a json block after its `Checked:` lines)."""
    if role == "final-reviewer":  # O(1)
        return f"Review the packet {path} as your instructions say. {REVIEW}"  # O(1)
    return f"Read {path} and do what it says. {WORK}"  # O(1)
