#!/usr/bin/env python3
"""Backlog state (phase 3): `<main root>/.superlite/backlog.json`, locked read-modify-write, questions, status lines.

An `outside[]` entry with a non-empty string `reason` is a left-out issue (the plan did not take it): it never becomes an
Admit question and `status_lines` prints it grouped by reason. An entry without one is an outside-author issue.
`status_lines` collapses the shipped batches of earlier plan rounds into one `earlier rounds: N shipped` line; `status --all` lists them (#406)."""
import fcntl
import json
import os
import re
import subprocess
from pathlib import Path

SHIP_Q = ("Approve that every batch lead ships its own batch (rebase, version bump, maxapp ship into the default "
          "branch) under the ship lock?")
SHIP_OK, SHIP_NO = "Approve shipping", "Not yet"
ACTIVE = ("running", "needs_decision")


def main_root(start: Path) -> Path:
    try:
        r = subprocess.run(["git", "-C", str(start), "rev-parse", "--path-format=absolute", "--git-common-dir"],
                           capture_output=True, text=True, check=True)  # O(1)
    except (subprocess.CalledProcessError, OSError):
        raise RuntimeError("not in a git repository") from None
    return Path(r.stdout.strip()).parent.resolve()  # O(1)


def path(root: Path) -> Path:
    return Path(root) / ".superlite" / "backlog.json"  # O(1)


def default() -> dict:
    return {"version": 1, "repo": "", "approved_ship": None, "titles": {}, "outside": [], "admitted": [],
            "skipped": [], "batches": []}  # O(1)


def load(p: Path) -> dict:
    try:
        d = json.loads(Path(p).read_text())  # O(size)
    except (OSError, ValueError):
        return default()
    return d if isinstance(d, dict) else default()


def update(p: Path, fn):
    p = Path(p)
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p.with_name(p.name + ".lock"), "a") as lk:
        fcntl.flock(lk, fcntl.LOCK_EX)  # O(wait)
        d = load(p)
        res = fn(d)
        tmp = p.with_name(p.name + ".tmp")
        tmp.write_text(json.dumps(d, indent=2))  # O(size)
        os.replace(tmp, p)
        return res


def batch(data: dict, bid: str) -> dict:
    for b in data.get("batches", []):  # O(batches)
        if b.get("id") == bid:
            return b
    raise KeyError(f"unknown batch {bid}")


def _qs(b: dict) -> list:
    return [q for dec in b.get("decisions", []) for q in dec.get("questions", [])]  # O(questions)


def _unanswered(b: dict) -> list:
    return [q for q in _qs(b) if not b.get("answers", {}).get(q["question"])]  # O(questions)


def _id_key(bid: str):
    m = re.search(r"\d+", bid)
    return (int(m.group()) if m else 0, bid)


def _shipped(data: dict, bid: str) -> bool:
    return any(b["id"] == bid and b["state"] == "shipped" for b in data["batches"])  # O(batches)


def _clash(b: dict, others: list):
    for o in others:  # O(batches * files)
        if set(b.get("files", [])) & set(o.get("files", [])):
            return o
    return None


def startable(data: dict, cap: int = 2) -> list:
    bs = data.get("batches", [])
    active = [b for b in bs if b["state"] in ACTIVE]
    room, chosen, out = cap - len(active), [], []
    for b in sorted((b for b in bs if b["state"] == "planned"), key=lambda b: _id_key(b["id"])):  # O(b log b)
        if len(out) >= room:
            break
        if not all(_shipped(data, d) for d in b.get("depends", [])) or _unanswered(b):
            continue
        if _clash(b, active + chosen):
            continue
        chosen.append(b)
        out.append(b["id"])
    return out


def _title(t) -> str:
    return re.sub(r"[\x00-\x1f\x7f]", " ", str(t))[:80]  # O(len)


def _left_out(o: dict) -> bool:
    return isinstance(o.get("reason"), str) and bool(o["reason"])  # O(1)


def admit_entries(data: dict) -> list:
    return [o for o in data.get("outside", []) if not _left_out(o)]  # O(outside)


def ref(n) -> str:
    """An issue as shown: #12 for a number, the key itself (PIX-4) for a Jira key."""
    return f"#{n}" if isinstance(n, int) else str(n)  # O(1)


