#!/usr/bin/env python3
"""Golden run: score and run golden cases against sealed clones, append rows to the results file.

golden.py run [--level minor|major | --ids a,b] [--no-rerun] [--timeout S] [--root R]
golden.py history [ID]
"""

from __future__ import annotations

import argparse
import json
import os
import re
import shlex
import shutil
import statistics
import subprocess
import sys
import tempfile
import threading
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import golden_case  # noqa: E402
import golden_seal  # noqa: E402

LEVELS = {"minor": ["small", "typical"], "major": ["small", "typical", "large"]}
SLICE_S = 300  # wait slice, so a runaway lead cost can end a case early
TEST_TIMEOUT = 900  # the hidden tests may not hang a case
COST_CAP = 3  # a lead cost above 3x baseline ends the case
WARN_X = 2  # a lead cost or turn count above 2x baseline warns


# the lead stopped at the ship block: "ship not approved", "shipping is not approved", "ship is not yet approved", "ship approval missing"
SHIP_STOP = re.compile(r"\bship[^.!?\n]{0,60}approv|approv[^.!?\n]{0,60}\bship", re.I)  # a sealed run is never approved: shipping and approval named close together, in either order, is the ship stop
HIDDEN_TAIL = 1200  # chars of a red hidden run's output kept in the row


def _run(cmd: list, cwd=None, timeout=None) -> tuple[int, str]:
    try:  # O(1)
        r = subprocess.run(cmd, cwd=str(cwd) if cwd else None, capture_output=True, text=True, encoding="utf-8",
                           errors="replace", timeout=timeout)  # O(cmd)
    except (OSError, subprocess.TimeoutExpired) as e:  # O(1)
        return 127, str(e)  # O(1)
    return r.returncode, (r.stdout + r.stderr).strip()  # O(out)


def score(case: dict, facts: dict) -> dict:
    row = facts.get("row")  # O(1)
    why, warn = [], []  # O(1)
    state, reason = facts.get("state", ""), facts.get("reason", "") or ""  # O(1)
    if state == "timeout":  # O(1)
        why.append("timeout")  # O(1)
    elif (state == "parked" or reason.startswith("BLOCKED")) and not SHIP_STOP.search(reason):  # O(1)
        why.append(f"lead ended: {reason}")  # O(1)
    elif state in ("needs_decision", "error"):  # O(1)
        why.append(f"lead ended: {state} {reason}".rstrip())  # O(1)
    if row is None and state != "timeout":  # O(1)
        why.append("no cost row")  # O(1)
    hid = facts.get("hidden")  # the hidden tests are a score, never a gate | O(1)
    suite = facts.get("suite")  # O(1)
    row = row or {}  # O(1)
    lead = row.get("lead") or {}  # O(1)
    lead_usd = float(lead.get("cost_usd", 0) or 0)  # O(1)
    turns = int(lead.get("turns", 0) or 0)  # O(1)
    total = lead_usd + float((row.get("workers_total") or {}).get("cost_usd", 0) or 0)  # O(1)
    if row:  # O(1)
        if not (row.get("grade") or {}).get("tasks"):  # O(1)
            why.append("no plan tasks")  # O(1)
        if not (row.get("grade") or {}).get("final_rounds"):  # O(1)
            why.append("no final review")  # O(1)
        if not (row.get("tests") or {}).get("full"):  # O(1)
            why.append("suite never ran")  # O(1)
        if state != "timeout":  # the full suite at the end of the lead's run: a fact of the run, not the lead's words | O(1)
            if suite and suite.get("failed", 0) > 0:  # O(1)
                why.append("suite red")  # O(1)
            elif not suite or not suite.get("passed", 0):  # O(1)
                why.append("no green full suite run")  # O(1)
    base = case.get("baseline") or {}  # O(1)
    if base.get("lead_usd") and lead_usd > WARN_X * base["lead_usd"]:  # O(1)
        warn.append(f"lead cost {lead_usd:.2f} above {WARN_X}x baseline {base['lead_usd']:.2f}")  # O(1)
    if base.get("lead_turns") and turns > WARN_X * base["lead_turns"]:  # O(1)
        warn.append(f"lead turns {turns} above {WARN_X}x baseline {base['lead_turns']}")  # O(1)
    res = {"passed": not why, "why": why, "warn": warn, "lead_usd": round(lead_usd, 2), "total_usd": round(total, 2),
           "lead_turns": turns, "wall_min": round(float(lead.get("wall_s", 0) or 0) / 60, 1)}  # O(1)
    if hid is not None:  # O(1)
        res["hidden_share"] = share = hidden_share(hid)  # O(1)
        earlier = facts.get("earlier") or []  # the shares of this case's earlier started runs | O(runs)
        if earlier and share < min(earlier):  # O(runs)
            warn.append(f"hidden tests {share:.2f} below earlier runs (lowest {min(earlier):.2f})")  # O(1)
    if suite is not None:  # O(1)
        res["suite"] = {"passed": suite.get("passed", 0), "failed": suite.get("failed", 0)}  # O(1)
    return res  # O(1)


