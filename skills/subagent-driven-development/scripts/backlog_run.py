#!/usr/bin/env python3
"""Backlog runner (phase 3): start batch leads, wait for them, answer an escalated lead.

    backlog_run.py start [B] [--cap 2] [--model opus]
    backlog_run.py wait [--timeout 21600] [--poll 10]
    backlog_run.py answer B --file F        (F = {"answers": {question: answer}})

Exit 0 done, 2 refused, 3 BLOCKED. Fleet modules are imported inside functions so tests can swap them.
"""
# Complexity notation: b = batches, w = workers, m = lines of metrics.jsonl
import argparse  # O(1)
import json  # O(1)
import subprocess  # O(1)
import sys  # O(1)
import os  # O(1)
import time  # O(1)
from pathlib import Path  # O(1)

HERE = Path(__file__).resolve().parent  # O(1)
sys.path.insert(0, str(HERE))  # O(1)
import backlog_checks as bc  # noqa: E402 | O(1)
import backlog_state as bs  # noqa: E402 | O(1)

ACTIVE = ("running", "needs_decision")


def _root() -> Path:
    return bs.main_root(Path.cwd())  # O(1) + spawn


def _now_ms() -> int:
    return int(time.time() * 1000)  # O(1)


def _run(cmd, cwd):
    try:  # O(1)
        r = subprocess.run(cmd, cwd=str(cwd), capture_output=True, text=True)  # O(cmd)
    except OSError as e:  # O(1)
        return 127, str(e)  # O(1)
    return r.returncode, (r.stdout + r.stderr).strip()  # O(out)


def _ctrl(s: str) -> bool:
    return any((ord(c) < 32 and c not in "\n\t") or ord(c) == 127 for c in s)  # O(len)


def _stop(sd, lead):  # O(w)
    import fleet
    try:  # O(1)
        fleet.stop(sd, [lead])  # O(w)
    except (Exception, SystemExit):  # O(1)
        pass  # O(1)


def _unanswered(b: dict) -> bool:
    return any(not b.get("answers", {}).get(q["question"]) for d in b.get("decisions", []) for q in d.get("questions", []))  # O(q)


def _refuse(msg: str, code: int = 2) -> int:
    print(f"BLOCKED: {msg}")  # O(1)
    return code  # O(1)


def _pick(data: dict, bid, cap: int):
    """-> (ids, None) or (None, (message, exit code))."""
    if not bid:  # O(1)
        ids = bs.startable(data, cap)  # O(b log b)
        return (ids, None) if ids else (None, ("", 0))  # O(1)
    try:  # O(1)
        b = bs.batch(data, bid)  # O(b)
    except KeyError:  # O(1)
        return None, (f"unknown batch {bid}", 2)  # O(1)
    if b["state"] not in ("planned", "parked"):  # O(1)
        return None, (f"{bid} is {b['state']}", 2)  # O(1)
    for d in b.get("depends", []):  # O(depends * b)
        if not any(x["id"] == d and x["state"] == "shipped" for x in data["batches"]):
            return None, (f"{bid} waits for {d}", 2)  # O(1)
    active = [x for x in data["batches"] if x["state"] in ACTIVE]  # O(b)
    for o in active:  # O(b * files)
        if set(b.get("files", [])) & set(o.get("files", [])):
            return None, (f"{bid} shares files with running {o['id']}", 2)  # O(1)
    if _unanswered(b):  # O(q)
        return None, (f"{bid} has open decisions (sl backlog decide --print)", 2)  # O(1)
    if len(active) >= cap:  # O(1)
        return None, (f"no free slot for {bid} (cap {cap})", 2)  # O(1)
    return [bid], None  # O(1)