def left_out_lines(data: dict) -> list:
    """One `<reason>: refs` line per reason; an issue already in a batch is not listed (#483); rounds above 1 show as `(N rounds)`; cap hints close the list."""
    held = {i for b in data.get("batches", []) for i in b.get("issues", [])}  # O(batches * issues)
    groups = {}
    for o in data.get("outside", []):  # O(outside)
        if _left_out(o) and o.get("number") not in held:  # O(1)
            r = o.get("rounds")
            tag = f" ({r} rounds)" if isinstance(r, int) and not isinstance(r, bool) and r > 1 else ""  # O(1)
            groups.setdefault(_title(o["reason"]), []).append(ref(o["number"]) + tag)  # O(1)
    lines = [f"{r}: {' '.join(ns)}" for r, ns in groups.items()]  # O(groups)
    if any(r.startswith("not planned (cap)") for r in groups):  # O(groups)
        m = data.get("max_batches")
        m = m if isinstance(m, int) and not isinstance(m, bool) else 7  # O(1)
        lines.append(f"cap: a plan round holds at most {m} batches (sl backlog plan --max-batches N raises it, up to 20); capped issues rank first in the next round")  # O(1)
    ks = list(dict.fromkeys(m.group(1) for r in groups if (m := re.match(r"^not triaged \((\d+) cap\)$", r))))  # O(groups)
    for k in ks:  # O(ks)
        lines.append(f"cap: a plan round triages only the first {k} open issues; the rest rank first in the next round")  # O(1)
    return lines


def _admit_q(o: dict) -> str:
    return f"Admit outside issue #{o['number']} ({_title(o.get('title', ''))}, by {o.get('author', '')}) into the backlog?"


def open_questions(data: dict) -> list:
    out = []
    if data.get("approved_ship") is None and data.get("batches"):
        out.append({"question": SHIP_Q, "header": "Ship", "multiSelect": False, "options": [
            {"label": SHIP_OK, "description": "one yes for all batches"},
            {"label": SHIP_NO, "description": "leads stop before ship"}]})
    for o in admit_entries(data):  # O(outside)
        out.append({"question": _admit_q(o), "header": f"#{o['number']}", "multiSelect": False, "options": [
            {"label": "Admit", "description": "triaged on the next sl backlog plan"},
            {"label": "Skip", "description": "stays out of this backlog"}]})
    for b in data.get("batches", []):  # O(batches * questions)
        if b["state"] == "planned":
            out.extend({**q, "question": f"{b['id']}: {q['question']}"} for q in _unanswered(b))
    return out


def answer(data: dict, answers: dict, by: str, now: str) -> list:
    qs = {q["question"] for q in open_questions(data)}
    errs, outside = [], {_admit_q(o): o for o in admit_entries(data)}
    for q, a in answers.items():  # O(answers * batches)
        if q not in qs:
            errs.append(f"no open question: {q}")
        elif q == SHIP_Q:
            if a == SHIP_OK:
                data["approved_ship"] = {"by": by, "time": now}
            elif a != SHIP_NO:
                errs.append(f"ship: answer must be {SHIP_OK} or {SHIP_NO}")
        elif q in outside:
            o = outside[q]
            if a not in ("Admit", "Skip"):
                errs.append(f"#{o['number']}: answer must be Admit or Skip")
                continue
            data["admitted" if a == "Admit" else "skipped"].append(o["number"])
            data["outside"] = [x for x in data["outside"] if x is not o]
        else:
            bid, _, text = q.partition(": ")
            if a:
                batch(data, bid).setdefault("answers", {})[text] = a
    return errs


def skip_issue(data: dict, n: int) -> str:
    hit = next((b for b in data.get("batches", []) if n in b.get("issues", [])), None)  # O(batches * issues)
    if hit is None:
        msg = f"skipped {ref(n)} (in no batch)"
    else:
        if hit["state"] in ACTIVE:
            raise ValueError(f"{ref(n)} is in {hit['id']}, which is {hit['state']}")
        hit["issues"] = [i for i in hit["issues"] if i != n]  # O(issues)
        if hit["issues"]:
            msg = f"skipped {ref(n)} ({hit['id']} keeps " + " ".join(ref(i) for i in hit["issues"]) + ")"
        else:
            data["batches"] = [b for b in data["batches"] if b is not hit]  # O(batches)
            for b in data["batches"]:  # O(batches * depends)
                b["depends"] = [d for d in b.get("depends", []) if d != hit["id"]]
            keep = f"; its worktree {hit['worktree']} stays" if hit["state"] == "parked" and hit.get("worktree") else ""
            msg = f"skipped {ref(n)} ({hit['id']} dropped{keep})"
    data["outside"] = [o for o in data.get("outside", []) if o.get("number") != n]  # O(outside)
    if n not in data["skipped"]:  # O(skipped)
        data["skipped"].append(n)
    return msg


NOTE_MAX = 2000
NOTE_CTRL = re.compile(r"[\x00-\x08\x0b-\x1f\x7f]")