def hidden_share(hid) -> float:  # passed / (passed + failed + errors), 0.0 when nothing ran or could not collect | O(1)
    hid = hid or {}  # O(1)
    n = hid.get("passed", 0)  # O(1)
    total = n + hid.get("failed", 0) + hid.get("errors", 0)  # O(1)
    return round(n / total, 2) if total else 0.0  # O(1)


def _earlier(out: Path, cid: str) -> list:  # hidden shares of the case's earlier started runs in the results file | O(lines)
    shares = []  # O(1)
    try:  # O(1)
        lines = Path(out).read_text(encoding="utf-8", errors="replace").splitlines()  # O(size)
    except OSError:  # O(1)
        return shares  # O(1)
    for ln in lines:  # O(lines)
        try:  # a torn line never ends a run | O(1)
            r = json.loads(ln) if ln.strip() else None  # O(len)
        except ValueError:  # O(1)
            continue  # O(1)
        v = r.get("hidden_share") if isinstance(r, dict) else None  # O(1)
        if isinstance(r, dict) and r.get("row") == "golden" and r.get("case") == cid and r.get("started", True) and isinstance(v, (int, float)) and not isinstance(v, bool):  # O(1)
            shares.append(float(v))  # O(1)
    return shares  # O(1)


def _count(out: str, word: str) -> int:
    m = re.search(rf"(\d+) {word}", out)  # O(out)
    return int(m.group(1)) if m else 0  # O(1)


def hidden_run(case: dict, wt) -> dict:
    paths = []  # O(1)
    for t in case.get("hidden_tests", []):  # O(tests)
        p = Path(wt) / t["path"]  # O(1)
        p.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        p.write_text(t["text"], encoding="utf-8", newline="\n")  # O(size)
        paths.append(t["path"])  # O(1)
    code, out = _run(shlex.split(case["test_cmd"]) + paths, cwd=wt, timeout=TEST_TIMEOUT)  # O(tests)
    return {"ok": golden_case.tests_green(code, out), "exit": code, "passed": _count(out, "passed"), "failed": _count(out, "failed"),
            "skipped": _count(out, "skipped"), "errors": _count(out, "errors?"), "out": out[-HIDDEN_TAIL:]}  # tests_green is the check golden_case verify uses | O(out)


def hidden_ok(case: dict, wt) -> bool:
    return hidden_run(case, wt)["ok"]  # O(tests)


def _plugin(src: Path) -> str:
    try:  # O(1)
        v = json.loads((Path(src) / ".claude-plugin" / "plugin.json").read_text()).get("version", "?")  # O(1)
    except (OSError, ValueError):  # O(1)
        v = "?"  # O(1)
    code, sha = _run(["git", "rev-parse", "--short", "HEAD"], cwd=src)  # O(1)
    return f"{v}+{sha.strip()}" if code == 0 and sha.strip() else v  # O(1)


ABORT = threading.Event()  # set on Ctrl-C: waits end at their next slice