def cmd_start(a) -> int:
    import fleet
    import fleet_io
    import fleet_lead
    import fleet_state
    import worktree
    import backlog_brief
    if os.environ.get("SUPERLITE_FLEET_WORKER"):  # only Max's session runs this; never a lead or worker
        return _refuse("sl backlog_run start runs only in the main session")  # O(1)
    root = _root()  # O(1)
    sd, p = root / ".superlite", bs.path(root)  # O(1)
    data = bs.load(p)  # O(size)
    if not data.get("approved_ship"):  # O(1)
        return _refuse("no ship approval yet (sl backlog decide --print)")  # O(1)
    try:  # O(1)
        live = fleet.hc.agent_states()  # O(w)
    except fleet.hc.HerdrError as e:  # O(1)
        return _refuse(f"Herdr not reachable ({e})", 3)  # O(1)
    ids, err = _pick(data, a.batch, a.cap)  # O(b log b)
    if err:  # O(1)
        if err[1] == 0:  # O(1)
            print("no startable batch")  # O(1)
            return 0  # O(1)
        return _refuse(err[0], err[1])  # O(1)
    for bid in ids:  # O(ids)
        x = bs.batch(data, bid)  # O(b)
        if x.get("agent") and x["agent"] in live:  # O(1)
            return _refuse(f"{bid} lead {x.get('lead', '')} is still running (sl backlog wait)")  # O(1)
    summaries = []  # O(1)
    for b in data["batches"]:  # O(b)
        f = sd / "backlog" / f"{b['id']}.md"  # O(1)
        if b["state"] == "shipped" and f.is_file():  # O(1)
            summaries.append(str(f))  # O(1)
    fleet_on = False  # O(1)
    for bid in ids:  # O(ids)
        batch = bs.batch(data, bid)  # O(b)
        wt, _ = worktree.ensure(f"{bid.lower()}-{batch['topic']}", root)  # O(w) + spawns
        wt = Path(wt)  # O(1)
        branch = "superlite/" + wt.name.replace("superlite-", "", 1)  # O(1)
        ctx = {"sl": str(HERE / "sl"), "backlog_md": str(HERE.parent / "backlog.md"), "repo": data.get("repo", ""),
               "approved": data.get("approved_ship"), "titles": data.get("titles", {}), "summaries": summaries,
               "resume": batch["state"] == "parked" and bool(batch.get("worktree"))}  # O(1)
        brief = wt / ".superlite" / "briefs" / "lead.md"  # O(1)
        brief.parent.mkdir(parents=True, exist_ok=True)  # O(1)
        brief.write_text(backlog_brief.lead_brief(batch, ctx), encoding="utf-8")  # O(size)
        if not fleet_on and not fleet_state.is_on(sd):  # O(w)
            fleet.main(["on", "--plan", str(sd)])  # O(w)
        fleet_on = True  # O(1)
        try:  # O(1)
            rec = fleet_lead.spawn_lead(sd, wt, a.model)  # O(1) + spawns
        except SystemExit as e:  # O(1)
            return e.code if isinstance(e.code, int) else 3  # O(1)
        fleet_io.send_brief(sd, rec["id"], str(brief), bid)  # O(w)

        def mark(d, bid=bid, rec=rec, wt=wt, branch=branch):  # O(b)
            x = bs.batch(d, bid)
            x.update({"state": "running", "lead": rec["id"], "agent": rec["name"], "worktree": str(wt), "branch": branch,
                      "since": _now_ms(), "reason": "", "ship_runs": 0})
        bs.update(p, mark)  # O(size)
        print(f"{bid} running lead={rec['id']} worktree={wt}")  # O(1)
    return 0  # O(1)


def _park(p, sd, repo, b, reason, out):  # O(size)
    import fleet  # noqa: F401
    import ship_lock
    bid, lead = b["id"], b["lead"]  # O(1)

    def mark(d):  # O(b)
        x = bs.batch(d, bid)
        x["state"], x["reason"] = "parked", reason
    bs.update(p, mark)  # O(size)
    try:  # O(1)
        ship_lock.release(ship_lock.lock_path(repo), bid)  # O(1)
    except (OSError, ValueError):  # O(1)
        pass  # O(1)
    _stop(sd, lead)  # O(w)
    out.append(f"{bid} parked: {reason}")  # O(1)


def _shipped(p, sd, root, b, wt) -> list:  # O(size)
    bid = b["id"]
    bs.update(p, lambda d: bs.batch(d, bid).__setitem__("state", "shipped"))  # O(size)
    _stop(sd, b["lead"])  # O(w)
    pr = f" PR #{b['pr']}" if b.get("pr") else ""
    ver = f" {b['version']}" if b.get("version") else ""
    out = [f"{bid} shipped{pr}{ver} summary={sd / 'backlog' / (bid + '.md')}"]
    if b.get("open_issues"):  # O(k)
        out.append(f"{bid} OPEN " + " ".join(f"#{n}" for n in b["open_issues"]))  # O(k)
    rc, msg = _run(["maxapp", "ship", "-C", str(wt)], root)  # O(cmd)
    if rc:  # O(1)
        out.append(f"{bid} cleanup: {(msg.splitlines() or ['failed'])[-1][:120]}")  # O(len)
    return out


