#!/usr/bin/env python3
"""Workers, test runs and a quality grade read from one lead worktree's `.superlite` (#680).

    workers(sd, prices)  -> {role: {"n", "tokens", "cost_usd"}}   (the lead is not a worker)
    test_runs(sd)        -> {"full", "full_min", "fast", "fast_min"}
    quality(sd)          -> tasks, first_time_pass, package_findings, final_rounds, final_verdicts, fixer_rounds
    grade(quality, batch)-> quality plus ci_red, ship_reruns, ship_waits, questions, points, letter
    snapshot(sd, prices) -> {"workers", "tests", "quality"}; every reader returns its empty value for a missing folder.
"""
# Complexity notation:
#   A = agent ids, M = metrics lines, B = bytes of transcripts, R = report files, S = test summaries
import json  # O(1)
import re  # O(1)
from pathlib import Path  # O(1)

import metrics  # O(1)

TOKENS = ("input", "cache_read", "cache_write", "output", "thinking")  # O(1)
SUFFIXES = ("-sonnet-high", "-sonnet", "-opus", "-haiku")  # O(1)
FIXER_LABEL = re.compile(r"^F-(.+)-\d+$")  # O(1)
FR_LABEL = re.compile(r"^FR(\d+)$")  # O(1)
DONE = ("DONE", "DONE_WITH_CONCERNS")  # O(1)


def _json(p):  # a dict from a JSON file, else None | O(file)
    try:  # O(1)
        d = json.loads(Path(p).read_text(encoding="utf-8"))  # O(file)
    except (OSError, ValueError):  # O(1)
        return None  # O(1)
    return d if isinstance(d, dict) else None  # O(1)


def _role(typ):  # the role named by an agent type | O(len)
    t = str(typ or "")  # O(1)
    for pre in ("fleet:", "superlite:"):  # O(1)
        t = t.removeprefix(pre)  # O(1)
    for suf in SUFFIXES:  # O(1)
        if t.endswith(suf):  # O(1)
            t = t[: -len(suf)]  # O(1)
            break  # O(1)
    return t or "other"  # O(1)


def workers(sd, prices=None) -> dict:  # O(M + A + B)
    sd = Path(sd)  # O(1)
    roles: dict = {}  # agent id -> role | O(1)
    trs: dict = {}  # agent id -> (t, transcript) | O(1)
    d = _json(sd / "fleet.json")  # O(file)
    ws = d.get("workers") if d else None  # O(1)
    for wid, w in (ws.items() if isinstance(ws, dict) else []):  # O(A)
        if isinstance(w, dict) and w.get("role"):  # O(1)
            roles[str(wid)] = str(w["role"])  # O(1)
        else:  # O(1)
            roles.setdefault(str(wid), "")  # O(1)
    lines: list = []  # O(1)
    seen: set = set()  # identical records in the live file and the archives count once | O(1)
    for f in [sd / "metrics.jsonl", *sorted(sd.glob("runs/*/metrics.jsonl"))]:  # O(F)
        try:  # O(1)
            fl = f.read_text(encoding="utf-8", errors="replace").splitlines()  # O(M)
        except OSError:  # O(1)
            continue  # O(1)
        for ln in fl:  # O(M)
            if ln not in seen:  # O(1)
                seen.add(ln)  # O(1)
                lines.append(ln)  # O(1)
    for ln in lines:  # O(M)
        try:  # O(1)
            e = json.loads(ln)  # O(line)
        except ValueError:  # O(1)
            continue  # O(1)
        aid = e.get("agent_id") if isinstance(e, dict) else None  # O(1)
        if not aid or e.get("ev") not in ("launch", "stop"):  # O(1)
            continue  # O(1)
        aid = str(aid)  # O(1)
        if not roles.get(aid):  # O(1)
            roles[aid] = _role(e.get("type")) if e.get("type") else roles.get(aid, "")  # O(1)
        if e.get("ev") == "stop" and e.get("transcript") and isinstance(e.get("t"), (int, float)):  # O(1)
            if aid not in trs or e["t"] >= trs[aid][0]:  # O(1)
                trs[aid] = (e["t"], str(e["transcript"]))  # O(1)
    out: dict = {}  # O(1)
    for aid in sorted(roles):  # O(A)
        role = roles[aid] or "other"  # O(1)
        if role == "lead":  # O(1)
            continue  # O(1)
        slot = out.setdefault(role, {"n": 0, "tokens": dict.fromkeys(TOKENS, 0), "cost_usd": 0.0})  # O(1)
        slot["n"] += 1  # O(1)
        if aid in trs:  # O(1)
            try:  # O(1)
                u = metrics.session_usage(trs[aid][1], prices=prices, sidechain=True)  # O(B)
            except Exception:  # an unreadable transcript counts the worker, not its tokens | O(1)
                continue  # O(1)
            for k in TOKENS:  # O(1)
                slot["tokens"][k] += int((u.get("tokens") or {}).get(k) or 0)  # O(1)
            slot["cost_usd"] += float(u.get("cost_usd") or 0.0)  # O(1)
    for slot in out.values():  # O(roles)
        slot["cost_usd"] = round(slot["cost_usd"], 6)  # O(1)
    return out  # O(1)


