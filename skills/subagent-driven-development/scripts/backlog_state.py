#!/usr/bin/env python3
"""Backlog state (phase 3): `<main root>/.superlite/backlog.json`, locked read-modify-write, questions, status lines."""
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


def _admit_q(o: dict) -> str:
    return f"Admit outside issue #{o['number']} ({_title(o.get('title', ''))}, by {o.get('author', '')}) into the backlog?"


def open_questions(data: dict) -> list:
    out = []
    if data.get("approved_ship") is None and data.get("batches"):
        out.append({"question": SHIP_Q, "header": "Ship", "multiSelect": False, "options": [
            {"label": SHIP_OK, "description": "one yes for all batches"},
            {"label": SHIP_NO, "description": "leads stop before ship"}]})
    for o in data.get("outside", []):  # O(outside)
        out.append({"question": _admit_q(o), "header": f"#{o['number']}", "multiSelect": False, "options": [
            {"label": "Admit", "description": "triaged on the next sl backlog plan"},
            {"label": "Skip", "description": "stays out of this backlog"}]})
    for b in data.get("batches", []):  # O(batches * questions)
        if b["state"] == "planned":
            out.extend({**q, "question": f"{b['id']}: {q['question']}"} for q in _unanswered(b))
    return out


def answer(data: dict, answers: dict, by: str, now: str) -> list:
    qs = {q["question"] for q in open_questions(data)}
    errs, outside = [], {_admit_q(o): o for o in data.get("outside", [])}
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
        msg = f"skipped #{n} (in no batch)"
    else:
        if hit["state"] != "planned" and not (hit["state"] == "parked" and not hit.get("worktree")):
            raise ValueError(f"#{n} is in {hit['id']}, which is {hit['state']}")
        hit["issues"] = [i for i in hit["issues"] if i != n]  # O(issues)
        if hit["issues"]:
            msg = f"skipped #{n} ({hit['id']} keeps " + " ".join(f"#{i}" for i in hit["issues"]) + ")"
        else:
            data["batches"] = [b for b in data["batches"] if b is not hit]  # O(batches)
            for b in data["batches"]:  # O(batches * depends)
                b["depends"] = [d for d in b.get("depends", []) if d != hit["id"]]
            msg = f"skipped #{n} ({hit['id']} dropped)"
    data["outside"] = [o for o in data.get("outside", []) if o.get("number") != n]  # O(outside)
    if n not in data["skipped"]:  # O(skipped)
        data["skipped"].append(n)
    return msg


def park(data: dict, bid: str, reason: str) -> str:
    b = batch(data, bid)
    if b["state"] != "planned":
        raise ValueError(f"{bid} is {b['state']}; only a planned batch can be parked")
    if not isinstance(reason, str) or not 1 <= len(reason) <= 200 or re.search(r"[\x00-\x1f\x7f]", reason):
        raise ValueError("reason: 1 to 200 characters, no control characters")
    b["state"], b["reason"], b["parked_by"] = "parked", reason, "main"
    return f"{bid} parked: {reason}"


def status_lines(data: dict) -> list:
    bs = data.get("batches", [])
    run = sum(1 for b in bs if b["state"] in ACTIVE)
    ship = data.get("approved_ship")
    sh = f"ship approved ({ship['by']} {ship['time']})" if ship else "ship not approved"
    repo = f" {data['repo']}" if data.get("repo") else ""
    head = f"backlog{repo}: {len(bs)} batches, {run} running, {sum(1 for b in bs if b['state'] == 'shipped')} shipped, {sh}"
    if not bs:
        return [head]
    active = [b for b in bs if b["state"] in ACTIVE]
    lines = [head, "batch | issues | state | lead | PR | next"]
    for b in bs:  # O(batches)
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
            nxt = (b.get("version") or "-") + (" OPEN " + " ".join(f"#{i}" for i in b["open_issues"]) if b.get("open_issues") else "")
        issues = " ".join(f"#{i}" for i in b.get("issues", []))
        lines.append(f"{b['id']} | {issues} | {s} | {b.get('lead') or '-'} | {'#%s' % b['pr'] if b.get('pr') else '-'} | {nxt}")
    n = len(open_questions(data))
    if n:
        lines.append(f"questions: {n} open (sl backlog decide --print)")
    return lines
