#!/usr/bin/env python3
"""Checks for backlog questions and batch proposals; one cut rule for plan and lead questions; merging of clashing batches; a file two batches only append to does not clash (append_only, #602)."""
import copy
import json
import re

ID_RE = re.compile(r"^B[1-9][0-9]{0,5}$")
TOPIC_RE = re.compile(r"^[a-z0-9][a-z0-9-]{0,39}$")
FENCE_RE = re.compile(r"```json[ \t]*\r?\n(.*?)```", re.S)
REC = " (Recommended)"
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


RUNS = {"main": "main", "user": "Max"}


def _line(v: object, hi: int, lo: int) -> bool:
    return isinstance(v, str) and lo <= len(v) <= hi and not any(ord(c) < 32 or ord(c) == 127 for c in v)  # O(len)


def check_step(obj: object, where: str, issues: list | None = None) -> tuple:
    """A step a lead cannot run (#674): (clean step, []) or (None, errors). Unknown keys are dropped."""
    if not isinstance(obj, dict):  # O(1)
        return None, [f"{where}: not an object"]
    errs: list[str] = []
    out: dict = {}
    if issues is not None:
        got = obj.get("issues")
        if (not isinstance(got, list) or not got or not all(isinstance(i, int) and not isinstance(i, bool) and i in issues for i in got)):  # O(len * issues)
            errs.append(f"{where} issues: a non-empty list of this batch's issues")
        else:
            out["issues"] = got
    if not isinstance(obj.get("runs"), str) or obj["runs"] not in RUNS:  # O(1)
        errs.append(f"{where} runs: main or user")
    else:
        out["runs"] = obj["runs"]
    if not _line(obj.get("command"), 300, 1):  # O(len)
        errs.append(f"{where} command: 1 to 300 characters, one line")
    else:
        out["command"] = obj["command"]
    if "why" in obj:
        if not _line(obj["why"], 200, 0):  # O(len)
            errs.append(f"{where} why: 0 to 200 characters, one line")
        else:
            out["why"] = obj["why"]
    return (None, errs) if errs else (out, [])


def step_line(step: dict) -> str:
    return f"{RUNS[step['runs']]} runs this: {step['command']}"  # O(1)


def ask_shape(q: dict) -> tuple:
    """The question without the step keys of its options (AskUserQuestion rejects them) and one line per option that had a step."""
    out = copy.deepcopy(q)
    lines: list[str] = []
    for e in as_batch(out).get("questions", []):  # O(questions * options)
        for o in e.get("options", []):
            r, c = o.pop("runs", None), o.pop("command", None)
            if isinstance(r, str) and r in RUNS and isinstance(c, str):  # O(1)
                lines.append(f'step: "{_word(e.get("question", ""), 60)}" / "{o.get("label", "")}": {step_line({"runs": r, "command": c})}')
    return out, lines


def as_batch(q):
    """A bare question object {"question", "header", "options"} becomes {"questions": [q]}; anything else passes through."""
    if isinstance(q, dict) and "questions" not in q and "question" in q:  # O(1)
        return {"questions": [q]}
    return q


def _word(v: str, hi: int) -> str:
    """v cut to at most hi characters at its last blank, trailing blanks and ,;:- dropped (#370).

    A first word longer than hi, or a cut that would leave only those characters, falls back to the plain cut."""
    head = v[:hi]  # O(hi)
    if len(v) > hi and not v[hi].isspace():  # O(1) the cut falls inside a word
        m = re.search(r"\s\S*\Z", head)  # O(hi) the last blank
        if m and head[:m.start()].strip():  # O(hi)
            head = head[:m.start()]  # O(hi)
    return head.rstrip(" \t\n,;:-") or v[:hi].rstrip()  # O(hi)


def _cut(v: str, hi: int, word: bool = False) -> str:
    cut = _word if word else (lambda s, n: s[:n].rstrip())  # O(1)
    if v.endswith(REC) and hi > len(REC):  # O(len)
        return cut(v[:len(v) - len(REC)], hi - len(REC)) + REC  # O(hi)
    return cut(v, hi)  # O(hi)


def _fit(holder: dict, key: str, hi: int, name: str, what: str, notes: list) -> None:
    v = holder.get(key)
    if not isinstance(v, str) or len(v) <= hi:  # O(1)
        return
    c = _cut(v, hi)
    if c.strip():
        holder[key] = c
        notes.append(f'"{name}" {what}: {len(v)} -> {len(c)} characters')