def _await(seal, clone: Path, case: dict, timeout_s: int) -> dict:
    left = timeout_s  # O(1)
    cap = (case.get("baseline") or {}).get("lead_usd", 0) * COST_CAP  # O(1)
    while True:  # O(timeout/slice)
        res = seal.wait(clone, min(SLICE_S, max(left, 1)))  # O(1)
        if res.get("state") != "timeout":  # O(1)
            return res  # O(1)
        left -= SLICE_S  # O(1)
        live = getattr(seal, "lead_cost", None)  # the batch row exists only after the lead stopped | O(1)
        spent = live(clone) if live else float(((seal.row(clone) or {}).get("lead") or {}).get("cost_usd", 0) or 0)  # O(1)
        over = cap and spent > cap  # O(1)
        if left <= 0 or over or ABORT.is_set():  # O(1)
            return res  # O(1)


PATCH_CAP = 2 * 1024 * 1024  # bytes of a saved patch file


def _save_patch(seal, case: dict, wt, out_dir, n: int) -> str:  # the lead's change, saved before the clone goes | O(diff)
    fn = getattr(seal, "patch", None)  # O(1)
    if not fn or not wt or out_dir is None:  # O(1)
        return ""  # O(1)
    try:  # a patch never ends a run | O(1)
        text = fn(wt, case.get("base", "")) or ""  # O(diff)
        if not text:  # O(1)
            return ""  # O(1)
        raw = text.encode("utf-8", errors="replace")  # O(diff)
        if len(raw) > PATCH_CAP:  # O(1)
            text = raw[:PATCH_CAP].decode("utf-8", errors="ignore").rsplit("\n", 1)[0] + "\n... cut\n"  # O(diff)
        name = f"{case['id']}-{n}.patch"  # O(1)
        d = Path(out_dir) / "golden"  # O(1)
        d.mkdir(parents=True, exist_ok=True)  # O(1)
        (d / name).write_text(text, encoding="utf-8", newline="\n")  # O(diff)
        return name  # O(1)
    except Exception:  # noqa: BLE001 | O(1)
        return ""  # O(1)


def _attempt(case: dict, src: Path, work: Path, timeout_s: int, seal, n: int, plugin: str, out_dir=None, earlier=None) -> dict:
    clone = None  # O(1)
    try:  # O(1)
        clone = seal.seal(case, src, work)  # O(clone)
        st = seal.start(clone)  # O(1)
        if not st.get("ok"):  # O(1)
            res = {"passed": False, "why": [f"lead did not start: {st.get('out', '')}"], "warn": [], "lead_usd": 0.0,
                   "total_usd": 0.0, "lead_turns": 0, "wall_min": 0.0, "started": False}  # O(1)
        else:  # O(1)
            w = _await(seal, clone, case, timeout_s)  # O(timeout)
            wt = seal.worktree(clone)  # O(1)
            patch_name = _save_patch(seal, case, wt, out_dir, n) if w.get("state") != "timeout" else ""  # before the hidden tests are written | O(diff)
            hid = hidden_run(case, wt) if w.get("state") in ("parked", "done") and wt else None  # hidden tests only after the lead stopped | O(tests)
            brow = seal.row(clone)  # O(1)
            suite_fn = getattr(seal, "suite", None)  # the lead's last full-suite summary, read before cleanup | O(1)
            suite = suite_fn(clone) if suite_fn and w.get("state") != "timeout" else None  # O(1)
            res = {**score(case, {"state": w.get("state"), "reason": w.get("reason", ""), "row": brow, "hidden": hid, "suite": suite, "earlier": earlier}), "started": True}  # O(1)
            if hid:  # the facts of the hidden run, so a red one can be diagnosed | O(1)
                res["hidden"] = {k: hid[k] for k in ("exit", "passed", "failed", "skipped", "errors")}  # O(1)
                if not hid["ok"]:  # O(1)
                    res["hidden_out"] = hid["out"]  # O(1)
            if patch_name:  # O(1)
                res["patch"] = patch_name  # O(1)
            elif w.get("state") in ("parked", "done") and wt and out_dir is not None and getattr(seal, "patch", None):  # a stopped lead should leave a change: the gap shows | O(1)
                res["patch"] = ""  # O(1)
                why_fn = getattr(seal, "patch_error", None)  # O(1)
                reason = (why_fn(wt) if why_fn else "") or ""  # O(1)
                res["warn"] = [*res["warn"], f"no patch saved: {reason}" if reason else "no patch saved"]  # O(1)
            if not brow:  # no batch row yet (timeout, cost cap): the lead's cost so far, read before cleanup | O(1)
                live = getattr(seal, "lead_cost", None)  # O(1)
                spent = float(live(clone) or 0) if live else 0.0  # O(1)
                if spent > 0:  # O(1)
                    res["lead_usd"], res["total_usd"] = round(spent, 2), round(max(res["total_usd"], spent), 2)  # O(1)
    finally:  # O(1)
        if clone is not None:  # O(1)
            seal.cleanup(clone)  # O(1)
    return {"v": 1, "row": "golden", "case": case["id"], "attempt": n, **res, "plugin": plugin}  # O(1)


