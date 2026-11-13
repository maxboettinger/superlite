#!/usr/bin/env python3
"""Fleet worker reports: parse a worker's reply into one dict, and build the one-line brief message.

    fleet_report.parse(text, label="", allow_json=True) -> {"status", "files", "tests", "red", "reds", "findings", "summary", "concerns", "valid"}
    fleet_report.brief_message(role, path, full=False) -> one line telling a worker to read PATH and how to end its reply (a lead's follows its brief's End line; O(size of the brief), as it reads the brief file)

`parse` never raises. Only a valid last fenced json block sets `valid` True. The fallbacks (a `Verdict:` line with
finding lines, then a `Status:` line, then a status token) read the labelled form outside fenced blocks: `Files changed:`,
`Test:`/`Tests:`/`Test result:`, `Summary:` and `Concerns:`/`Open questions:` lines (bold, backticked or bulleted labels),
each with an inline value or the list items under it; `concerns` is the list of those entries (the json block's
non-empty `concerns` list wins). `full` makes a final-reviewer brief ask for a full review, not the fast path.
`red` is the json block's non-empty `red` string, else the reply's last `Red run:` line, else ""; a `red` that is neither a string nor an object of strings breaks the block.
`reds` is a batch worker's red run per task id: `Red run Tn:` lines, `Red run:` header items (`- Tn: text`) and the json `red` object.
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
PARTIAL = re.compile(r"^\s*\**Verdict:\**\s*APPROVED\s*\(partial\b", re.M | re.I)  # O(1)
RED_LINE = re.compile(r"^[ \t]*(?:[-*][ \t]+)?([*`]*)Red run([*`]*):([*`]*)[ \t]*(\S.*?)[ \t]*\r?$", re.M)  # O(1)
TID = r"[A-Z]{1,3}\d+[A-Za-z]?"  # a plan task id | O(1)
RED_TASK = re.compile(r"^[ \t]*(?:[-*][ \t]+)?([*`]*)Red run[ \t]+\(?(" + TID + r")\)?[*`]*:[*`]*[ \t]*(\S.*?)[ \t]*\r?$", re.M)  # `Red run Tn: text` | O(1)
RED_HEAD = re.compile(r"^[ \t]*(?:[-*][ \t]+)?[*`]*Red runs?[*`]*:[*`]*[ \t]*(.*?)[ \t]*\r?$")  # a `Red run:` header, with or without a value | O(1)
RED_ITEM = re.compile(r"^[ \t]*(?:(?:[-*+]|\d+[.)])[ \t]+)?[*`]*(" + TID + r")[*`]*:[*`]*[ \t]*(\S.*?)[ \t]*\r?$")  # a per-task item under a header | O(1)
FINDING_LINE = re.compile(r"^\s*(?:[-*]\s+)?(\S+?):(\d+)\s+-\s+(.+?)\s+-\s+(.+)\s+-\s+tier\s+([123])\s*$", re.M)  # O(1)
LABEL = re.compile(r"^[ \t]*(?:[-*+][ \t]+)?[*_`]*(files changed|changed files|files touched|files|tests?(?: command| results?)?|results?|summary|concerns|open questions|questions)"
                   r"[*_`]*[ \t]*:[*_`]*[ \t]*(.*)$", re.I)  # a label line, its text stripped of trailing blanks | O(1)
ITEM = re.compile(r"^[ \t]*(?:[-*+]|\d+[.)])[ \t]+(.*)$")  # a list item under a label | O(1)
NONE_WORDS = ("none", "(none)", "-", "n/a")  # O(1)
FULL = "Full review: the packet's FAST PATH line does not apply; review every section and the diff."  # O(1)
WORK = ("End your reply with the line `Status: <DONE|DONE_WITH_CONCERNS|NEEDS_CONTEXT|BLOCKED>`, then one fenced json block: "
        '{"status": "<that word>", "files": ["<path changed>"], "tests": "<test command and result line>", '
        '"red": "<the summary line of the run that saw your new tests fail, or none - no test>", '
        '"findings": [{"file": "<path>", "line": <int>, "problem": "<text>", "fix": "<text>", "tier": <1|2|3>}], '
        '"summary": "<one line>"}. `findings` lists only the findings still open; `tier` is the integer 1, 2 or 3 (fixing.md).')  # O(1)
RED_ONE = '"red": "<the summary line of the run that saw your new tests fail, or none - no test>"'  # O(1)
RED_MANY = '"red": {"<task id>": "<the summary line of the run that saw that task\'s new tests fail, or none - no test>"}'  # O(1)
WORK_BATCH = WORK.replace(RED_ONE, RED_MANY, 1)  # a batch worker's red is an object keyed by task id | O(1)
PLANNED = WORK.replace("`Status: <DONE|", "`Status: <DONE planned: <plan path>|DONE|", 1)  # O(1)
PLANNED_END = "End: Status: DONE planned:"  # O(1)
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


def _red_line(text: str) -> str:  # O(s)
    """The last `Red run:` line's text, else ""."""
    found = RED_LINE.findall(text)  # O(s)
    if not found:  # O(1)
        return ""  # O(1)
    opener, _, _, value = found[-1]  # O(1)
    if opener.startswith("**") and value.endswith("**"):  # a fully bold line closes its stars after the value
        value = value[:-2].rstrip()  # O(1)
    return value  # O(1)


