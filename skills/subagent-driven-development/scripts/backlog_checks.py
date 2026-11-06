#!/usr/bin/env python3
"""Checks for backlog questions and batch proposals; merging of clashing batches."""
import copy
import json
import re

ID_RE = re.compile(r"^B[1-9][0-9]?$")
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FENCE_RE = re.compile(r"```json[ \t]*\r?\n(.*?)```", re.S)
DEFAULTS = {"state": "planned", "answers": {}, "lead": None, "agent": None, "worktree": None, "branch": None, "since": 0,
            "pr": None, "merged": False, "version": None, "reason": "", "ship_runs": 0, "questions": 0}


def _ctrl(s: str) -> bool:
    return any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in s)  # O(len)


def _text(errs: list, where: str, v, lo: int, hi: int, msg: str) -> bool:
    if not isinstance(v, str) or not lo <= len(v) <= hi:  # O(1)
        errs.append(f"{where}: {msg}")
        return False
    if _ctrl(v):  # O(len)
        errs.append(f"{where}: control character")
        return False
    return True


def as_batch(q):
    """A bare question object {"question", "header", "options"} becomes {"questions": [q]}; anything else passes through."""
    if isinstance(q, dict) and "questions" not in q and "question" in q:  # O(1)
        return {"questions": [q]}
    return q


def check_question(q: dict) -> list[str]:
    q = as_batch(q)
    if not isinstance(q, dict) or not isinstance(q.get("questions"), list):  # O(1)
        return ["not an object with questions"]
    qs = q["questions"]
    errs: list[str] = []
    if not 1 <= len(qs) <= 4:
        return ["questions: 1 to 4 entries"]
    seen: set = set()
    for i, e in enumerate(qs, 1):  # O(4 * options)
        p = f"q{i}"
        if not isinstance(e, dict):
            errs.append(f"{p}: not an object")
            continue
        if _text(errs, f"{p} question", e.get("question"), 1, 300, "1 to 300 characters"):
            if e["question"] in seen:
                errs.append(f"{p} question: duplicate")
            seen.add(e["question"])
        _text(errs, f"{p} header", e.get("header"), 1, 12, "1 to 12 characters")
        opts = e.get("options")
        if not isinstance(opts, list) or not 2 <= len(opts) <= 4:
            errs.append(f"{p} options: 2 to 4 entries")
        else:
            labels: set = set()
            for o in opts:
                if not isinstance(o, dict):
                    errs.append(f"{p} options: not an object")
                    continue
                if _text(errs, f"{p} options label", o.get("label"), 1, 60, "label 1 to 60 characters"):
                    if o["label"] in labels:
                        errs.append(f"{p} options: duplicate label {o['label']}")
                    labels.add(o["label"])
                _text(errs, f"{p} options description", o.get("description", ""), 0, 200, "description 0 to 200 characters")
        if "multiSelect" in e and not isinstance(e["multiSelect"], bool):
            errs.append(f"{p} multiSelect: true or false")
    return errs


def clean_question(q: dict) -> dict:
    """Rebuild a question that check_question accepted from its validated fields only: unknown keys never pass."""
    out = []
    for e in as_batch(q)["questions"]:  # O(4 * options)
        c = {"question": e["question"], "header": e["header"],
             "options": [{k: o[k] for k in ("label", "description") if k in o} for o in e["options"]]}
        if "multiSelect" in e:
            c["multiSelect"] = e["multiSelect"]
        out.append(c)
    return {"questions": out}


def _plain(f) -> str | None:
    if not isinstance(f, str) or not f or "\0" in f or "\\" in f or f[0] in "/~":  # O(len)
        return None
    parts = f.split("/")
    if ".." in parts:
        return None
    while parts and parts[0] == ".":
        parts = parts[1:]
    parts = [x for x in parts if x not in ("", ".")]
    return "/".join(parts) if parts else None


def _reach(batches: list[dict]) -> dict:
    deps = {b["id"]: set(b["depends"]) for b in batches}
    out = {}
    for s in deps:  # O(n * edges)
        seen: set = set()
        stack = list(deps[s])
        while stack:
            x = stack.pop()
            if x in seen or x not in deps:
                continue
            seen.add(x)
            stack.extend(deps[x])
        out[s] = seen
    return out