def _fit_label(o: dict, name: str, what: str, notes: list) -> None:
    """Cut an over-long option label (60) at its last whole word; its full text, without the ` (Recommended)` suffix, goes in front of the description (#370)."""
    v = o.get("label")
    if not isinstance(v, str) or len(v) <= 60:  # O(1)
        return
    c = _cut(v, 60, word=True)  # O(len)
    if not c.strip():  # O(len)
        return
    o["label"] = c
    full = (v[:len(v) - len(REC)] if v.endswith(REC) else v).strip()  # O(len)
    d = o.get("description")
    if full and (d is None or isinstance(d, str)):  # O(1) a non-string description stays for check_question to refuse
        rest = (d or "").lstrip()  # O(len)
        o["description"] = full + (("" if full[-1] in ".!?:" else ".") + " " + rest if rest.strip() else "")  # O(len)
    notes.append(f'"{name}" {what}: {len(v)} -> {len(c)} characters')


def fit_question(q: object, question: bool = False) -> list[str]:
    """Cut an over-long question (300, only with question=True), header (12), option label (60) and option description (200) of a question batch in place.

    q is {"questions": [...]} or a bare question object (cut in the caller's dict). Returns one note per cut. An over-long label is cut at its last whole word (a " (Recommended)" suffix kept) and its full text goes in front of its description, which is then cut to 200. A cut that would leave only blanks is not made. The question text is
    cut only with question=True, which plan uses; a lead's question keeps its text because main answers it by that
    text. Every other error, and every unknown key, is left alone for check_question."""
    notes: list[str] = []
    qs = as_batch(q).get("questions") if isinstance(q, dict) else None
    for e in qs if isinstance(qs, list) else []:  # O(questions * options)
        if not isinstance(e, dict):
            continue
        t = e.get("question")
        name = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", t).split())[:60] if isinstance(t, str) else "?"
        if question:
            _fit(e, "question", 300, name, "question", notes)
        _fit(e, "header", 12, name, "header", notes)
        opts = e.get("options")
        for n, o in enumerate(opts if isinstance(opts, list) else [], 1):
            if isinstance(o, dict):
                _fit_label(o, name, f"option {n} label", notes)
                _fit(o, "description", 200, name, f"option {n} description", notes)
    return notes


def cut_lines(notes: list[str], prefix: str = "") -> list[str]:
    """One `<prefix>shortened: <note>` line per cut note, at most 5, then `<prefix>shortened: N more`."""
    lines = [f"{prefix}shortened: {n}" for n in notes[:5]]  # O(1)
    if len(notes) > 5:
        lines.append(f"{prefix}shortened: {len(notes) - 5} more")
    return lines


def _fit_topic(b: dict, k: int, notes: list) -> None:
    """Cut a topic over 40 characters at its last dash (plain cut without one); the note names the batch id, or `batch k` (#483)."""
    v = b.get("topic")
    if not isinstance(v, str) or len(v) <= 40:  # O(1)
        return
    head = v[:40]  # O(1)
    c = head.rsplit("-", 1)[0] if v[40] != "-" and "-" in head else head  # O(1)
    c = c.rstrip("-") or head.rstrip("-")  # O(1)
    if not c:
        return
    b["topic"] = c
    bid = b.get("id")
    notes.append(f'"{bid if isinstance(bid, str) else f"batch {k}"}" topic: {len(v)} -> {len(c)} characters')  # O(1)


def topic_slug(text: str) -> str:
    """text as a topic: lowercase words joined by -, at most 40 characters, cut at the last whole word; "" when no word is left."""
    v = re.sub(r"[^a-z0-9]+", "-", str(text).lower()).strip("-")  # O(len)
    if len(v) <= 40:  # O(1)
        return v  # O(1)
    head = v[:40]  # O(1)
    c = head.rsplit("-", 1)[0] if v[40] != "-" and "-" in head else head  # O(1)
    return c.strip("-") or head.strip("-")  # O(1)


def normalise_topics(obj: object) -> list[str]:
    """Rewrite every topic that is not already a valid one to its slug, in place; one `topic: "<id>" "<old>" -> <new>` note per rewrite."""
    notes: list[str] = []
    batches = obj.get("batches") if isinstance(obj, dict) else None
    for k, b in enumerate(batches if isinstance(batches, list) else [], 1):  # O(batches * len)
        t = b.get("topic") if isinstance(b, dict) else None
        if not isinstance(t, str) or TOPIC_RE.fullmatch(t):  # O(1)
            continue
        new = topic_slug(t)  # O(len)
        if not new:  # O(1)
            continue
        bid = b.get("id")
        bid = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", bid).split()) if isinstance(bid, str) else bid
        old = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", t).split())[:60]  # O(len)
        b["topic"] = new
        notes.append(f'topic: "{bid if isinstance(bid, str) else f"batch {k}"}" "{old}" -> {new}')  # O(1)
    return notes