def _round(root, sd, p, states) -> list:
    import fleet_io
    import fleet
    import ship_lock
    data = bs.load(p)  # O(size)
    out = []  # O(1)
    for b in [x for x in data["batches"] if x["state"] == "parked" and x.get("agent") and x.get("lead")]:  # O(b)
        if states.get("v") is None:  # O(1)
            try:  # O(1)
                states["v"] = fleet.hc.agent_states()  # O(w)
            except fleet.hc.HerdrError:  # O(1)
                states["v"] = False  # O(1)
        if states["v"] is not False and b["agent"] in states["v"]:  # the lead parked the batch itself and still lives
            try:  # O(1)
                ship_lock.release(ship_lock.lock_path(data.get("repo", "")), b["id"])  # O(1)
            except (OSError, ValueError):  # O(1)
                pass  # O(1)
            _stop(sd, b["lead"])  # O(w)
            out.append(f"{b['id']} parked: {' '.join(str(b.get('reason') or 'parked by its lead').split())[:120]}")  # O(len)
    for b in [x for x in data["batches"] if x["state"] == "running"]:  # O(b)
        bid, wt, since = b["id"], Path(b.get("worktree") or ""), b.get("since", 0)  # O(1)
        rec = fleet_io.latest_stop(sd, b["lead"], since)  # O(m)
        if rec is None:  # O(1)
            if states.get("v") is None:  # O(1)
                try:  # O(1)
                    states["v"] = fleet.hc.agent_states()  # O(w)
                except fleet.hc.HerdrError:  # O(1)
                    states["v"] = False  # O(1)
            if states["v"] is not False and b.get("agent") not in states["v"]:  # O(1)
                if b.get("merged"):  # PR is merged: the lead's pane ending is the normal end
                    out.extend(_shipped(p, sd, root, b, wt))  # O(size)
                    continue  # O(1)
                _park(p, sd, data.get("repo", ""), b, "lead pane gone", out)  # O(size)
            continue  # O(1)
        q = wt / ".superlite" / "question.json"  # O(1)
        try:  # O(1)
            fresh = q.stat().st_mtime * 1000 >= since  # O(1)
        except OSError:  # O(1)
            fresh = False  # O(1)
        if fresh:  # O(1)
            try:  # O(1)
                errs = bc.check_question(json.loads(q.read_text(encoding="utf-8")))  # O(size)
            except (OSError, ValueError, RecursionError):  # O(1)
                errs = ["not JSON"]  # O(1)
            if errs:  # O(1)
                _park(p, sd, data.get("repo", ""), b, f"invalid question.json: {'; '.join(errs)}", out)  # O(size)
            else:  # O(1)
                bs.update(p, lambda d, bid=bid: bs.batch(d, bid).__setitem__("state", "needs_decision"))  # O(size)
                out.append(f"{bid} needs_decision question={q}")  # O(1)
            continue  # O(1)
        if b.get("merged"):  # O(1)
            out.extend(_shipped(p, sd, root, b, wt))  # O(size)
            continue  # O(1)
        last = " ".join(str(rec.get("last") or "lead stopped").split())[:120]  # O(len)
        _park(p, sd, data.get("repo", ""), b, last, out)  # O(size)
    return out  # O(b)


def cmd_wait(a) -> int:
    root = _root()  # O(1)
    sd, p = root / ".superlite", bs.path(root)  # O(1)
    if not any(b["state"] == "running" or (b["state"] == "parked" and b.get("lead")) for b in bs.load(p)["batches"]):  # O(b)
        print("no running batch")  # O(1)
        return 0  # O(1)
    deadline = time.monotonic() + a.timeout  # O(1)
    while True:  # O(timeout / poll)
        lines = _round(root, sd, p, {})  # O(b * m)
        if lines:  # O(1)
            print("\n".join(lines))  # O(lines)
            return 0  # O(1)
        if not any(b["state"] == "running" for b in bs.load(p)["batches"]):  # O(b)
            print("no running batch")  # O(1)
            return 0  # O(1)
        if time.monotonic() >= deadline:  # O(1)
            print("TIMEOUT")  # O(1)
            return 0  # O(1)
        time.sleep(a.poll)  # O(poll)