def check_proposal(obj: dict, known: set[int]) -> tuple[list[dict], list[str]]:
    if not isinstance(obj, dict) or not isinstance(obj.get("batches"), list):  # O(1)
        return [], ["proposal: not an object with batches"]
    raw = obj["batches"]
    if not 1 <= len(raw) <= 20:
        return [], ["batches: 1 to 20 entries"]
    errs: list[str] = []
    out: list[dict] = []
    ids: set = set()
    owner: dict = {}
    for n, b in enumerate(raw, 1):  # O(batches * fields)
        if not isinstance(b, dict):
            errs.append(f"batch {n}: not an object")
            continue
        bid = b.get("id")
        if not isinstance(bid, str) or not ID_RE.match(bid):
            errs.append(f"batch {n}: id must be B<n>")
            continue
        if bid in ids:
            errs.append(f"{bid}: duplicate id")
            continue
        ids.add(bid)
        topic = b.get("topic")
        if not isinstance(topic, str) or not TOPIC_RE.match(topic):
            errs.append(f"{bid}: topic must be lowercase words joined by -")
        issues = b.get("issues")
        if not isinstance(issues, list) or not issues or not all(isinstance(i, int) and not isinstance(i, bool) for i in issues):
            errs.append(f"{bid}: issues must be a non-empty list of numbers")
            issues = []
        for i in issues:
            if i not in known:
                errs.append(f"{bid}: unknown issue #{i}")
            elif i in owner and owner[i] != bid:
                errs.append(f"#{i} is in {owner[i]} and {bid}")
            else:
                owner[i] = bid
        files = b.get("files", [])
        clean: set = set()
        if not isinstance(files, list):
            errs.append(f"{bid}: files must be a list")
            files = None
        for f in files or []:
            p = _plain(f)
            if p is None:
                errs.append(f"{bid}: file {f!r} is not a plain relative path")
            else:
                clean.add(p)
        if files is not None and not files:
            errs.append(f"{bid}: files must list at least one repo-relative file")
        deps = b.get("depends", [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            errs.append(f"{bid}: depends must be a list of batch ids")
            deps = []
        decisions = b.get("decisions", [])
        if not isinstance(decisions, list):
            errs.append(f"{bid}: decisions must be a list")
            decisions = []
        cleaned = []
        for k, d in enumerate(decisions, 1):
            bad = check_question(d)
            errs.extend(f"{bid} decision {k}: {e}" for e in bad)
            if not bad:
                cleaned.append(clean_question(d))
        out.append({"id": bid, "topic": topic, "issues": sorted(set(issues)), "files": sorted(clean), "depends": list(dict.fromkeys(deps)),
                    "decisions": cleaned, **copy.deepcopy(DEFAULTS)})
    for b in out:  # O(batches * deps)
        for d in b["depends"]:
            if d not in ids or d == b["id"]:
                errs.append(f"{b['id']}: depends on unknown batch {d}" if d not in ids else f"{b['id']}: depends on itself")
    if not errs:
        r = _reach(out)
        cyc = sorted(k for k, v in r.items() if k in v)
        if cyc:
            errs.append("dependency cycle: " + " ".join(cyc))
    return ([], errs) if errs else (out, [])


def _num(b: dict) -> int:
    return int(b["id"][1:])


def separate(batches: list[dict]) -> list[dict]:
    bs = sorted(copy.deepcopy(batches), key=_num)  # O(n log n)
    while True:  # O(n^3) worst case, n <= 20
        r = _reach(bs)
        pair = None
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                cyc = b["id"] in r[a["id"]] and a["id"] in r[b["id"]]
                clash = set(a["files"]) & set(b["files"]) and b["id"] not in r[a["id"]] and a["id"] not in r[b["id"]]
                if cyc or clash:
                    pair = (a, b)
                    break
            if pair:
                break
        if not pair:
            return bs
        a, b = pair
        a["issues"] = sorted(set(a["issues"]) | set(b["issues"]))
        a["files"] = sorted(set(a["files"]) | set(b["files"]))
        a["decisions"] = a["decisions"] + b["decisions"]
        a["depends"] = [d for d in dict.fromkeys(a["depends"] + b["depends"]) if d not in (a["id"], b["id"])]
        bs.remove(b)
        for x in bs:
            if x is not a:
                x["depends"] = [a["id"] if d == b["id"] else d for d in x["depends"]]
                x["depends"] = [d for d in dict.fromkeys(x["depends"]) if d != x["id"]]


def proposal_from(text: str) -> dict | None:
    for m in reversed(FENCE_RE.findall(text or "")):  # O(blocks * len)
        try:
            o = json.loads(m)
        except (ValueError, RecursionError):
            continue
        if isinstance(o, dict) and "batches" in o:
            return o
    return None