def fit_proposal(obj: object) -> list[str]:
    """Cut an over-long question (300), header (12), option label (60) and option description (200) in place; return one note per cut.

    Uses fit_question(question=True) for every decision. An over-long label is cut at its last whole word (a " (Recommended)" suffix kept) and its full text goes in front of its description, which is then cut to 200. A cut that would leave
    only blanks is not made. Every other error, and every unknown key, is left alone for check_proposal."""
    notes: list[str] = []
    batches = obj.get("batches") if isinstance(obj, dict) else None
    for k, b in enumerate(batches if isinstance(batches, list) else [], 1):  # O(batches * decisions * options)
        if isinstance(b, dict):
            _fit_topic(b, k, notes)  # O(len)
        decisions = b.get("decisions") if isinstance(b, dict) else None
        for d in decisions if isinstance(decisions, list) else []:
            notes += fit_question(d, question=True)
    return notes


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
            for n, o in enumerate(opts, 1):  # O(options)
                if not isinstance(o, dict):
                    errs.append(f"{p} options: not an object")
                    continue
                if _text(errs, f"{p} options label", o.get("label"), 1, 60, "label 1 to 60 characters"):
                    if o["label"] in labels:
                        errs.append(f"{p} options: duplicate label {o['label']}")
                    labels.add(o["label"])
                _text(errs, f"{p} options description", o.get("description", ""), 0, 200, "description 0 to 200 characters")
                if "runs" in o or "command" in o:
                    errs.extend(check_step({k: o[k] for k in ("runs", "command") if k in o}, f"{p} option {n}")[1])  # O(1)
        if "multiSelect" in e and not isinstance(e["multiSelect"], bool):
            errs.append(f"{p} multiSelect: true or false")
    return errs


def clean_question(q: dict) -> dict:
    """Rebuild a question that check_question accepted from its validated fields only: unknown keys never pass."""
    out = []
    for e in as_batch(q)["questions"]:  # O(4 * options)
        c = {"question": e["question"], "header": e["header"],
             "options": [{k: o[k] for k in ("label", "description", "runs", "command") if k in o} for o in e["options"]]}
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


def check_proposal(obj: dict, known: set, batches: frozenset = frozenset()) -> tuple[list[dict], list[str]]:
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
        if not isinstance(bid, str) or not ID_RE.fullmatch(bid):
            errs.append(f"batch {n}: id must be B<n>, B1 to B999999 (got {bid!r})")
            continue
        if bid in ids:
            errs.append(f"{bid}: duplicate id")
            continue
        ids.add(bid)
        topic = b.get("topic")
        if not isinstance(topic, str) or not TOPIC_RE.fullmatch(topic):
            errs.append(f"{bid}: topic must be lowercase words joined by -, at most 40 characters")
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
        app = b.get("append_only", [])
        aclean: set = set()
        if not isinstance(app, list):
            errs.append(f"{bid}: append_only must be a list")
            app = []
        for f in app:
            p = _plain(f)
            if p is None:
                errs.append(f"{bid}: append_only file {f!r} is not a plain relative path")
            else:
                aclean.add(p)
        clean |= aclean  # an append-only file is also a batch file
        deps = b.get("depends", [])
        if not isinstance(deps, list) or not all(isinstance(d, str) for d in deps):
            errs.append(f"{bid}: depends must be a list of batch ids")
            deps = []
        decisions = b.get("decisions", [])
        if not isinstance(decisions, list):
            errs.append(f"{bid}: decisions must be a list")
            decisions = []
        steps = b.get("main_steps", [])
        if not isinstance(steps, list):
            errs.append(f"{bid}: main_steps must be a list")
            steps = []
        elif len(steps) > 8:
            errs.append(f"{bid}: main_steps: at most 8 entries")
            steps = []
        scl = []
        for k, st in enumerate(steps, 1):
            c, bad = check_step(st, f"{bid} main_steps {k}", sorted(set(issues)))
            errs.extend(bad)
            if c:
                scl.append(c)
        cleaned = []
        for k, d in enumerate(decisions, 1):
            bad = check_question(d)
            errs.extend(f"{bid} decision {k}: {e}" for e in bad)
            if not bad:
                cleaned.append(clean_question(d))
        out.append({"id": bid, "topic": topic, "issues": sorted(set(issues)), "files": sorted(clean), **({"append_only": sorted(aclean)} if aclean else {}),
                    **({"main_steps": scl} if scl else {}),
                    "depends": list(dict.fromkeys(deps)), "decisions": cleaned, **copy.deepcopy(DEFAULTS)})
    for b in out:  # O(batches * deps)
        for d in b["depends"]:
            if (d not in ids and d not in batches) or d == b["id"]:  # local ids win over backlog ids
                errs.append(f"{b['id']}: depends on unknown batch {d}" if d not in ids and d not in batches else f"{b['id']}: depends on itself")
    if not errs:
        r = _reach(out)
        cyc = sorted(k for k, v in r.items() if k in v)
        if cyc:
            errs.append("dependency cycle: " + " ".join(cyc))
    return ([], errs) if errs else (out, [])