def _case(case: dict, src: Path, work: Path, rerun: bool, timeout_s: int, seal, plugin: str, out_dir=None, earlier=None) -> list:
    rows = []  # O(1)
    for n in (1, 2) if rerun else (1,):  # O(2)
        if ABORT.is_set():  # O(1)
            break  # O(1)
        rows.append(_attempt(case, src, work / f"{case['id']}-{n}", timeout_s, seal, n, plugin, out_dir, earlier))  # O(attempt)
        if rows[-1]["passed"] or not rows[-1].get("started", True):  # a refused start has the same cause again | O(1)
            break  # O(1)
    return rows  # O(1)


def run(cases: list, src: Path, out: Path, rerun: bool = True, timeout_s: int = 5400, seal=None) -> list:
    seal = seal or golden_seal  # O(1)
    ABORT.clear()  # O(1)
    plugin = _plugin(src)  # O(1)
    before = {c["id"]: _earlier(out, c["id"]) for c in cases}  # read before this run appends | O(cases * lines)
    work = Path(tempfile.mkdtemp(prefix="golden-"))  # O(1)
    rows = []  # O(1)
    try:  # O(1)
        err = None  # O(1)
        with ThreadPoolExecutor(max_workers=max(len(cases), 1)) as ex:  # O(cases)
            futs = [ex.submit(_case, c, src, work, rerun, timeout_s, seal, plugin, Path(out).parent, before[c["id"]]) for c in cases]  # O(cases)
            try:  # O(1)
                for f in futs:  # O(cases)
                    try:  # one case failing never drops the rows of the others | O(1)
                        rows.extend(f.result())  # O(1)
                    except Exception as e:  # noqa: BLE001 | O(1)
                        err = err or e  # O(1)
            except BaseException:  # Ctrl-C: end the waits, the attempts' finally clauses clean their clones | O(1)
                ABORT.set()  # O(1)
                ex.shutdown(wait=True, cancel_futures=True)  # O(attempt)
                raise  # O(1)
        if err:  # O(1)
            raise err  # O(1)
    finally:  # O(1)
        shutil.rmtree(work, ignore_errors=True)  # O(files)
        if rows:  # O(1)
            Path(out).parent.mkdir(parents=True, exist_ok=True)  # O(1)
            with open(out, "a") as fh:  # append, never rewrite
                for r in rows:  # O(rows)
                    fh.write(json.dumps(r) + "\n")  # O(row)
    return rows  # O(1)