def test_runs(sd) -> dict:  # O(S)
    out = {"full": 0, "full_min": 0.0, "fast": 0, "fast_min": 0.0}  # O(1)
    files: dict = {}  # file name -> path, deduped by name | O(1)
    for p in [*Path(sd).glob("test-summary-*.json"), *Path(sd).glob("runs/*/test-summary-*.json")]:  # `test-summary.json` is the newest run's copy | O(S)
        files.setdefault(p.name, p)  # O(1)
    for _, p in sorted(files.items()):  # O(S log S)
        d = _json(p)  # O(file)
        if not d or d.get("mode") not in ("full", "fast"):  # O(1)
            continue  # O(1)
        m = d["mode"]  # O(1)
        out[m] += 1  # O(1)
        s = d.get("seconds")  # O(1)
        out[m + "_min"] += (s if isinstance(s, (int, float)) and not isinstance(s, bool) else 0) / 60  # O(1)
    out["full_min"], out["fast_min"] = round(out["full_min"], 2), round(out["fast_min"], 2)  # O(1)
    return out  # O(1)


def _count(v) -> int:  # findings as an int or a list | O(1)
    if isinstance(v, list):  # O(1)
        return len(v)  # O(1)
    return v if isinstance(v, int) and not isinstance(v, bool) else 0  # O(1)


def quality(sd) -> dict:  # O(R)
    tasks: dict = {}  # task id -> DONE report | O(1)
    fixed: set = set()  # tasks with a fixer label | O(1)
    pkg = fixer = 0  # O(1)
    finals: dict = {}  # round -> verdict | O(1)
    for p in sorted((Path(sd) / "fleet" / "reports").glob("*.json")):  # O(R log R)
        r = _json(p)  # O(file)
        if not r:  # O(1)
            continue  # O(1)
        label, role = str(r.get("label") or ""), str(r.get("role") or "")  # O(1)
        fm = FIXER_LABEL.match(label)  # O(1)
        if fm:  # O(1)
            fixed.add(fm.group(1))  # O(1)
            fixer += 1  # O(1)
        elif role == "implementer":  # O(1)
            for t in (x.strip() for x in label.split(",")):  # O(k)
                if t:  # O(1)
                    tasks[t] = r.get("status") in DONE  # O(1)
        if role == "package-reviewer" or label.startswith("review-"):  # O(1)
            pkg += _count(r.get("findings"))  # O(1)
        m = FR_LABEL.match(label)  # O(1)
        if m:  # O(1)
            finals[int(m.group(1))] = str(r.get("status") or "UNKNOWN")  # O(1)
    return {"tasks": len(tasks), "first_time_pass": sum(1 for t, ok in tasks.items() if ok and t not in fixed),
            "package_findings": pkg, "final_rounds": len(finals),
            "final_verdicts": [finals[k] for k in sorted(finals)], "fixer_rounds": fixer}  # O(R)


def _int(v) -> int:  # O(1)
    return v if isinstance(v, int) and not isinstance(v, bool) else 0  # O(1)


def grade(quality: dict, batch: dict) -> dict:  # O(1)
    q, b = quality or {}, batch or {}  # O(1)
    out = {"tasks": _int(q.get("tasks")), "first_time_pass": _int(q.get("first_time_pass")),
           "package_findings": _int(q.get("package_findings")), "final_rounds": _int(q.get("final_rounds")),
           "final_verdicts": list(q.get("final_verdicts") or []), "fixer_rounds": _int(q.get("fixer_rounds")),
           "ci_red": _int(b.get("ship_reds")), "ship_reruns": _int(b.get("ship_runs")),
           "ship_waits": _int(b.get("ship_waits")), "questions": _int(b.get("questions"))}  # O(1)
    pts = (max(out["tasks"] - out["first_time_pass"], 0) + out["package_findings"] + max(out["final_rounds"] - 1, 0)
           + out["fixer_rounds"] + 2 * out["ci_red"] + out["ship_reruns"] + out["questions"])  # O(1)
    out["points"] = pts  # O(1)
    out["letter"] = "A" if pts == 0 else "B" if pts <= 3 else "C" if pts <= 7 else "D"  # O(1)
    return out  # O(1)


def snapshot(sd, prices=None) -> dict:  # O(M + A + B + R + S)
    return {"workers": workers(sd, prices), "tests": test_runs(sd), "quality": quality(sd)}  # O(M + A + B + R + S)