def read_note(path: str) -> str:
    try:
        raw = Path(path).read_text(encoding="utf-8-sig")
    except (OSError, UnicodeDecodeError) as e:
        raise ValueError(f"--note {path} unreadable: {e}") from None
    t = NOTE_CTRL.sub("", raw.replace("\r\n", "\n").replace("\r", "\n"))  # O(len)
    t = "\n".join(ln.rstrip() for ln in t.split("\n")).strip()  # O(len)
    if len(t) > NOTE_MAX:
        raise ValueError(f"--note {path}: {len(t)} characters, at most 2000")
    return t


def set_note(data: dict, text: str, src: str, now: str) -> str:
    if not text:
        data.pop("note", None)
        return "note: cleared; lead briefs carry no note"
    data["note"] = {"text": text, "file": src, "time": now}
    n = len(text.split("\n"))
    return f"note: stored from {src} ({n} line{'' if n == 1 else 's'}); every lead brief from now on carries it"


def note_line(data: dict):
    nt = data.get("note")
    if not isinstance(nt, dict) or not isinstance(nt.get("text"), str) or not nt["text"]:
        return None
    n = len(nt["text"].split("\n"))
    return (f"note: {n} line{'' if n == 1 else 's'} from {nt.get('file')} ({nt.get('time')}) go into every lead brief "
            "(sl backlog start --note FILE replaces it, an empty file clears it)")


def park(data: dict, bid: str, reason: str) -> str:
    b = batch(data, bid)
    if b["state"] != "planned":
        raise ValueError(f"{bid} is {b['state']}; only a planned batch can be parked")
    if not isinstance(reason, str) or not 1 <= len(reason) <= 200 or re.search(r"[\x00-\x1f\x7f]", reason):
        raise ValueError("reason: 1 to 200 characters, no control characters")
    b["state"], b["reason"], b["parked_by"] = "parked", reason, "main"
    return f"{bid} parked: {reason}"


def in_round(data: dict, b: dict) -> bool:
    if b["state"] != "shipped":  # O(1)
        return True  # O(1)
    if isinstance(data.get("round"), list):  # O(1)
        return b["id"] in data["round"]  # O(round)
    titles = data.get("titles") or {}  # O(1)
    return not titles or any(str(i) in titles for i in b.get("issues", []))  # O(issues)


def status_lines(data: dict, all_: bool = False) -> list:
    bs = data.get("batches", [])
    run = sum(1 for b in bs if b["state"] in ACTIVE)
    ship = data.get("approved_ship")
    sh = f"ship approved ({ship['by']} {ship['time']})" if ship else "ship not approved"
    repo = f" {data['repo']}" if data.get("repo") else ""
    head = f"backlog{repo}: {len(bs)} batches, {run} running, {sum(1 for b in bs if b['state'] == 'shipped')} shipped, {sh}"
    nl = note_line(data)
    if not bs:
        return [head] + left_out_lines(data) + ([nl] if nl else [])
    active = [b for b in bs if b["state"] in ACTIVE]
    rows = bs if all_ else [b for b in bs if in_round(data, b)]  # O(batches)
    lines = [head]  # O(1)
    if len(rows) < len(bs):  # O(1)
        lines.append(f"earlier rounds: {len(bs) - len(rows)} shipped (sl backlog status --all lists them)")  # O(1)
    if rows:  # O(1)
        lines.append("batch | issues | state | lead | PR | next")  # O(1)
    for b in rows:  # O(batches)
        s = b["state"]
        if s == "planned":
            dep = next((d for d in b.get("depends", []) if not _shipped(data, d)), None)
            c = _clash(b, [o for o in active if o is not b])
            nxt = f"waits {dep}" if dep else "decide" if _unanswered(b) else f"clash {c['id']}" if c else "start"
        elif s == "running":
            nxt = "sl backlog wait"
        elif s == "needs_decision":
            nxt = f"sl backlog decide --print --batch {b['id']}"
        elif s == "parked":
            nxt = (b.get("reason") or "-")[:40]
        else:
            nxt = (b.get("version") or "-") + (" OPEN " + " ".join(ref(i) for i in b["open_issues"]) if b.get("open_issues") else "")
        issues = " ".join(ref(i) for i in b.get("issues", []))
        lines.append(f"{b['id']} | {issues} | {s} | {b.get('lead') or '-'} | {'#%s' % b['pr'] if b.get('pr') else '-'} | {nxt}")
    lines.extend(left_out_lines(data))
    if nl:
        lines.append(nl)
    n = len(open_questions(data))
    if n:
        lines.append(f"questions: {n} open (sl backlog decide --print)")
    return lines