def _history(out: Path, cid: str | None) -> int:
    rows = []  # O(1)
    if out.exists():  # O(1)
        for x in out.read_text(encoding="utf-8", errors="replace").splitlines():  # O(lines)
            try:  # a torn line never ends the history | O(1)
                r = json.loads(x) if x.strip() else None  # O(len)
            except ValueError:  # O(1)
                continue  # O(1)
            if isinstance(r, dict):  # O(1)
                rows.append(r)  # O(1)
    by: dict = {}  # O(1)
    shares: dict = {}  # O(1)
    for r in rows:  # O(rows)
        usd = r.get("lead_usd")  # O(1)
        if not isinstance(usd, (int, float)) or isinstance(usd, bool) or usd <= 0:  # a row with no cost is no run to count | O(1)
            continue  # O(1)
        if r.get("row") == "golden" and r.get("started", True) and isinstance(r.get("case"), str) and (cid is None or r.get("case") == cid):  # O(1)
            by.setdefault(r["case"], []).append(usd)  # O(1)
            sh = r.get("hidden_share")  # O(1)
            if isinstance(sh, (int, float)) and not isinstance(sh, bool):  # O(1)
                shares.setdefault(r["case"], []).append(sh)  # O(1)
    for k, v in sorted(by.items()):  # O(cases)
        spread = (max(v) / min(v)) if min(v) else 0.0  # O(runs)
        noise = f"max/min {spread:.2f}" if len(v) >= 5 else "(noise from 5 runs)"  # O(1)
        hid = f" hidden {statistics.median(shares[k]):.2f}" if shares.get(k) else ""  # O(runs)
        print(f"{k}: runs {len(v)} median lead ${statistics.median(v):.2f}{hid} {noise}")  # O(1)
    return 0  # O(1)


def main(argv: list) -> int:
    if os.environ.get("SUPERLITE_FLEET_WORKER"):  # O(1)
        print("golden: refused inside a lead or worker", file=sys.stderr)  # O(1)
        return 2  # O(1)
    ap = argparse.ArgumentParser(prog="golden")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    r = sub.add_parser("run")  # O(1)
    g = r.add_mutually_exclusive_group()  # O(1)
    g.add_argument("--level", choices=sorted(LEVELS))  # O(1)
    g.add_argument("--ids")  # O(1)
    r.add_argument("--no-rerun", action="store_true")  # O(1)
    r.add_argument("--timeout", type=int, default=5400)  # O(1)
    r.add_argument("--root", default=".")  # O(1)
    h = sub.add_parser("history")  # O(1)
    h.add_argument("id", nargs="?")  # O(1)
    h.add_argument("--root", default=".")  # O(1)
    try:  # O(1)
        a = ap.parse_args(argv)  # O(1)
    except SystemExit as e:  # O(1)
        return int(e.code or 0)  # O(1)
    root = Path(a.root).resolve()  # O(1)
    out = root / ".superlite" / "golden-results.jsonl"  # O(1)
    if a.cmd == "history":  # O(1)
        return _history(out, a.id)  # O(rows)
    allc = {c["id"]: c for c in golden_case.cases(root)}  # O(cases)
    ids = a.ids.split(",") if a.ids else LEVELS[a.level or "minor"]  # O(1)
    bad = [i for i in ids if i not in allc]  # O(ids)
    if bad:  # O(1)
        print(f"golden: unknown case {', '.join(bad)}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    try:  # O(1)
        rows = run([allc[i] for i in ids], root, out, not a.no_rerun, a.timeout)  # O(cases)
    except Exception as e:  # a failed clone or checkout in seal | O(1)
        print(f"golden: {e}", file=sys.stderr)  # O(1)
        return 2  # O(1)
    final = {x["case"]: x for x in rows}  # the last attempt decides
    for x in final.values():  # O(cases)
        if x.get("started", True):  # O(1)
            h = x.get("hidden")  # O(1)
            hid = f"{h.get('passed', 0)}/{h.get('passed', 0) + h.get('failed', 0) + h.get('errors', 0)}" if isinstance(h, dict) else "n/a"  # O(1)
            line = f"{x['case']}: {'PASS' if x['passed'] else 'FAIL'} lead ${x.get('lead_usd', 0):.2f} total ${x.get('total_usd', 0):.2f} {x.get('wall_min', 0)} min, hidden {hid}"  # O(1)
            if x["why"]:  # O(1)
                line += f"; why: {'; '.join(x['why'])}"  # O(1)
            if x.get("warn"):  # O(1)
                line += f"; warn: {'; '.join(x['warn'])}"  # O(1)
            print(line)  # O(1)
        else:  # O(1)
            print(f"{x['case']}: NOT RUN {(x['why'] or [''])[0].splitlines()[0] if x['why'] else ''}".rstrip())  # O(1)
    return 0 if all(x["passed"] for x in final.values()) else 1  # O(cases)


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