def _num(b: dict) -> int:
    return int(b["id"][1:])


def serial_files(a: dict, b: dict) -> list[str]:
    """Files both batches list, minus those both only append to."""
    return sorted((set(a.get("files") or []) & set(b.get("files") or [])) - (set(a.get("append_only") or []) & set(b.get("append_only") or [])))  # O(files)


def appended_files(a: dict, b: dict) -> list[str]:
    """Files both batches list and both only append to."""
    return sorted(set(a.get("files") or []) & set(b.get("files") or []) & set(a.get("append_only") or []) & set(b.get("append_only") or []))  # O(files)


def separate(batches: list[dict]) -> list[dict]:
    bs = sorted(copy.deepcopy(batches), key=_num)  # O(n log n)
    while True:  # O(n^3) worst case, n <= 20
        r = _reach(bs)
        pair = None
        for i, a in enumerate(bs):
            for b in bs[i + 1:]:
                cyc = b["id"] in r[a["id"]] and a["id"] in r[b["id"]]
                clash = serial_files(a, b) and b["id"] not in r[a["id"]] and a["id"] not in r[b["id"]]
                if cyc or clash:
                    pair = (a, b)
                    break
            if pair:
                break
        if not pair:
            return bs
        a, b = pair
        a["issues"] = sorted(set(a["issues"]) | set(b["issues"]))
        fa, fb, oa, ob = set(a["files"]), set(b["files"]), set(a.get("append_only") or []), set(b.get("append_only") or [])
        app = (oa - (fb - ob)) | (ob - (fa - oa))  # a file the other side rewrites stops being append-only
        a["files"] = sorted(fa | fb)
        if app:
            a["append_only"] = sorted(app)
        else:
            a.pop("append_only", None)
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


def _ref(i):
    """A left-out issue ref as a number or an upper-case key; None for anything else (bool included)."""
    if isinstance(i, int) and not isinstance(i, bool):  # O(1)
        return i
    if not isinstance(i, str):  # O(1)
        return None
    t = i.strip().lstrip("#")  # O(len)
    return int(t) if t.isdigit() else (t.upper() or None)  # O(len)


def left_out_reasons(obj: object, known: set) -> dict:
    """{issue: reason} from a proposal's `left_out` list ({"issues": [...], "reason": "..."} entries); the first reason per issue wins.

    A reason loses control characters and runs of blanks and is cut to 60 characters at a whole word. Entries that are not objects, a non-list `issues`, a non-string or blank reason, and issues not in known are ignored."""
    out: dict = {}
    entries = obj.get("left_out") if isinstance(obj, dict) else None
    for e in entries if isinstance(entries, list) else []:  # O(entries * issues)
        if not isinstance(e, dict) or not isinstance(e.get("issues"), list) or not isinstance(e.get("reason"), str):  # O(1)
            continue
        r = " ".join(re.sub(r"[\x00-\x1f\x7f]", " ", e["reason"]).split())  # O(len)
        if not r:
            continue
        r = _word(r, 60)  # O(len)
        for i in e["issues"]:
            n = _ref(i)
            if n is not None and n in known and n not in out:  # O(1)
                out[n] = r
    return out


BY_MISSING = ('by: missing; name who answered: "by": "user" for AskUserQuestion answers, "by": "main" for main\'s rulings, '
              'or a {question: "user"|"main"} map naming every answered question')
BY_ERR = 'by: "user", "main" or a {question: "user"|"main"} map'


def answer_by(obj: dict, answers: dict) -> tuple[dict, str]:
    if not isinstance(obj, dict) or "by" not in obj:  # O(1)
        return {}, BY_MISSING  # O(1)
    by = obj["by"]  # O(1)
    if isinstance(by, str) and by in ("user", "main"):  # O(1)
        return {q: by for q in answers}, ""  # O(answers)
    if not isinstance(by, dict) or any(v not in ("user", "main") for v in by.values()):  # O(by)
        return {}, BY_ERR  # O(1)
    for q in by:  # O(by)
        if q not in answers:
            return {}, f"by: no answer for {q}"  # O(1)
    for q in answers:  # O(answers)
        if q not in by:  # O(1)
            return {}, "by: the map names no one for " + "".join("?" if _ctrl(c) else c for c in str(q))[:60]  # O(len)
    return {q: by[q] for q in answers}, ""  # O(answers)