def _answers(f) -> tuple:
    try:  # O(1)
        obj = json.loads(Path(f).read_text(encoding="utf-8"))  # O(size)
    except (OSError, ValueError) as e:  # O(1)
        return None, f"cannot read {f}: {e}"  # O(1)
    ans = obj.get("answers") if isinstance(obj, dict) else None  # O(1)
    if not isinstance(ans, dict) or not 1 <= len(ans) <= 4:  # O(1)
        return None, "answers: 1 to 4 entries"  # O(1)
    for k, v in ans.items():  # O(4 * len)
        if not isinstance(k, str) or not isinstance(v, str) or not 1 <= len(v) <= 300 or _ctrl(v) or _ctrl(k):
            return None, f"bad answer for {str(k)[:60]}"  # O(1)
    return ans, ""  # O(1)


def cmd_answer(a) -> int:
    import fleet_io
    if os.environ.get("SUPERLITE_FLEET_WORKER"):  # only Max's session runs this; never a lead or worker
        return _refuse("sl backlog_run answer runs only in the main session")  # O(1)
    root = _root()  # O(1)
    sd, p = root / ".superlite", bs.path(root)  # O(1)
    try:  # O(1)
        b = bs.batch(bs.load(p), a.batch)  # O(b)
    except KeyError:  # O(1)
        return _refuse(f"unknown batch {a.batch}")  # O(1)
    if b["state"] != "needs_decision":  # O(1)
        return _refuse(f"{a.batch} is {b['state']}, not waiting for an answer")  # O(1)
    ans, err = _answers(a.file)  # O(size)
    if ans is None:  # O(1)
        return _refuse(err)  # O(1)
    n = int(b.get("questions", 0)) + 1  # O(1)
    ed = Path(b["worktree"]) / ".superlite"  # O(1)
    q = ed / "question.json"  # O(1)
    if q.is_file():  # O(1)
        q.replace(ed / f"question-{n}.json")  # O(1)
    af = ed / f"answer-{n}.json"  # O(1)
    af.write_text(json.dumps({"answers": ans}, indent=2), encoding="utf-8")  # O(size)

    def mark(d):  # O(b)
        x = bs.batch(d, a.batch)
        x.setdefault("answers", {}).update(ans)
        x.update({"questions": n, "state": "running", "since": _now_ms()})
    bs.update(p, mark)  # O(size)
    msg = f"Max answered your question: read {af} (record it as a Ruling), then go on with the batch."  # O(1)
    rc = fleet_io.main(["send", b["lead"], "--text", msg, "--plan", str(sd)])  # O(w)
    if rc:  # O(1)
        bs.update(p, lambda d: bs.batch(d, a.batch).__setitem__("state", "needs_decision"))  # O(size)
        return 3  # O(1)
    print(f"{a.batch} answered: {af.name} sent to {b['lead']}")  # O(1)
    return 0  # O(1)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(prog="backlog_run")  # O(1)
    sub = ap.add_subparsers(dest="cmd", required=True)  # O(1)
    s = sub.add_parser("start")  # O(1)
    s.add_argument("batch", nargs="?")  # O(1)
    s.add_argument("--cap", type=int, default=2)  # O(1)
    s.add_argument("--model", default="opus")  # O(1)
    w = sub.add_parser("wait")  # O(1)
    w.add_argument("--timeout", type=int, default=21600)  # O(1)
    w.add_argument("--poll", type=int, default=10)  # O(1)
    an = sub.add_parser("answer")  # O(1)
    an.add_argument("batch")  # O(1)
    an.add_argument("--file", required=True)  # O(1)
    a = ap.parse_args(argv)  # O(1)
    return {"start": cmd_start, "wait": cmd_wait, "answer": cmd_answer}[a.cmd](a)  # O(1)


if __name__ == "__main__":
    sys.exit(main())