def _red_tasks(text: str) -> dict:  # O(s)
    """Per-task red runs: the `Red run Tn:` lines and the items under `Red run:` headers, a later entry for an id winning."""
    out, head, first = {}, False, True  # head = inside a header's item list, first = no item read yet | O(1)
    for line in text.split("\n"):  # O(s)
        m = RED_TASK.match(line)  # O(len)
        if m:  # O(1)
            value = m.group(3).strip()  # O(len)
            if m.group(1).startswith("**") and value.endswith("**"):  # a fully bold line closes its stars after the value
                value = value[:-2].rstrip()  # O(1)
            out[m.group(2)] = value  # O(1)
            head = False  # O(1)
            continue  # O(1)
        if RED_HEAD.match(line):  # O(len)
            head, first = True, True  # O(1)
            continue  # O(1)
        if head:  # O(1)
            if first and not line.strip():  # blank lines count only before the first item | O(1)
                continue  # O(1)
            m = RED_ITEM.match(line)  # O(len)
            if m:  # O(1)
                out[m.group(1)] = m.group(2).strip()  # O(1)
                first = False  # O(1)
                continue  # O(1)
            head = False  # the first other line ends the list | O(1)
    return out  # O(1)


def _file_entry(part: str) -> str:  # O(p)
    """A files entry: its first backticked span, else its first token without a trailing `:,;`."""
    part = part.strip()  # O(p)
    m = re.search(r"`([^`]+)`", part)  # O(p)
    if m:  # O(1)
        return m.group(1).strip()  # O(1)
    return part.split(None, 1)[0].rstrip(":,;") if part else ""  # O(p)


def _labelled(text: str) -> dict:  # O(s)
    """Files, tests, summary, concerns and finding lines read from the labelled lines outside fenced blocks."""
    files, tests, summaries, concerns, findings = [], [], [], [], []  # O(1)
    seen, fenced, cur, cur_ind = set(), False, None, None  # cur = [kind, inline value, items] of the open label; cur_ind = its bullet indent, None when not bulleted | O(1)
    for raw in text.split("\n"):  # O(s)
        line = raw.rstrip()  # O(len)
        if line.lstrip().startswith("```"):  # a fence line toggles | O(1)
            fenced, cur, cur_ind = not fenced, None, None  # O(1)
            continue  # O(1)
        if fenced:  # O(1)
            continue  # O(1)
        if cur is not None and not line.strip() and not cur[1] and not cur[2]:  # a blank line keeps an empty label open | O(1)
            continue  # O(1)
        bullet = cur is not None and ITEM.match(line)  # O(len)
        sibling = bool(bullet) and cur_ind is not None and len(line) - len(line.lstrip()) <= cur_ind  # a bullet no deeper than a bulleted open label is a sibling | O(1)
        head = RED_HEAD.match(line)  # O(len)
        if cur is not None and (RED_TASK.match(line) or (head and (sibling or not head.group(1)))):  # a red header or per-task line, or a sibling `Red run:`, closes the open label | O(len)
            cur, cur_ind = None, None  # O(1)
            continue  # O(1)
        m = LABEL.match(line) if not bullet or sibling else None  # else a bullet under an open label is an item | O(len)
        if m:  # O(1)
            name = m.group(1).lower()  # O(1)
            kind = "files" if name.startswith(("file", "changed")) else "tests" if name.startswith(("test", "result")) else "summary" if name == "summary" else "concerns"  # O(1)
            cur = [kind, m.group(2).strip(), []]  # O(1)
            cur_ind = len(line) - len(line.lstrip()) if ITEM.match(line) else None  # O(len)
            (files if kind == "files" else tests if kind == "tests" else summaries if kind == "summary" else concerns).append(cur)  # O(1)
            continue  # O(1)
        f = FINDING_LINE.match(line)  # O(len)
        if f:  # O(1)
            findings.append({"file": f.group(1), "line": int(f.group(2)), "problem": f.group(3), "fix": f.group(4), "tier": int(f.group(5))})  # O(1)
        m = ITEM.match(line)  # O(len)
        if m and cur is not None:  # O(1)
            cur[2].append(m.group(1).strip())  # O(1)
        else:  # a blank or other line ends the items | O(1)
            cur, cur_ind = None, None  # O(1)
    out_files = []  # O(1)
    for _, value, items in files:  # O(s)
        for part in value.split(",") + items if value else items:  # O(s)
            entry = _file_entry(part)  # O(p)
            if entry and entry.lower() not in NONE_WORDS and entry not in seen:  # O(1)
                seen.add(entry)  # O(1)
                out_files.append(entry)  # O(1)
    first = lambda block: block[1] or (block[2][0] if block[2] else "")  # O(1)
    out_tests = [t for t in (first(b) for b in tests) if t]  # O(t)
    out_concerns = []  # O(1)
    for _, value, items in concerns:  # O(s)
        for part in ([value] if value else []) + items:  # O(s)
            part = part.replace("**", "").strip()  # O(p)
            if part and part.lower() not in NONE_WORDS:  # O(1)
                out_concerns.append(part)  # O(1)
    return {"files": out_files, "tests": "; ".join(out_tests), "summary": first(summaries[0]) if summaries else "", "concerns": out_concerns, "findings": findings}  # O(1)


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
    red = obj.get("red", "")  # O(1)
    json_reds = {}  # O(1)
    if isinstance(red, dict) and all(isinstance(k, str) and isinstance(v, str) for k, v in red.items()):  # a batch worker's object keyed by task id | O(f)
        json_reds = {k.strip(): v.strip() for k, v in red.items() if k.strip() and v.strip()}  # O(f)
        red = ""  # O(1)
    files, tests, summary, findings = obj.get("files", []), obj.get("tests", ""), obj.get("summary", ""), obj.get("findings", [])  # O(1)
    if (status not in STATUSES or not isinstance(files, list) or not all(isinstance(x, str) for x in files)  # O(f)
            or not isinstance(tests, str) or not isinstance(red, str) or not isinstance(summary, str) or not isinstance(findings, list)
            or not all(_finding_ok(f) for f in findings)):  # one bad finding breaks the block
        return None  # O(1)
    concerns = obj.get("concerns")  # O(1)
    if not (isinstance(concerns, list) and concerns and all(isinstance(x, str) for x in concerns)):  # else the labelled lines | O(f)
        concerns = _labelled(text)["concerns"]  # O(s)
    return {"status": status, "files": files, "tests": tests, "red": red or _red_line(text), "reds": {**_red_tasks(text), **json_reds}, "findings": findings, "summary": summary, "concerns": concerns, "valid": True}  # O(1)


def partial(text: str) -> bool:  # an APPROVED verdict that left packet lines unread | O(s)
    return bool(PARTIAL.search(text if isinstance(text, str) else ""))  # O(s)


def parse(text: str, label: str = "", allow_json: bool = True) -> dict:  # O(s)
    """A worker's reply as a report. Order: the last json block (when ALLOW_JSON), a `Verdict:` line with its finding
    lines, a `Status:` line or leading status token, the label's own `Tn ... STATUS`, else UNKNOWN."""
    text = text if isinstance(text, str) else ""  # O(1)
    report = _from_json(text) if allow_json else None  # O(s)
    if report:  # O(1)
        return report  # O(1)
    lab = _labelled(text)  # O(s)
    base = {"files": lab["files"], "tests": lab["tests"], "red": _red_line(text), "reds": _red_tasks(text), "findings": [], "summary": lab["summary"], "concerns": lab["concerns"], "valid": False}  # O(1)
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
    return {**base, "status": status or "UNKNOWN", "findings": lab["findings"]}  # O(1)


def _planning(path: str) -> bool:  # O(size of the brief)
    """True when the brief at PATH holds a line starting with PLANNED_END (a plan-phase lead brief)."""
    try:  # O(1)
        with open(path, encoding="utf-8", errors="replace") as fh:  # O(1)
            return any(line.startswith(PLANNED_END) for line in fh)  # O(size of the brief)
    except OSError:  # O(1)
        return False  # O(1)


def brief_message(role: str, path: str, full: bool = False) -> str:  # O(size of the brief)
    """The one line a worker gets for a brief file: read PATH, then how to end the reply (the final reviewer has its
    own, a packet and a json block after its `Checked:` lines; a lead whose brief holds the plan-phase End line gets
    PLANNED, naming `DONE planned: <plan path>`). FULL asks a final reviewer for a full review."""
    if role == "final-reviewer":  # O(1)
        return f"Review the packet {path} as your instructions say. {FULL + ' ' if full else ''}{REVIEW}"  # O(1)
    if role == "lead" and _planning(path):  # O(size of the brief)
        return f"Read {path} and do what it says. {PLANNED}"  # O(1)
    return f"Read {path} and do what it says. {WORK}"  # O(1)
